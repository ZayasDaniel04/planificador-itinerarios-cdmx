from dataclasses import dataclass, field

# Ejes de preferencia: cada lugar y cada usuario se describen con estos 8 intereses
INTERESES = ["cultura", "comida", "naturaleza", "vida_nocturna",
             "compras", "arte", "historia", "fotografia"]

TIPOS_GRUPO = ["solo", "pareja", "amigos", "familia"]

# Interes que dispara cada categoria de lugar (peso de 0 a 1 por interes)
PERFIL_CATEGORIA = {
    "museo":            {"cultura": 1.0, "historia": 0.7, "arte": 0.4},
    "galeria":          {"arte": 1.0, "cultura": 0.6, "fotografia": 0.4},
    "atraccion":        {"historia": 0.6, "fotografia": 0.8, "cultura": 0.4},
    "mirador":          {"fotografia": 1.0, "naturaleza": 0.4},
    "zoologico":        {"naturaleza": 1.0, "fotografia": 0.4},
    "parque":           {"naturaleza": 1.0, "fotografia": 0.3},
    "jardin":           {"naturaleza": 0.9, "fotografia": 0.6},
    "restaurante":      {"comida": 1.0},
    "cafeteria":        {"comida": 0.6, "cultura": 0.2},
    "bar":              {"vida_nocturna": 1.0, "comida": 0.3},
    "mercado":          {"comida": 0.8, "compras": 0.8, "cultura": 0.3},
    "teatro":           {"cultura": 0.9, "arte": 0.9},
    "cine":             {"cultura": 0.4, "arte": 0.3},
    "libreria":         {"cultura": 0.7, "compras": 0.4, "arte": 0.2},
    "centro_comercial": {"compras": 1.0},
}


@dataclass
class Perfil:
    tipo_grupo: str = "amigos"
    personas: int = 2
    hay_ninos: bool = False
    hay_adultos_mayores: bool = False
    presupuesto_por_persona: float = 500.0   # MXN para todo el dia
    hora_inicio: str = "10:00"
    hora_fin: str = "20:00"
    nivel_actividad: int = 2                 # 1 poca caminata, 3 mucha
    zona: str = ""                           # vacio = cualquier zona
    dia_semana: str = "sabado"
    intereses: dict = field(default_factory=dict)   # {"cultura": 0.9, ...}

    def vector(self):
        """Vector del usuario en el orden de INTERESES."""
        return [float(self.intereses.get(i, 0.0)) for i in INTERESES]


def vector_lugar(categoria):
    """Vector del lugar en el orden de INTERESES, segun su categoria."""
    pesos = PERFIL_CATEGORIA.get(categoria, {})
    return [pesos.get(i, 0.0) for i in INTERESES]
