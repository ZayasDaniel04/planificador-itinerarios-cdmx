"""Genera data/lugares_limpio.csv desde el crudo de OpenStreetMap (data/lugares_raw.csv).

CUIDADO: este script regenera el CSV desde cero y BORRARIA las correcciones manuales
(lugares eliminados, costos editados...). Por eso se niega a sobrescribir un CSV que ya
existe, salvo que se use --forzar. Para mejorar el dataset actual usa mejorar_dataset.py.

Uso (desde backend/):
    python limpiar_dataset.py --salida ../data/prueba.csv     # genera en otro archivo
    python limpiar_dataset.py --forzar                        # sobrescribe lugares_limpio.csv
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from app.calidad_datos import (COLUMNAS_DEFECTO, DEFECTOS_CATEGORIA, ZONAS, asignar_zona,
                               motivo_coordenada_invalida)

DATOS = Path(__file__).resolve().parents[1] / "data"

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--salida", default=str(DATOS / "lugares_limpio.csv"))
ap.add_argument("--forzar", action="store_true", help="permite sobrescribir un CSV existente")
args = ap.parse_args()
salida = Path(args.salida)
if salida.exists() and not args.forzar:
    sys.exit(f"{salida} ya existe y puede tener correcciones manuales. "
             "Usa --salida otro.csv para generar aparte, o --forzar si de verdad quieres sobrescribirlo.")

df = pd.read_csv(DATOS / "lugares_raw.csv")
print("Lugares crudos:", len(df))

# ---------- 1. LIMPIEZA ----------
df = df.dropna(subset=["nombre", "lat", "lon"])
df["nombre"] = df["nombre"].str.strip()
df = df[df["nombre"] != ""]
# coordenadas invalidas (vacias, en cero, invertidas o lejos de la zona de estudio)
invalidas = [bool(motivo_coordenada_invalida(a, b)) for a, b in zip(df["lat"], df["lon"])]
print("Descartados por coordenadas invalidas:", sum(invalidas))
df = df[[not x for x in invalidas]]
# una sola sucursal por nombre y categoria (decision de diseno: evita que cadenas como Starbucks
# llenen los cupos; las demas sucursales se descartan a proposito)
df["nombre_min"] = df["nombre"].str.lower()
antes = len(df)
df = df.drop_duplicates(subset=["nombre_min", "categoria"])
print("Descartados por repetir nombre y categoria:", antes - len(df))

# ---------- 2. SELECCION ----------
# prioriza los lugares con mas datos reales en OSM (sitio web, horario, tipo de cocina, costo)
df["puntos"] = (
    df["sitio_web"].notna() * 2
    + df["horario"].notna() * 2
    + df["cocina"].notna() * 1
    + df["costo_osm"].notna() * 1
)

CUPOS = {
    "restaurante": 60, "cafeteria": 40, "museo": 40, "atraccion": 30,
    "parque": 25, "bar": 25, "mercado": 15, "teatro": 12, "jardin": 10,
    "libreria": 10, "centro_comercial": 8, "mirador": 8, "galeria": 7,
    "cine": 6, "zoologico": 6,
}

df = df.sample(frac=1, random_state=42)  # desempata al azar
partes = []
for cat, cupo in CUPOS.items():
    sub = df[df["categoria"] == cat].sort_values("puntos", ascending=False, kind="stable")
    partes.append(sub.head(cupo))
df = pd.concat(partes)

# ---------- 3. ENRIQUECIMIENTO ----------
# Zona = la mas cercana de las 5 (ver ZONAS en app/calidad_datos.py)
df["zona"] = [asignar_zona(a, b) for a, b in zip(df["lat"], df["lon"])]

# duracion_min, costo_estimado, nivel_actividad, apto_*, horas, ambiente... son VALORES POR
# DEFECTO DE LA CATEGORIA (ver DEFECTOS_CATEGORIA): estimaciones, no datos de OSM.
for i, col in enumerate(COLUMNAS_DEFECTO):
    df[col] = df["categoria"].map(lambda c: DEFECTOS_CATEGORIA[c][i])

df = df.rename(columns={"cocina": "tipo_comida", "horario": "horario_osm"})
df = df.sort_values(["categoria", "zona", "nombre"]).reset_index(drop=True)
df.insert(0, "id", df.index + 1)

columnas = ["id", "nombre", "categoria", "zona", "lat", "lon", "ambiente",
            "duracion_min", "costo_estimado", "precio_nivel", "nivel_actividad",
            "apto_ninos", "apto_adultos_mayores", "es_comida", "tipo_comida",
            "hora_apertura", "hora_cierre", "dias_cerrado", "horario_osm", "sitio_web"]
df[columnas].to_csv(salida, index=False, encoding="utf-8-sig")

print("Lugares seleccionados:", len(df), "->", salida)
print("\nPor zona:")
print(df["zona"].value_counts())
print("\nPor categoria:")
print(df["categoria"].value_counts())
print("\nSiguiente paso: python mejorar_dataset.py (agrega procedencia y calidad).")
