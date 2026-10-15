from typing import Dict, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.genetico import generar_itinerario_genetico
from app.itinerario import generar_itinerario, construir_pool, resumen
from app.perfiles import Perfil
from app.recomendador import cargar_lugares, recomendar
from app.restricciones import validar_itinerario

app = FastAPI(title="Planificador de itinerarios CDMX")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

LUGARES = cargar_lugares()


class PerfilEntrada(BaseModel):
    tipo_grupo: str = "amigos"
    personas: int = 2
    hay_ninos: bool = False
    hay_adultos_mayores: bool = False
    presupuesto_por_persona: float = 500
    nivel_actividad: int = 2
    zona: str = ""
    dia_semana: str = "sabado"
    intereses: Dict[str, float] = {}
    n: int = 10


def _perfil_valido(datos):
    """Crea el Perfil y responde 422 con la lista de problemas si algo no tiene sentido."""
    perfil = Perfil(**datos)
    errores = perfil.validar()
    if errores:
        raise HTTPException(status_code=422, detail=errores)
    return perfil


@app.get("/")
def inicio():
    return {"mensaje": "API del planificador funcionando", "lugares": len(LUGARES)}


@app.post("/recomendar")
def api_recomendar(p: PerfilEntrada):
    datos = p.model_dump()
    n = datos.pop("n")
    perfil = _perfil_valido(datos)
    top = recomendar(LUGARES, perfil, n=n)
    if top.empty:
        return {"total": 0, "lugares": []}
    columnas = ["id", "nombre", "categoria", "zona", "lat", "lon", "ambiente",
                "duracion_min", "costo_estimado", "puntaje",
                "sim", "ajuste", "confianza", "precio_rel"]     # los 4 ultimos explican el puntaje
    top = top[columnas].round(3).fillna("")
    return {"total": len(top), "lugares": top.to_dict(orient="records")}


class PerfilItinerario(PerfilEntrada):
    hora_inicio: str = "10:00"
    hora_fin: str = "20:00"
    algoritmo: Literal["greedy", "genetico"] = "greedy"
    semilla: int = 42          # solo afecta al genetico: misma semilla = mismo itinerario


@app.post("/itinerario")
def api_itinerario(p: PerfilItinerario):
    datos = p.model_dump()
    datos.pop("n")
    algoritmo = datos.pop("algoritmo")
    semilla = datos.pop("semilla")
    perfil = _perfil_valido(datos)

    if algoritmo == "genetico":
        it = generar_itinerario_genetico(LUGARES, perfil, seed=semilla)
    else:
        it = generar_itinerario(LUGARES, perfil)

    # Toda respuesta se revisa de forma independiente antes de entregarse
    violaciones = validar_itinerario(it["paradas"], perfil, LUGARES)
    mensaje = ""
    if not it["paradas"]:
        hay_candidatos = not construir_pool(LUGARES, perfil).empty
        mensaje = ("Hay lugares compatibles con el perfil, pero ninguno cabe en el horario y el "
                   "presupuesto indicados." if hay_candidatos else
                   "Ningun lugar cumple los filtros del perfil (zona, ninos, adultos mayores, "
                   "nivel de actividad, presupuesto o dia).")
        it["resumen"] = resumen([])
    it.update({"algoritmo": algoritmo, "valido": not violaciones,
               "violaciones": violaciones, "mensaje": mensaje})
    return it
