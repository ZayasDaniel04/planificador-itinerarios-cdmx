import pandas as pd
from app.perfiles import Perfil, vector_lugar
from app.reglas import pasa_filtros, ajuste_reglas

df = pd.read_csv("../data/lugares_limpio.csv")
print("Lugares totales:", len(df))

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
    validos = [r for _, r in df.iterrows() if pasa_filtros(r, perfil)]
    print(f"\n{nombre}: {len(validos)} lugares pasan los filtros")
    cats = pd.Series([r["categoria"] for r in validos]).value_counts().head(6)
    print(cats.to_string())

# Vector de ejemplo
print("\nVector de un museo:", vector_lugar("museo"))
