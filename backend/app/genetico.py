"""Algoritmo genetico para el itinerario, comparable con el voraz.

Comparte con el voraz TODO lo demas: el mismo pool de candidatos (itinerario.construir_pool),
las mismas restricciones (restricciones.revisar_parada) y la misma funcion fitness
(fitness.fitness). Solo cambia la estrategia de busqueda.

  Individuo   permutacion de los candidatos. simular() recorre ese orden y agrega cada lugar
              que cumpla las restricciones, asi que TODO individuo produce un itinerario valido
              (restricciones manejadas por construccion, sin penalizaciones).
  Fitness     fitness.fitness(ruta, perfil)
  Seleccion   torneo de 3
  Cruce       de orden (OX), probabilidad 0.9
  Mutacion    intercambio (0.4) y movimiento de un lugar (0.4)
  Elitismo    los 2 mejores pasan intactos
"""
import random
import time

from app.fitness import fitness                                         # noqa: F401 (re-export)
from app.itinerario import construir_desde_candidatos, construir_pool, resumen
from app.restricciones import (EstadoDia, preparar_candidatos, revisar_parada, agregar_parada,
                               validar_itinerario)

POBLACION = 60
GENERACIONES = 80
SEMILLA_ALEATORIA = 42


def preparar(pool, perfil, usar_horarios_osm=True):
    """Convierte el pool (DataFrame) en candidatos, igual que hace el voraz."""
    return preparar_candidatos(pool, perfil, usar_horarios_osm)


def simular(orden, filas, perfil):
    """Recorre los lugares en el orden dado y se queda con los que caben en el dia."""
    estado = EstadoDia(perfil)
    for i in orden:
        c = filas[i]
        datos, _ = revisar_parada(estado, c, perfil)
        if datos is not None:
            agregar_parada(estado, c, datos)
    return estado.ruta


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


def genetico(filas, perfil, semilla=None, poblacion=POBLACION, generaciones=GENERACIONES,
             seed=SEMILLA_ALEATORIA):
    """Devuelve (ruta, fitness, historial).

    `semilla` es opcional: un orden inicial (por ejemplo, la ruta del voraz) que se agrega a la
    poblacion. `seed` es la semilla del generador aleatorio: misma seed + mismos datos = mismo
    resultado."""
    rnd = random.Random(seed)
    n = len(filas)
    base = list(range(n))
    if n < 2:                                   # nada que combinar
        ruta = simular(base, filas, perfil)
        return ruta, fitness(ruta, perfil), [round(fitness(ruta, perfil), 3)]
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
        cand = rnd.sample(range(len(pob)), min(3, len(pob)))
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


def _resultado(ruta, perfil, df, segundos, historial=None):
    res = {"ruta": ruta, "fitness": fitness(ruta, perfil), "seg": segundos,
           "resumen": resumen(ruta), "violaciones": validar_itinerario(ruta, perfil, df)}
    if historial is not None:
        res["historial"] = historial
    return res


def comparar(df, perfil, generaciones=GENERACIONES, poblacion=POBLACION, con_semilla=True,
             seed=SEMILLA_ALEATORIA, usar_horarios_osm=True, pesos=None):
    """Corre voraz y genetico sobre los mismos candidatos y restricciones.

    con_semilla=True agrega la ruta del voraz a la poblacion inicial (el genetico no puede
    quedar peor que el voraz). Para una comparacion justa del algoritmo en si, usar
    con_semilla=False. Devuelve None si ningun lugar pasa los filtros del perfil."""
    pool = construir_pool(df, perfil, pesos)
    if pool.empty:
        return None
    filas = preparar(pool, perfil, usar_horarios_osm)

    t0 = time.perf_counter()
    ruta_g = construir_desde_candidatos(filas, perfil)
    res_g = _resultado(ruta_g, perfil, df, time.perf_counter() - t0)

    pos = {f["id"]: i for i, f in enumerate(filas)}
    semilla = [pos[p["id"]] for p in ruta_g] if (con_semilla and ruta_g) else None
    t0 = time.perf_counter()
    ruta_ga, _, hist = genetico(filas, perfil, semilla, poblacion, generaciones, seed)
    res_ga = _resultado(ruta_ga, perfil, df, time.perf_counter() - t0, hist)
    return {"greedy": res_g, "genetico": res_ga}


def generar_itinerario_genetico(df, perfil, seed=SEMILLA_ALEATORIA, con_semilla=True):
    """Devuelve el itinerario del genetico con el mismo formato que el voraz."""
    r = comparar(df, perfil, con_semilla=con_semilla, seed=seed)
    if r is None:
        return {"paradas": [], "resumen": resumen([])}
    g = r["genetico"]
    return {"paradas": g["ruta"], "resumen": g["resumen"]}
