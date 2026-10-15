"""Funcion fitness: la misma para el voraz y el genetico, de modo que se comparen con justicia.

    fitness = sum(puntaje de cada lugar)                      (que tan bien encaja cada lugar)
              - PESO_TRASLADO   * minutos de traslado         (menos camino es mejor)
              - PESO_ESPERA     * minutos de espera           (esperar a que abra es tiempo perdido)
              + BONO_COMIDA                                   (si el dia incluye comida fuerte)
              - PENA_REPETICION * pares seguidos de la misma categoria   (variedad)
              + BONO_BAR_NOCTURNO                             (si el grupo quiere vida nocturna,
                                                               el dia termina tarde y hay un bar)

El fitness es una metrica PROPIA del sistema, no una medida de satisfaccion real de las personas:
que un algoritmo la optimice mejor no prueba por si solo que sus itinerarios gusten mas.
Un itinerario vacio vale -1e9 (invalido). Los itinerarios que incumplen restricciones duras no
deberian existir: la validez se comprueba aparte con restricciones.validar_itinerario().
"""
from app.horarios import a_min
from app.restricciones import COMIDA_FUERTE

PESO_TRASLADO = 0.01
PESO_ESPERA = 0.005
BONO_COMIDA = 0.5
PENA_REPETICION = 0.15
BONO_BAR_NOCTURNO = 0.4
FITNESS_INVALIDO = -1e9


def es_nocturno(perfil):
    """El grupo pide vida nocturna (interes >= 0.5) y el dia termina a las 21:00 o despues."""
    return perfil.intereses.get("vida_nocturna", 0) >= 0.5 and a_min(perfil.hora_fin) >= 21 * 60


def desglose_fitness(ruta, perfil):
    """Devuelve cada termino del fitness por separado (util para explicar y depurar)."""
    if not ruta:
        return {"puntajes": 0.0, "traslado": 0.0, "espera": 0.0, "comida": 0.0,
                "repeticion": 0.0, "bar_nocturno": 0.0, "total": FITNESS_INVALIDO}
    puntajes = sum(p["puntaje"] for p in ruta)
    traslado = -PESO_TRASLADO * sum(p["traslado_min"] for p in ruta)
    espera = -PESO_ESPERA * sum(p["espera_min"] for p in ruta)
    comida = BONO_COMIDA if any(p["categoria"] in COMIDA_FUERTE for p in ruta) else 0.0
    repeticion = -PENA_REPETICION * sum(1 for a, b in zip(ruta, ruta[1:])
                                        if a["categoria"] == b["categoria"])
    bar = BONO_BAR_NOCTURNO if es_nocturno(perfil) and any(p["categoria"] == "bar" for p in ruta) else 0.0
    total = puntajes + traslado + espera + comida + repeticion + bar
    return {"puntajes": puntajes, "traslado": traslado, "espera": espera, "comida": comida,
            "repeticion": repeticion, "bar_nocturno": bar, "total": total}


def fitness(ruta, perfil):
    """Calidad de un itinerario (mayor es mejor)."""
    if not ruta:
        return FITNESS_INVALIDO
    f = sum(p["puntaje"] for p in ruta)
    f -= PESO_TRASLADO * sum(p["traslado_min"] for p in ruta)
    f -= PESO_ESPERA * sum(p["espera_min"] for p in ruta)
    if any(p["categoria"] in COMIDA_FUERTE for p in ruta):
        f += BONO_COMIDA
    for a, b in zip(ruta, ruta[1:]):
        if a["categoria"] == b["categoria"]:
            f -= PENA_REPETICION
    if es_nocturno(perfil) and any(p["categoria"] == "bar" for p in ruta):
        f += BONO_BAR_NOCTURNO
    return f
