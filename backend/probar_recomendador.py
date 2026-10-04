import pandas as pd
from app.perfiles import Perfil
from app.recomendador import cargar_lugares, recomendar

df = cargar_lugares()

ejemplos = {
    "Familia con ninos": Perfil(tipo_grupo="familia", personas=4, hay_ninos=True,
                                presupuesto_por_persona=400, nivel_actividad=2,
                                intereses={"naturaleza": 0.9, "cultura": 0.6, "comida": 0.7}),
    "Pareja romantica": Perfil(tipo_grupo="pareja", personas=2,
                               presupuesto_por_persona=800, nivel_actividad=1,
                               intereses={"comida": 0.9, "arte": 0.7, "fotografia": 0.6}),
    "Amigos de fiesta": Perfil(tipo_grupo="amigos", personas=4,
                               presupuesto_por_persona=600, nivel_actividad=3,
                               intereses={"vida_nocturna": 1.0, "comida": 0.8}),
}

for nombre, perfil in ejemplos.items():
    top = recomendar(df, perfil, n=10)
    print(f"\n=== {nombre} ===")
    print(top[["nombre", "categoria", "zona", "puntaje"]].round(2).to_string(index=False))
