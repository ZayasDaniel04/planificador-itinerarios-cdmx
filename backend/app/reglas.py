"""Sistema experto: reglas por tipo de grupo."""

# Bono (+) o penalizacion (-) al puntaje segun grupo y categoria
AJUSTE_GRUPO = {
    "familia": {
        "parque": 0.30, "zoologico": 0.40, "museo": 0.15, "jardin": 0.20,
        "mercado": 0.10, "atraccion": 0.10, "cine": 0.10,
        "bar": -1.0, "teatro": -0.05,
    },
    "pareja": {
        "mirador": 0.35, "jardin": 0.25, "cafeteria": 0.20, "teatro": 0.25,
        "galeria": 0.20, "restaurante": 0.15, "bar": 0.10,
        "zoologico": -0.15, "centro_comercial": -0.10,
    },
    "amigos": {
        "mercado": 0.25, "bar": 0.25, "atraccion": 0.10, "restaurante": 0.10,
        "cafeteria": 0.05, "libreria": -0.05, "galeria": -0.05,
    },
    "solo": {
        "cafeteria": 0.20, "libreria": 0.25, "museo": 0.15, "parque": 0.10,
        "galeria": 0.15, "mirador": 0.10, "bar": -0.10, "zoologico": -0.10,
    },
}

# Ambientes que "encajan" con cada grupo (suma un pequeno bono)
AMBIENTE_GRUPO = {
    "familia": {"familiar", "naturaleza", "cultural"},
    "pareja":  {"romantico", "tranquilo"},
    "amigos":  {"animado", "nocturno", "turistico"},
    "solo":    {"tranquilo", "cultural"},
}


def pasa_filtros(lugar, perfil):
    """Filtros duros: devuelve False si el lugar NO es apropiado."""
    if perfil.hay_ninos:
        if lugar["apto_ninos"] == 0 or lugar["categoria"] == "bar":
            return False
    if perfil.hay_adultos_mayores:
        if lugar["apto_adultos_mayores"] == 0:
            return False
        if lugar["nivel_actividad"] > 2:
            return False
    if perfil.tipo_grupo == "familia" and lugar["categoria"] == "bar":
        return False
    # nivel de actividad: no mandar caminatas largas a quien pidio poca
    if lugar["nivel_actividad"] > perfil.nivel_actividad + 1:
        return False
    # presupuesto: un solo lugar no puede gastarse todo el presupuesto
    limite = 0.8 if lugar["es_comida"] == 1 else 0.6
    if lugar["costo_estimado"] > perfil.presupuesto_por_persona * limite:
        return False
    # zona
    if perfil.zona and lugar["zona"] != perfil.zona:
        return False
    # dia cerrado
    cerrado = str(lugar.get("dias_cerrado", "") or "")
    if perfil.dia_semana and perfil.dia_semana in cerrado:
        return False
    return True


def ajuste_reglas(lugar, perfil):
    """Bono o penalizacion total por reglas de grupo y ambiente."""
    ajuste = AJUSTE_GRUPO.get(perfil.tipo_grupo, {}).get(lugar["categoria"], 0.0)
    ambientes = set(str(lugar.get("ambiente", "")).split("|"))
    if ambientes & AMBIENTE_GRUPO.get(perfil.tipo_grupo, set()):
        ajuste += 0.10
    return ajuste
