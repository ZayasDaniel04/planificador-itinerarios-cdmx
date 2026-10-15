import re
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

    def validar(self):
        """Devuelve la lista de problemas del perfil (vacia = perfil valido)."""
        from app.calidad_datos import ZONAS
        from app.horarios import indice_dia
        errores = []
        if self.tipo_grupo not in TIPOS_GRUPO:
            errores.append(f"tipo_grupo debe ser uno de {TIPOS_GRUPO}")
        if self.personas < 1:
            errores.append("personas debe ser al menos 1")
        if self.presupuesto_por_persona < 0:
            errores.append("presupuesto_por_persona no puede ser negativo")
        if self.nivel_actividad not in (1, 2, 3):
            errores.append("nivel_actividad debe ser 1, 2 o 3")
        horas = {}
        for campo in ("hora_inicio", "hora_fin"):
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(getattr(self, campo)))
            if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                errores.append(f"{campo} debe tener formato HH:MM (00:00 a 23:59)")
            else:
                horas[campo] = int(m.group(1)) * 60 + int(m.group(2))
        if len(horas) == 2 and horas["hora_fin"] <= horas["hora_inicio"]:
            errores.append("hora_fin debe ser posterior a hora_inicio")
        if self.dia_semana and indice_dia(self.dia_semana) is None:
            errores.append("dia_semana debe ser lunes, martes, miercoles, jueves, viernes, sabado o domingo")
        if self.zona and self.zona not in ZONAS:
            errores.append(f"zona debe estar vacia o ser una de {list(ZONAS)}")
        for interes, peso in self.intereses.items():
            if interes not in INTERESES:
                errores.append(f"interes desconocido: {interes!r} (validos: {INTERESES})")
            elif not 0 <= peso <= 1:
                errores.append(f"el peso del interes {interes!r} debe estar entre 0 y 1")
        return errores


def vector_lugar(categoria):
    """Vector del lugar en el orden de INTERESES, segun su categoria."""
    pesos = PERFIL_CATEGORIA.get(categoria, {})
    return [pesos.get(i, 0.0) for i in INTERESES]
