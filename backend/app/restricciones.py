"""Restricciones compartidas por el algoritmo voraz y el genetico.

Antes, el voraz (itinerario.construir) y el genetico (genetico.simular) tenian cada uno su
propia copia de las reglas. Ahora ambos llaman a las mismas funciones de este modulo:

  preparar_candidatos()  convierte el pool recomendado en candidatos con su horario del dia
  revisar_parada()       decide si un lugar puede ir a continuacion (UNICA fuente de reglas)
  agregar_parada()       actualiza el estado del dia y registra la parada
  validar_itinerario()   revision independiente de un itinerario ya armado

Restricciones DURAS (un itinerario que las incumpla es invalido):
  1. No repetir lugares (ni por id ni por nombre normalizado).
  2. Cada visita cabe completa en una ventana de apertura del lugar ese dia (horario real de
     OSM si existe; si no, estimacion por categoria).
  3. La ultima salida no pasa de la hora de fin del usuario.
  4. El gasto acumulado por persona no pasa del presupuesto.
  5. Cada visita dura exactamente duracion_min; el traslado se calcula con Haversine a
     VELOCIDAD_KMH (minimo MIN_TRASLADO); no se llega antes de terminar el lugar anterior
     mas el traslado.
  6. La espera antes de una visita no pasa de ESPERA_MAX minutos.
  7. Maximo por categoria (MAX_POR_CATEGORIA / MAX_DEFAULT).
  8. Una sola comida fuerte (restaurante o mercado), que empiece dentro de VENTANA_COMIDA.
  9. Perfil del visitante: todo lugar debe pasar pasa_filtros() (ninos, adultos mayores,
     nivel de actividad, zona, gasto maximo por lugar y dia abierto).
"""
import math
import re
import unicodedata
from functools import lru_cache

from app.horarios import a_min, a_hhmm, ventanas_lugar
from app.reglas import pasa_filtros

VELOCIDAD_KMH = 18          # velocidad promedio en la ciudad
MIN_TRASLADO = 5            # minimo por traslado, en minutos
VENTANA_COMIDA = (12 * 60 + 30, 16 * 60)
COMIDA_FUERTE = ("restaurante", "mercado")
MAX_POR_CATEGORIA = {"cafeteria": 1, "libreria": 1, "cine": 1}
MAX_DEFAULT = 2
ESPERA_MAX = 120            # espera maxima permitida antes de una visita, en minutos
_EPS = 1e-9


