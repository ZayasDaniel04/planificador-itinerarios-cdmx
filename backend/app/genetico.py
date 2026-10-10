"""Algoritmo genetico para el itinerario, comparable con el greedy."""
import random
import time

from app.itinerario import (a_min, a_hhmm, traslado_min, construir, resumen,
                            VENTANA_COMIDA, COMIDA_FUERTE, MAX_POR_CATEGORIA, MAX_DEFAULT)
from app.recomendador import recomendar

ESPERA_MAX = 120


def preparar(pool):
    """Convierte el pool (DataFrame) en una lista de diccionarios, mas rapida de simular."""
    filas = []
    for _, l in pool.iterrows():
        filas.append({
            "id": int(l["id"]),
            "nombre": str(l["nombre"]),
            "categoria": str(l["categoria"]),
            "zona": str(l["zona"]),
            "lat": float(l["lat"]),
            "lon": float(l["lon"]),
            "apertura": a_min(l["hora_apertura"]),
            "cierre": a_min(l["hora_cierre"]),
            "duracion": int(l["duracion_min"]),
            "costo": float(l["costo_estimado"]),
            "puntaje": float(l["puntaje"]),
        })
    return filas


def simular(orden, filas, perfil):
    """Recorre los lugares en el orden dado y se queda con los que caben en el dia."""
    fin_dia = a_min(perfil.hora_fin)
    reloj = a_min(perfil.hora_inicio)
    gasto = 0.0
    actual = None
    por_cat = {}
    comio = False
    ruta = []
    for i in orden:
        l = filas[i]
        cat = l["categoria"]
        if por_cat.get(cat, 0) >= MAX_POR_CATEGORIA.get(cat, MAX_DEFAULT):
            continue
        fuerte = cat in COMIDA_FUERTE
        if fuerte and comio:
            continue
        tras = traslado_min(actual, l) if actual is not None else 0
        llegada = reloj + tras
        inicio_v = max(llegada, l["apertura"])
        if fuerte:
            inicio_v = max(inicio_v, VENTANA_COMIDA[0])
            if inicio_v > VENTANA_COMIDA[1]:
                continue
        espera = inicio_v - llegada
        fin_v = inicio_v + l["duracion"]
        if espera > ESPERA_MAX or fin_v > fin_dia or fin_v > l["cierre"]:
            continue
        if gasto + l["costo"] > perfil.presupuesto_por_persona:
            continue
        ruta.append({
            "orden": len(ruta) + 1,
            "id": l["id"],
            "nombre": l["nombre"],
            "categoria": cat,
            "zona": l["zona"],
            "lat": l["lat"],
            "lon": l["lon"],
            "llegada": a_hhmm(inicio_v),
            "salida": a_hhmm(fin_v),
            "duracion_min": l["duracion"],
            "traslado_min": int(tras),
            "espera_min": int(espera),
            "costo_estimado": l["costo"],
            "puntaje": round(l["puntaje"], 3),
        })
        reloj = fin_v
        gasto += l["costo"]
        actual = l
        por_cat[cat] = por_cat.get(cat, 0) + 1
        if fuerte:
            comio = True
    return ruta


def fitness(ruta, perfil):
    """Calidad de un itinerario (mayor es mejor). Sirve para greedy y genetico."""
    if not ruta:
        return -1e9
    f = sum(p["puntaje"] for p in ruta)
    f -= 0.01 * sum(p["traslado_min"] for p in ruta)
    f -= 0.005 * sum(p["espera_min"] for p in ruta)
    if any(p["categoria"] in COMIDA_FUERTE for p in ruta):
        f += 0.5
    for a, b in zip(ruta, ruta[1:]):
        if a["categoria"] == b["categoria"]:
            f -= 0.15
    nocturno = perfil.intereses.get("vida_nocturna", 0) >= 0.5 and a_min(perfil.hora_fin) >= 21 * 60
    if nocturno and any(p["categoria"] == "bar" for p in ruta):
        f += 0.4
    return f


def _cruce(p1, p2, rnd):
    """Cruce de orden (OX): conserva un tramo del padre 1 y completa con el orden del padre 2."""
    n = len(p1)
    a, b = sorted(rnd.sample(range(n), 2))
    segmento = p1[a:b]
    en_seg = set(segmento)
    resto = [g for g in p2 if g not in en_seg]
    return resto[:a] + segmento + resto[a:]


def _mutar(ind, rnd):
    if rnd.random() < 0.4:                      # intercambia dos lugares
        i, j = rnd.sample(range(len(ind)), 2)
        ind[i], ind[j] = ind[j], ind[i]
    if rnd.random() < 0.4:                      # mueve un lugar a otra posicion
        g = ind.pop(rnd.randrange(len(ind)))
        ind.insert(rnd.randrange(len(ind) + 1), g)


def genetico(filas, perfil, semilla=None, poblacion=60, generaciones=80, seed=42):
    rnd = random.Random(seed)
    n = len(filas)
    base = list(range(n))
    pob = []
    if semilla:
        en_sem = set(semilla)
        resto = [g for g in base if g not in en_sem]
        rnd.shuffle(resto)
        pob.append(list(semilla) + resto)
    while len(pob) < poblacion:
        ind = base[:]
        rnd.shuffle(ind)
        pob.append(ind)

    def evaluar(ind):
        ruta = simular(ind, filas, perfil)
        return fitness(ruta, perfil), ruta

    def torneo(pob, evals):
        cand = rnd.sample(range(len(pob)), 3)
        return pob[max(cand, key=lambda i: evals[i][0])]

    evals = [evaluar(ind) for ind in pob]
    historial = []
    for _ in range(generaciones):
        orden = sorted(range(len(pob)), key=lambda i: evals[i][0], reverse=True)
        pob = [pob[i] for i in orden]
        evals = [evals[i] for i in orden]
        historial.append(round(evals[0][0], 3))
        nueva = [pob[0][:], pob[1][:]]          # elitismo
        while len(nueva) < poblacion:
            p1 = torneo(pob, evals)
            p2 = torneo(pob, evals)
            hijo = _cruce(p1, p2, rnd) if rnd.random() < 0.9 else p1[:]
            _mutar(hijo, rnd)
            nueva.append(hijo)
        pob = nueva
        evals = [evaluar(ind) for ind in pob]

    mejor = max(range(len(pob)), key=lambda i: evals[i][0])
    return evals[mejor][1], evals[mejor][0], historial


def comparar(df, perfil, generaciones=80, poblacion=60, con_semilla=True):
    """Corre greedy y genetico sobre los mismos candidatos y devuelve ambos resultados."""
    pool = recomendar(df, perfil, n=40, max_por_categoria=8)
    if pool.empty:
        return None
    filas = preparar(pool)

    t0 = time.time()
    ruta_g = construir(pool, perfil)
    t_g = time.time() - t0
    res_g = {"ruta": ruta_g, "fitness": fitness(ruta_g, perfil),
             "seg": t_g, "resumen": resumen(ruta_g)}

    if len(filas) < 5 or not ruta_g:
        return {"greedy": res_g, "genetico": res_g}

    pos = {f["id"]: i for i, f in enumerate(filas)}
    semilla = [pos[p["id"]] for p in ruta_g] if con_semilla else None
    t0 = time.time()
    ruta_ga, f_ga, hist = genetico(filas, perfil, semilla, poblacion, generaciones)
    t_ga = time.time() - t0
    res_ga = {"ruta": ruta_ga, "fitness": f_ga, "seg": t_ga,
              "resumen": resumen(ruta_ga), "historial": hist}
    return {"greedy": res_g, "genetico": res_ga}
