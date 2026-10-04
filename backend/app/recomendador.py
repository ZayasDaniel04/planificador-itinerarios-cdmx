import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from app.perfiles import vector_lugar
from app.reglas import pasa_filtros, ajuste_reglas

# Pesos del puntaje final (se pueden ajustar y comparar en la evaluacion)
W_SIM = 0.60
W_REGLAS = 0.25
W_POP = 0.10
W_PRECIO = 0.15


def cargar_lugares(ruta="../data/lugares_limpio.csv"):
    return pd.read_csv(ruta)


def recomendar(df, perfil, n=15, max_por_categoria=3):
    """Devuelve los n mejores lugares para el perfil, con su puntaje."""
    mascara = df.apply(lambda r: pasa_filtros(r, perfil), axis=1)
    validos = df[mascara].copy()
    if validos.empty:
        return validos

    # 1. Similitud coseno usuario vs lugar
    vu = np.array([perfil.vector()])
    vl = np.array([vector_lugar(c) for c in validos["categoria"]])
    if vu.sum() == 0:
        sim = np.zeros(len(validos))
    else:
        sim = cosine_similarity(vu, vl)[0]

    # 2. Ajuste por reglas de grupo
    reglas = np.array([ajuste_reglas(r, perfil) for _, r in validos.iterrows()])

    # 3. Popularidad aproximada
    pop = validos["sitio_web"].notna().astype(float).to_numpy()

    # 4. Costo relativo al presupuesto
    precio = np.clip(validos["costo_estimado"] / perfil.presupuesto_por_persona, 0, 1).to_numpy()

    validos["puntaje"] = W_SIM * sim + W_REGLAS * reglas + W_POP * pop - W_PRECIO * precio
    validos = validos.sort_values("puntaje", ascending=False)

    # Diversidad: maximo N lugares por categoria
    elegidos, conteo = [], {}
    for idx, fila in validos.iterrows():
        c = fila["categoria"]
        if conteo.get(c, 0) < max_por_categoria:
            elegidos.append(idx)
            conteo[c] = conteo.get(c, 0) + 1
        if len(elegidos) == n:
            break
    return validos.loc[elegidos]