# ---------------------------------------------------------------- distancias y nombres
def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia Haversine entre dos puntos."""
    r = 6371.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = f2 - f1
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=500_000)
def _traslado_coords(lat1, lon1, lat2, lon2):
    km = distancia_km(lat1, lon1, lat2, lon2)
    return max(MIN_TRASLADO, round(km / VELOCIDAD_KMH * 60))


def traslado_min(a, b):
    """Minutos de traslado entre dos lugares (con cache: el genetico repite mucho los pares)."""
    return _traslado_coords(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))


def normalizar_nombre(nombre):
    """'Café  El Péndulo' -> 'cafe el pendulo' (para detectar el mismo lugar escrito distinto)."""
    s = unicodedata.normalize("NFKD", str(nombre).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", s).strip()


# ---------------------------------------------------------------- candidatos y estado
def preparar_candidatos(pool, perfil, usar_horarios_osm=True):
    """Convierte el pool (DataFrame de recomendar) en candidatos listos para simular.

    Cada candidato trae las ventanas de apertura DEL DIA del perfil y la procedencia de ese
    horario ("osm" real o "estimado_categoria"). Greedy y genetico parten de esta misma lista."""
    candidatos = []
    for _, l in pool.iterrows():
        ventanas, fuente = ventanas_lugar(l, perfil.dia_semana, usar_horarios_osm)
        costo_fuente = l.get("costo_fuente", "estimado_categoria")
        if not isinstance(costo_fuente, str):
            costo_fuente = "estimado_categoria"
        candidatos.append({
            "id": int(l["id"]),
            "nombre": str(l["nombre"]),
            "nombre_norm": normalizar_nombre(l["nombre"]),
            "categoria": str(l["categoria"]),
            "zona": str(l["zona"]),
            "lat": float(l["lat"]),
            "lon": float(l["lon"]),
            "ventanas": ventanas,
            "horario_fuente": fuente,
            "duracion": int(l["duracion_min"]),
            "costo": float(l["costo_estimado"]),
            "costo_fuente": costo_fuente,
            "puntaje": float(l["puntaje"]),
        })
    return candidatos


class EstadoDia:
    """Lo que ya paso en el dia: hora actual, gasto, lugar actual y lugares usados."""

    def __init__(self, perfil):
        self.fin_dia = a_min(perfil.hora_fin)
        self.reloj = a_min(perfil.hora_inicio)
        self.presupuesto = perfil.presupuesto_por_persona
        self.gasto = 0.0
        self.actual = None
        self.por_cat = {}
        self.comio = False
        self.ids = set()
        self.nombres = set()
        self.ruta = []


def revisar_parada(estado, c, perfil, espera_max=ESPERA_MAX):
    """Unica definicion de las restricciones duras para agregar el candidato `c` al final del dia.

    Devuelve ((inicio, fin, traslado, espera), "") si es posible, o (None, motivo) si no.
    `espera_max` solo puede endurecerse (el voraz lo usa para preferir esperas cortas); nunca
    puede pasar de ESPERA_MAX."""
    espera_max = min(espera_max, ESPERA_MAX)
    if c["id"] in estado.ids or c["nombre_norm"] in estado.nombres:
        return None, "lugar_repetido"
    cat = c["categoria"]
    if estado.por_cat.get(cat, 0) >= MAX_POR_CATEGORIA.get(cat, MAX_DEFAULT):
        return None, "limite_por_categoria"
    fuerte = cat in COMIDA_FUERTE
    if fuerte and estado.comio:
        return None, "segunda_comida_fuerte"

    tras = traslado_min(estado.actual, c) if estado.actual is not None else 0
    llegada = estado.reloj + tras
    cota = max(llegada, VENTANA_COMIDA[0]) if fuerte else llegada
    inicio = None
    for ini, fin in c["ventanas"]:
        t = max(cota, ini)
        if t + c["duracion"] <= fin:
            inicio = t
            break
    if inicio is None:
        return None, "fuera_de_horario"
    if fuerte and inicio > VENTANA_COMIDA[1]:
        return None, "fuera_de_ventana_de_comida"
    espera = inicio - llegada
    if espera > espera_max:
        return None, "espera_excesiva"
    fin_visita = inicio + c["duracion"]
    if fin_visita > estado.fin_dia:
        return None, "excede_hora_fin"
    if estado.gasto + c["costo"] > estado.presupuesto + _EPS:
        return None, "excede_presupuesto"
    return (inicio, fin_visita, tras, espera), ""


def agregar_parada(estado, c, datos):
    """Registra la parada y avanza el estado del dia."""
    inicio, fin_visita, tras, espera = datos
    estado.ruta.append({
        "orden": len(estado.ruta) + 1,
        "id": c["id"],
        "nombre": c["nombre"],
        "categoria": c["categoria"],
        "zona": c["zona"],
        "lat": c["lat"],
        "lon": c["lon"],
        "llegada": a_hhmm(inicio),
        "salida": a_hhmm(fin_visita),
        "duracion_min": c["duracion"],
        "traslado_min": int(tras),
        "espera_min": int(espera),
        "costo_estimado": c["costo"],
        "puntaje": round(c["puntaje"], 3),
        "horario_fuente": c["horario_fuente"],
        "costo_fuente": c["costo_fuente"],
    })
    estado.reloj = fin_visita
    estado.gasto += c["costo"]
    estado.actual = c
    estado.ids.add(c["id"])
    estado.nombres.add(c["nombre_norm"])
    estado.por_cat[c["categoria"]] = estado.por_cat.get(c["categoria"], 0) + 1
    if c["categoria"] in COMIDA_FUERTE:
        estado.comio = True


# ---------------------------------------------------------------- validacion independiente
def validar_itinerario(ruta, perfil, df=None):
    """Revisa un itinerario ya armado y devuelve la lista de violaciones (vacia = valido).

    No reutiliza el estado de la simulacion: recalcula todo desde las paradas. Si se pasa el
    DataFrame de lugares tambien comprueba contra los datos (horarios, costos, duracion y
    filtros del perfil). Una ruta vacia es valida (significa 'no hay solucion')."""
    problemas = []
    if not ruta:
        return problemas
    inicio_dia, fin_dia = a_min(perfil.hora_inicio), a_min(perfil.hora_fin)
    filas = None
    if df is not None:
        filas = {int(r["id"]): r for _, r in df.iterrows()}

    ids, nombres, por_cat = set(), set(), {}
    gasto, fuertes = 0.0, 0
    reloj, anterior = inicio_dia, None
    for i, p in enumerate(ruta, 1):
        etiqueta = f'parada {i} ("{p["nombre"]}")'
        llegada, salida = a_min(p["llegada"]), a_min(p["salida"])

        if p["id"] in ids:
            problemas.append(f"{etiqueta}: lugar repetido (id {p['id']})")
        ids.add(p["id"])
        nn = normalizar_nombre(p["nombre"])
        if nn in nombres:
            problemas.append(f"{etiqueta}: nombre repetido")
        nombres.add(nn)

        if salida - llegada != p["duracion_min"]:
            problemas.append(f"{etiqueta}: la visita dura {salida - llegada} min y deberia durar "
                             f"{p['duracion_min']}")
        tras = traslado_min(anterior, p) if anterior is not None else 0
        if llegada < reloj + tras:
            problemas.append(f"{etiqueta}: llega a las {p['llegada']} pero el traslado desde la "
                             f"parada anterior no alcanza ({tras} min)")
        espera = llegada - (reloj + tras)
        if espera > ESPERA_MAX:
            problemas.append(f"{etiqueta}: espera {espera} min (maximo {ESPERA_MAX})")
        if salida > fin_dia:
            problemas.append(f"{etiqueta}: sale a las {p['salida']}, despues de la hora de fin "
                             f"{perfil.hora_fin}")

        gasto += p["costo_estimado"]
        cat = p["categoria"]
        por_cat[cat] = por_cat.get(cat, 0) + 1
        if por_cat[cat] > MAX_POR_CATEGORIA.get(cat, MAX_DEFAULT):
            problemas.append(f"{etiqueta}: demasiados lugares de la categoria {cat}")
        if cat in COMIDA_FUERTE:
            fuertes += 1
            if not (VENTANA_COMIDA[0] <= llegada <= VENTANA_COMIDA[1]):
                problemas.append(f"{etiqueta}: la comida empieza a las {p['llegada']}, fuera de "
                                 f"{a_hhmm(VENTANA_COMIDA[0])}-{a_hhmm(VENTANA_COMIDA[1])}")

        if filas is not None:
            fila = filas.get(int(p["id"]))
            if fila is None:
                problemas.append(f"{etiqueta}: el id {p['id']} no existe en el dataset")
            else:
                ventanas, _ = ventanas_lugar(fila, perfil.dia_semana)
                if not any(ini <= llegada and salida <= fin for ini, fin in ventanas):
                    problemas.append(f"{etiqueta}: {p['llegada']}-{p['salida']} queda fuera del "
                                     f"horario de apertura ({perfil.dia_semana})")
                if abs(float(fila["costo_estimado"]) - p["costo_estimado"]) > _EPS:
                    problemas.append(f"{etiqueta}: el costo no coincide con el dataset")
                if int(fila["duracion_min"]) != p["duracion_min"]:
                    problemas.append(f"{etiqueta}: la duracion no coincide con el dataset")
                if not pasa_filtros(fila, perfil):
                    problemas.append(f"{etiqueta}: no cumple los filtros del perfil del visitante")

        reloj, anterior = salida, p

    if gasto > perfil.presupuesto_por_persona + _EPS:
        problemas.append(f"gasto ${gasto:.0f} por persona excede el presupuesto "
                         f"${perfil.presupuesto_por_persona:.0f}")
    if fuertes > 1:
        problemas.append("hay mas de una comida fuerte")
    return problemas
