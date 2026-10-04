from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.perfiles import Perfil
from app.recomendador import cargar_lugares, recomendar

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


@app.get("/")
def inicio():
    return {"mensaje": "API del planificador funcionando", "lugares": len(LUGARES)}


@app.post("/recomendar")
def api_recomendar(p: PerfilEntrada):
    datos = p.model_dump()
    n = datos.pop("n")
    perfil = Perfil(**datos)
    top = recomendar(LUGARES, perfil, n=n)
    columnas = ["id", "nombre", "categoria", "zona", "lat", "lon", "ambiente",
                "duracion_min", "costo_estimado", "puntaje"]
    top = top[columnas].round(3).fillna("")
    return {"total": len(top), "lugares": top.to_dict(orient="records")}


from app.itinerario import generar_itinerario


class PerfilItinerario(PerfilEntrada):
    hora_inicio: str = "10:00"
    hora_fin: str = "20:00"


@app.post("/itinerario")
def api_itinerario(p: PerfilItinerario):
    datos = p.model_dump()
    datos.pop("n")
    perfil = Perfil(**datos)
    return generar_itinerario(LUGARES, perfil)
