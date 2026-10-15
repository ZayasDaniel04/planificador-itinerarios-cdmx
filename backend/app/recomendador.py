"""Motor de recomendacion basado en contenido + reglas.

    puntaje = W_similitud * similitud_coseno(usuario, lugar)
            + W_reglas    * ajuste_reglas(grupo, categoria, ambiente)
            + W_confianza * confianza_datos(lugar)
            + W_fama      * fama(lugar)               (solo si el dataset trae la columna `fama`)
            - W_precio    * costo_relativo(lugar)

Que mide cada termino (y que NO mide):
  similitud     Coseno entre el vector de intereses del usuario y el vector de la CATEGORIA del
                lugar (8 ejes). Todos los lugares de una categoria tienen la misma similitud:
                mide el encaje tematico, no la calidad de un lugar concreto.
  reglas        Sistema experto (app/reglas.py): bonos y penalizaciones por tipo de grupo.
  confianza     Que tan VERIFICABLE es la informacion del lugar (ver confianza_datos). Antes se
                usaba "tiene sitio web" como si fuera popularidad, pero un sitio web no indica
                cuanta gente visita o aprecia un lugar. OSM no trae ratings ni visitas, asi que
                la popularidad real NO se mide.
  fama          Popularidad real (1 a 5), solo si alguien agrega la columna `fama` al CSV (por
                ejemplo, calificaciones de Google Maps o una encuesta). Si no existe, se ignora.
  precio        costo_estimado / presupuesto, recortado a [0, 1]. Penaliza lo caro.

Los pesos estan en PESOS_POR_DEFECTO y se pueden cambiar por llamada (`pesos=`) para medir su
efecto; ver evaluar_pesos.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from app.horarios import parsear_horario_osm
from app.perfiles import vector_lugar
from app.reglas import pasa_filtros, ajuste_reglas

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data" / "lugares_limpio.csv"

# Pesos del puntaje final (se pueden ajustar y comparar en la evaluacion)
PESOS_POR_DEFECTO = {
    "similitud": 0.60,
    "reglas": 0.25,
    "confianza": 0.10,
    "fama": 0.10,        # solo actua si el dataset tiene la columna `fama`
    "precio": 0.15,      # se RESTA
}
# Nombres anteriores, por compatibilidad con codigo que los importe
W_SIM = PESOS_POR_DEFECTO["similitud"]
W_REGLAS = PESOS_POR_DEFECTO["reglas"]
W_PRECIO = PESOS_POR_DEFECTO["precio"]


def cargar_lugares(ruta=None):
    """Carga el CSV de lugares. Si trae la columna `usable`, descarta los marcados con 0
    (coordenadas invalidas o duplicados exactos detectados por mejorar_dataset.py)."""
    df = pd.read_csv(ruta or RUTA_DATOS)
    if "usable" in df.columns:
        df = df[df["usable"].fillna(1).astype(int) == 1].reset_index(drop=True)
    return df


def resolver_pesos(pesos=None):
    """Mezcla los pesos pedidos con los de por defecto y valida que sean correctos."""
    final = dict(PESOS_POR_DEFECTO)
    for clave, valor in (pesos or {}).items():
        if clave not in PESOS_POR_DEFECTO:
            raise ValueError(f"Peso desconocido: {clave!r}. Validos: {sorted(PESOS_POR_DEFECTO)}")
        if valor < 0:
            raise ValueError(f"El peso {clave!r} no puede ser negativo (se resta solo el de precio)")
        final[clave] = float(valor)
    return final


def confianza_datos(df):
    """Que tan verificable es la informacion de cada lugar, de 0 a 1.

        0.50  si su horario real de OSM se pudo interpretar (no hay que adivinar cuando abre)
        0.25  si tiene sitio web (hay una fuente externa para confirmar datos)
        0.25  si trae un dato extra de OSM: tipo de comida (comida) o etiqueta de costo (resto)

    NO es popularidad ni calidad: solo indica cuanto del itinerario descansa en datos reales
    y no en estimaciones por categoria."""
    horario = df["horario_osm"] if "horario_osm" in df else pd.Series(None, index=df.index)
    tiene_horario = horario.map(lambda t: parsear_horario_osm(t) is not None).astype(float)
    web = (df["sitio_web"].notna().astype(float) if "sitio_web" in df
           else pd.Series(0.0, index=df.index))
    cocina = (df["tipo_comida"].notna() if "tipo_comida" in df
              else pd.Series(False, index=df.index))
    costo_osm = (df["costo_osm"].notna() if "costo_osm" in df
                 else pd.Series(False, index=df.index))
    es_comida = (df["es_comida"] == 1) if "es_comida" in df else pd.Series(False, index=df.index)
    extra = np.where(es_comida, cocina, costo_osm).astype(float)
    return (0.50 * tiene_horario + 0.25 * web + 0.25 * extra).to_numpy()


def _fama_normalizada(validos):
    """Fama de 1 a 5 llevada a [0, 1]. Si falta en algunos lugares se usa el promedio de los que
    la tienen. Devuelve None si el dataset no trae la columna (el termino no se aplica)."""
    if "fama" not in validos or validos["fama"].notna().sum() == 0:
        return None
    f = ((validos["fama"].astype(float) - 1) / 4).clip(0, 1)
    return f.fillna(f.mean()).to_numpy()


def puntuar(df, perfil, pesos=None):
    """Filtra con las reglas duras y calcula el puntaje de cada lugar. Devuelve el DataFrame
    ordenado de mayor a menor puntaje, con las columnas de cada componente (sim, ajuste,
    confianza, fama, precio_rel) para poder explicar la recomendacion."""
    w = resolver_pesos(pesos)
    mascara = df.apply(lambda r: pasa_filtros(r, perfil), axis=1)
    validos = df[mascara].copy()
    if validos.empty:
        return validos

    # 1. Similitud coseno usuario vs categoria del lugar
    vu = np.array([perfil.vector()])
    vl = np.array([vector_lugar(c) for c in validos["categoria"]])
    sim = np.zeros(len(validos)) if vu.sum() == 0 else cosine_similarity(vu, vl)[0]

    # 2. Ajuste por reglas de grupo
    ajuste = np.array([ajuste_reglas(r, perfil) for _, r in validos.iterrows()])

    # 3. Confianza de los datos (NO es popularidad)
    confianza = confianza_datos(validos)

    # 4. Fama real, solo si el dataset la trae
    fama = _fama_normalizada(validos)

    # 5. Costo relativo al presupuesto
    presupuesto = max(float(perfil.presupuesto_por_persona), 1e-9)
    precio = np.clip(validos["costo_estimado"] / presupuesto, 0, 1).to_numpy()

    puntaje = (w["similitud"] * sim + w["reglas"] * ajuste + w["confianza"] * confianza
               - w["precio"] * precio)
    if fama is not None:
        puntaje = puntaje + w["fama"] * fama
        validos["fama_norm"] = fama
    validos["sim"] = sim
    validos["ajuste"] = ajuste
    validos["confianza"] = confianza
    validos["precio_rel"] = precio
    validos["puntaje"] = puntaje
    # desempate estable por id: el mismo perfil siempre da el mismo orden (reproducibilidad)
    return validos.sort_values(["puntaje", "id"], ascending=[False, True], kind="stable")


def seleccionar_diverso(validos, n, max_por_categoria):
    """Toma los n mejores de un DataFrame ya ordenado por puntaje, con maximo
    `max_por_categoria` lugares de cada categoria (diversidad)."""
    elegidos, conteo = [], {}
    for idx, fila in validos.iterrows():
        c = fila["categoria"]
        if conteo.get(c, 0) < max_por_categoria:
            elegidos.append(idx)
            conteo[c] = conteo.get(c, 0) + 1
        if len(elegidos) == n:
            break
    return validos.loc[elegidos]


def recomendar(df, perfil, n=15, max_por_categoria=3, pesos=None):
    """Devuelve los n mejores lugares para el perfil, con su puntaje."""
    validos = puntuar(df, perfil, pesos)
    if validos.empty:
        return validos
    return seleccionar_diverso(validos, n, max_por_categoria)
