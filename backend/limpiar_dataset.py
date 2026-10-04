import pandas as pd

df = pd.read_csv("../data/lugares_raw.csv")
print("Lugares crudos:", len(df))

# ---------- 1. LIMPIEZA ----------
df = df.dropna(subset=["nombre", "lat", "lon"])
df["nombre"] = df["nombre"].str.strip()
df["nombre_min"] = df["nombre"].str.lower()
df = df.drop_duplicates(subset=["nombre_min", "categoria"])

# ---------- 2. SELECCION ----------
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
ZONAS = {
    "Centro Historico": (19.4326, -99.1332),
    "Roma-Condesa": (19.4120, -99.1700),
    "Polanco-Chapultepec": (19.4250, -99.1900),
    "Coyoacan": (19.3500, -99.1620),
    "San Angel": (19.3470, -99.1900),
}

def zona(lat, lon):
    return min(ZONAS, key=lambda z: (lat - ZONAS[z][0]) ** 2 + (lon - ZONAS[z][1]) ** 2)

df["zona"] = [zona(a, b) for a, b in zip(df["lat"], df["lon"])]

# duracion_min, costo_estimado (MXN por persona), precio_nivel (1-4),
# nivel_actividad (1-3), apto_ninos, apto_adultos_mayores, es_comida,
# hora_apertura, hora_cierre, dias_cerrado, ambiente
COLS = ["duracion_min", "costo_estimado", "precio_nivel", "nivel_actividad",
        "apto_ninos", "apto_adultos_mayores", "es_comida",
        "hora_apertura", "hora_cierre", "dias_cerrado", "ambiente"]

DEF = {
    "museo":            [90, 80, 2, 1, 1, 1, 0, "10:00", "17:00", "lunes", "cultural|tranquilo"],
    "galeria":          [45, 0, 1, 1, 0, 1, 0, "11:00", "18:00", "lunes", "cultural|tranquilo|romantico"],
    "atraccion":        [60, 50, 2, 2, 1, 1, 0, "09:00", "19:00", "", "turistico|animado"],
    "mirador":          [40, 0, 1, 1, 1, 1, 0, "09:00", "21:00", "", "romantico|tranquilo"],
    "zoologico":        [180, 50, 1, 3, 1, 0, 0, "09:00", "17:00", "lunes", "familiar|naturaleza"],
    "parque":           [60, 0, 1, 2, 1, 1, 0, "06:00", "18:00", "", "naturaleza|tranquilo|familiar"],
    "jardin":           [45, 0, 1, 1, 1, 1, 0, "08:00", "18:00", "", "naturaleza|tranquilo|romantico"],
    "restaurante":      [75, 250, 3, 1, 1, 1, 1, "09:00", "23:00", "", "animado|familiar"],
    "cafeteria":        [45, 100, 2, 1, 1, 1, 1, "08:00", "21:00", "", "tranquilo|romantico"],
    "bar":              [90, 250, 3, 1, 0, 0, 1, "17:00", "23:59", "", "animado|nocturno"],
    "mercado":          [60, 120, 1, 2, 1, 1, 1, "08:00", "18:00", "", "animado|turistico|familiar"],
    "teatro":           [120, 300, 3, 1, 1, 1, 0, "17:00", "22:00", "lunes", "cultural|romantico"],
    "cine":             [120, 90, 2, 1, 1, 1, 0, "12:00", "23:00", "", "tranquilo|familiar"],
    "libreria":         [40, 0, 1, 1, 1, 1, 0, "10:00", "20:00", "", "tranquilo|cultural"],
    "centro_comercial": [90, 150, 2, 2, 1, 1, 0, "11:00", "20:00", "", "animado|familiar"],
}

for i, col in enumerate(COLS):
    df[col] = df["categoria"].map(lambda c: DEF[c][i])

df = df.rename(columns={"cocina": "tipo_comida", "horario": "horario_osm"})
df = df.sort_values(["categoria", "zona", "nombre"]).reset_index(drop=True)
df.insert(0, "id", df.index + 1)

salida = ["id", "nombre", "categoria", "zona", "lat", "lon", "ambiente",
          "duracion_min", "costo_estimado", "precio_nivel", "nivel_actividad",
          "apto_ninos", "apto_adultos_mayores", "es_comida", "tipo_comida",
          "hora_apertura", "hora_cierre", "dias_cerrado", "horario_osm", "sitio_web"]
df[salida].to_csv("../data/lugares_limpio.csv", index=False, encoding="utf-8-sig")

print("Lugares seleccionados:", len(df))
print("\nPor zona:")
print(df["zona"].value_counts())
print("\nPor categoria:")
print(df["categoria"].value_counts())
