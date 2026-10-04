"""Optimizador de itinerario (version greedy)."""
import math

from app.recomendador import recomendar

VELOCIDAD_KMH = 18          # velocidad promedio en la ciudad
MIN_TRASLADO = 5            # minimo por traslado, en minutos
VENTANA_COMIDA = (12 * 60 + 30, 16 * 60)
COMIDA_FUERTE = ("restaurante", "mercado")
MAX_POR_CATEGORIA = {"cafeteria": 1, "libreria": 1, "cine": 1}
MAX_DEFAULT = 2


def a_min(hhmm):
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def a_hhmm(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia Haversine entre dos puntos."""
    r = 6371.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = f2 - f1
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def traslado_min(a, b):
    km = distancia_km(a["lat"], a["lon"], b["lat"], b["lon"])
    return max(MIN_TRASLADO, round(km / VELOCIDAD_KMH * 60))


def construir(pool, perfil):
    """Arma el dia eligiendo, en cada paso, el mejor lugar que cumpla las restricciones."""
    fin_dia = a_min(perfil.hora_fin)
    reloj = a_min(perfil.hora_inicio)
    presupuesto = perfil.presupuesto_por_persona
    gasto = 0.0
    actual = None
    usados = set()
    por_cat = {}
    comio = False
    ruta = []
    # si el grupo quiere vida nocturna, se reserva presupuesto para un bar
    nocturno = perfil.intereses.get("vida_nocturna", 0) >= 0.5 and fin_dia >= 21 * 60
    bares = pool[pool["categoria"] == "bar"]
    reserva = float(bares["costo_estimado"].min()) if (nocturno and not bares.empty) else 0.0
    bar_hecho = False

    while True:
        mejor = None
        for max_espera in (45, 120):     # primero sin esperar casi nada; si no hay, se relaja
            mejor_val = -1e9
            for idx, l in pool.iterrows():
                if idx in usados:
                    continue
                cat = l["categoria"]
                if por_cat.get(cat, 0) >= MAX_POR_CATEGORIA.get(cat, MAX_DEFAULT):
                    continue
                fuerte = cat in COMIDA_FUERTE
                if fuerte and comio:
                    continue

                tras = traslado_min(actual, l) if actual is not None else 0
                llegada = reloj + tras
                inicio_v = max(llegada, a_min(l["hora_apertura"]))
                if fuerte:
                    inicio_v = max(inicio_v, VENTANA_COMIDA[0])
                    if inicio_v > VENTANA_COMIDA[1]:
                        continue
                espera = inicio_v - llegada
                fin_v = inicio_v + int(l["duracion_min"])

                if espera > max_espera:
                    continue
                if fin_v > fin_dia or fin_v > a_min(l["hora_cierre"]):
                    continue
                if gasto + l["costo_estimado"] > presupuesto:
                    continue
                if cat != "bar" and not bar_hecho and gasto + l["costo_estimado"] + reserva > presupuesto:
                    continue

                valor = l["puntaje"] - 0.01 * tras - 0.005 * espera
                if actual is not None and cat == actual["categoria"]:
                    valor -= 0.15
                if fuerte and not comio:
                    valor += 0.5          # prioriza que el dia incluya comida
                if valor > mejor_val:
                    mejor_val = valor
                    mejor = (idx, l, tras, inicio_v, fin_v, espera)
            if mejor is not None:
                break

        if mejor is None:
            break

        idx, l, tras, inicio_v, fin_v, espera = mejor
        ruta.append({
            "orden": len(ruta) + 1,
            "id": int(l["id"]),
            "nombre": str(l["nombre"]),
            "categoria": str(l["categoria"]),
            "zona": str(l["zona"]),
            "lat": float(l["lat"]),
            "lon": float(l["lon"]),
            "llegada": a_hhmm(inicio_v),
            "salida": a_hhmm(fin_v),
            "duracion_min": int(l["duracion_min"]),
            "traslado_min": int(tras),
            "espera_min": int(espera),
            "costo_estimado": float(l["costo_estimado"]),
            "puntaje": round(float(l["puntaje"]), 3),
        })
        reloj = fin_v
        gasto += float(l["costo_estimado"])
        actual = l
        usados.add(idx)
        por_cat[l["categoria"]] = por_cat.get(l["categoria"], 0) + 1
        if l["categoria"] in COMIDA_FUERTE:
            comio = True
        if l["categoria"] == "bar":
            bar_hecho = True
    return ruta


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
    }


def generar_itinerario(df, perfil):
    pool = recomendar(df, perfil, n=40, max_por_categoria=8)
    if pool.empty:
        return {"paradas": [], "resumen": resumen([])}
    ruta = construir(pool, perfil)
    return {"paradas": ruta, "resumen": resumen(ruta)}
