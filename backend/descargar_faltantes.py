import time
import requests
import pandas as pd

SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HEADERS = {"User-Agent": "planificador-itinerarios-cdmx/1.0 (proyecto escolar de IA)", "Accept": "*/*"}

S, O, N, E = 19.28, -99.24, 19.46, -99.08
mlat, mlon = (S + N) / 2, (O + E) / 2
CUADRANTES = [
    f"{S},{O},{mlat},{mlon}",
    f"{S},{mlon},{mlat},{E}",
    f"{mlat},{O},{N},{mlon}",
    f"{mlat},{mlon},{N},{E}",
]

FALTANTES = [
    ("museo", "tourism", "museum"),
    ("galeria", "tourism", "gallery"),
    ("zoologico", "tourism", "zoo"),
    ("restaurante", "amenity", "restaurant"),
    ("mercado", "amenity", "marketplace"),
    ("teatro", "amenity", "theatre"),
    ("cine", "amenity", "cinema"),
]


def consultar(clave, valor, bbox):
    consulta = f"""
    [out:json][timeout:90];
    (
      node["{clave}"="{valor}"]["name"]({bbox});
      way["{clave}"="{valor}"]["name"]({bbox});
    );
    out center tags;
    """
    for intento in range(1, 6):
        servidor = SERVIDORES[(intento - 1) % len(SERVIDORES)]
        try:
            r = requests.post(servidor, data={"data": consulta}, headers=HEADERS, timeout=120)
            if r.status_code == 200:
                return r.json()["elements"]
            print(f"    intento {intento}: error {r.status_code}, espero {15 * intento}s")
        except Exception as e:
            print(f"    intento {intento}: {type(e).__name__}, espero {15 * intento}s")
        time.sleep(15 * intento)
    return None


filas = []
for categoria, clave, valor in FALTANTES:
    print(f"Descargando {categoria}...")
    total_cat = 0
    for i, bbox in enumerate(CUADRANTES, 1):
        elementos = consultar(clave, valor, bbox)
        if elementos is None:
            print(f"  cuadrante {i}: no se pudo, se omite")
            continue
        for el in elementos:
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
        total_cat += len(elementos)
        print(f"  cuadrante {i}: {len(elementos)} lugares")
        time.sleep(5)
    print(f"  -> {total_cat} en total\n")

nuevos = pd.DataFrame(filas)
existentes = pd.read_csv("../data/lugares_raw.csv")
df = pd.concat([existentes, nuevos]).drop_duplicates(subset="osm_id")
df.to_csv("../data/lugares_raw.csv", index=False, encoding="utf-8-sig")
print("Total final:", len(df))
print(df["categoria"].value_counts())
