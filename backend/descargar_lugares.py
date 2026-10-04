import requests
import pandas as pd

URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "planificador-itinerarios-cdmx/1.0 (proyecto escolar de IA)", "Accept": "*/*"}
# Caja de coordenadas (sur, oeste, norte, este): Centro, Roma, Condesa,
# Polanco, Chapultepec, Coyoacan y San Angel
BBOX = "19.28,-99.24,19.46,-99.08"

# (categoria, etiqueta de OpenStreetMap, valor)
CATEGORIAS = [
    ("museo", "tourism", "museum"),
    ("galeria", "tourism", "gallery"),
    ("atraccion", "tourism", "attraction"),
    ("mirador", "tourism", "viewpoint"),
    ("zoologico", "tourism", "zoo"),
    ("parque", "leisure", "park"),
    ("jardin", "leisure", "garden"),
    ("restaurante", "amenity", "restaurant"),
    ("cafeteria", "amenity", "cafe"),
    ("bar", "amenity", "bar"),
    ("mercado", "amenity", "marketplace"),
    ("teatro", "amenity", "theatre"),
    ("cine", "amenity", "cinema"),
    ("libreria", "shop", "books"),
    ("centro_comercial", "shop", "mall"),
]

filas = []
for categoria, clave, valor in CATEGORIAS:
    consulta = f"""
    [out:json][timeout:180];
    (
      node["{clave}"="{valor}"]["name"]({BBOX});
      way["{clave}"="{valor}"]["name"]({BBOX});
    );
    out center tags;
    """
    print(f"Descargando {categoria}...")
    r = requests.post(URL, data={"data": consulta}, headers=HEADERS, timeout=200)
    if r.status_code != 200:
        print(f"  Error {r.status_code}, se omite {categoria}")
        continue
    for el in r.json()["elements"]:
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        t = el.get("tags", {})
        filas.append({
            "osm_id": el["id"],
            "nombre": t.get("name"),
            "categoria": categoria,
            "lat": lat,
            "lon": lon,
            "horario": t.get("opening_hours"),
            "cocina": t.get("cuisine"),
            "costo_osm": t.get("fee"),
            "sitio_web": t.get("website"),
        })
    print(f"  {sum(1 for f in filas if f['categoria'] == categoria)} lugares")

df = pd.DataFrame(filas).drop_duplicates(subset="osm_id")
df.to_csv("../data/lugares_raw.csv", index=False, encoding="utf-8-sig")
print("\nTotal:", len(df))
print(df["categoria"].value_counts())
