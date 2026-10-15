"""Optimizador de itinerario (version greedy / voraz).

Las restricciones NO viven aqui: este modulo solo decide el ORDEN en que se prueban los lugares.
Cada candidato se valida con restricciones.revisar_parada(), la misma funcion que usa el
algoritmo genetico, asi que ambos cumplen exactamente las mismas reglas.

Estrategia voraz: en cada paso se elige, entre los lugares que SI se pueden agregar, el de mayor
`valor` inmediato (aporte al fitness de ese lugar). Nunca se reconsidera una decision ya tomada,
por eso puede quedar en un optimo local.
"""
from app.fitness import PESO_TRASLADO, PESO_ESPERA, PENA_REPETICION, BONO_COMIDA, es_nocturno
from app.horarios import a_min, a_hhmm                                  # noqa: F401 (re-export)
from app.recomendador import recomendar
from app.restricciones import (                                         # noqa: F401 (re-export)
    VELOCIDAD_KMH, MIN_TRASLADO, VENTANA_COMIDA, COMIDA_FUERTE, MAX_POR_CATEGORIA, MAX_DEFAULT,
    ESPERA_MAX, distancia_km, traslado_min, EstadoDia, preparar_candidatos, revisar_parada,
    agregar_parada)

POOL_N = 40                  # candidatos que se pasan al optimizador
POOL_MAX_POR_CATEGORIA = 8   # diversidad dentro del pool
ESPERA_PREFERIDA = 45        # el voraz prefiere esperas cortas; solo si no hay, relaja a ESPERA_MAX


def construir_pool(df, perfil, pesos=None):
    """Candidatos que reciben tanto el voraz como el genetico (mismo recomendador y filtros)."""
    return recomendar(df, perfil, n=POOL_N, max_por_categoria=POOL_MAX_POR_CATEGORIA, pesos=pesos)


def construir_desde_candidatos(candidatos, perfil):
    """Arma el dia eligiendo, en cada paso, el mejor lugar que cumpla las restricciones."""
    estado = EstadoDia(perfil)
    # si el grupo quiere vida nocturna, se reserva presupuesto para un bar (heuristica del
    # voraz: no es una restriccion, solo evita gastar todo antes de llegar a la noche)
    costos_bar = [c["costo"] for c in candidatos if c["categoria"] == "bar"]
    reserva = min(costos_bar) if (es_nocturno(perfil) and costos_bar) else 0.0
    bar_hecho = False

    while True:
        mejor = None
        for espera_max in (ESPERA_PREFERIDA, ESPERA_MAX):
            mejor_val = -1e9
            for c in candidatos:
                datos, _ = revisar_parada(estado, c, perfil, espera_max)
                if datos is None:
                    continue
                cat = c["categoria"]
                if cat != "bar" and not bar_hecho and estado.gasto + c["costo"] + reserva > estado.presupuesto:
                    continue
                _, _, tras, espera = datos
                valor = c["puntaje"] - PESO_TRASLADO * tras - PESO_ESPERA * espera
                if estado.actual is not None and cat == estado.actual["categoria"]:
                    valor -= PENA_REPETICION
                if cat in COMIDA_FUERTE and not estado.comio:
                    valor += BONO_COMIDA          # prioriza que el dia incluya comida
                if valor > mejor_val:
                    mejor_val = valor
                    mejor = (c, datos)
            if mejor is not None:
                break
        if mejor is None:
            break
        c, datos = mejor
        agregar_parada(estado, c, datos)
        if c["categoria"] == "bar":
            bar_hecho = True
    return estado.ruta


def construir(pool, perfil, usar_horarios_osm=True):
    """Version que recibe el pool (DataFrame de recomendar)."""
    return construir_desde_candidatos(preparar_candidatos(pool, perfil, usar_horarios_osm), perfil)


def resumen(ruta):
    return {
        "lugares": len(ruta),
        "gasto_por_persona": round(sum(p["costo_estimado"] for p in ruta), 2),
        "traslado_total_min": sum(p["traslado_min"] for p in ruta),
        "espera_total_min": sum(p["espera_min"] for p in ruta),
        "puntaje_total": round(sum(p["puntaje"] for p in ruta), 3),
        "incluye_comida": any(p["categoria"] in COMIDA_FUERTE for p in ruta),
        "hora_inicio": ruta[0]["llegada"] if ruta else "",
        "hora_fin": ruta[-1]["salida"] if ruta else "",
        # duracion de punta a punta del itinerario y tiempo realmente dentro de los lugares
        "duracion_total_min": (a_min(ruta[-1]["salida"]) - a_min(ruta[0]["llegada"])) if ruta else 0,
        "tiempo_en_lugares_min": sum(p["duracion_min"] for p in ruta),
        # cuantas paradas descansan en un horario real de OSM y cuantas en una estimacion
        "paradas_horario_real": sum(1 for p in ruta if p.get("horario_fuente") == "osm"),
        "paradas_horario_estimado": sum(1 for p in ruta if p.get("horario_fuente") != "osm"),
    }


def generar_itinerario(df, perfil):
    pool = construir_pool(df, perfil)
    if pool.empty:
        return {"paradas": [], "resumen": resumen([])}
    ruta = construir(pool, perfil)
    return {"paradas": ruta, "resumen": resumen(ruta)}
