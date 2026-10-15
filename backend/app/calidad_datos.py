"""Calidad y procedencia de los datos de lugares.

Reglas de este modulo:
  * Solo DETECTA y ETIQUETA. No borra lugares ni corrige valores por su cuenta (el CSV tiene
    correcciones manuales que no deben perderse). La unica excepcion es la columna `usable`,
    que marca con 0 lo que no se puede usar (coordenadas invalidas, campos obligatorios vacios
    o duplicados exactos) y que cargar_lugares() respeta.
  * Distingue DATO REAL (viene de OpenStreetMap) de ESTIMACION (valor por defecto de la
    categoria). Nunca se inventan horarios, precios ni condiciones de accesibilidad: lo que no
    se sabe queda marcado como "estimado_categoria".
"""
import re
from difflib import SequenceMatcher

import pandas as pd

from app.horarios import parsear_horario_osm
from app.restricciones import distancia_km, normalizar_nombre

# Caja de coordenadas usada en la descarga (sur, oeste, norte, este)
BBOX = (19.28, -99.24, 19.46, -99.08)
# OSM calcula el centro de las areas (ways) y a veces cae un poco fuera de la caja aunque el
# lugar la toque. Hasta este margen solo se ADVIERTE; mas alla se considera coordenada invalida.
MARGEN_BBOX_GRADOS = 0.02          # ~2.2 km

# Centro de cada zona; cada lugar se asigna a la zona cuyo centro queda mas cerca
ZONAS = {
    "Centro Historico": (19.4326, -99.1332),
    "Roma-Condesa": (19.4120, -99.1700),
    "Polanco-Chapultepec": (19.4250, -99.1900),
    "Coyoacan": (19.3500, -99.1620),
    "San Angel": (19.3470, -99.1900),
}
UMBRAL_LEJOS_DE_ZONA_KM = 5.0      # mas lejos que esto del centro de su zona se marca para revisar
RADIO_DUPLICADO_M = 150            # lugares con nombre parecido a menos de esta distancia
RADIO_DUPLICADO_EXACTO_M = 100     # mismo nombre normalizado + misma categoria a menos de esto

COLUMNAS_DEFECTO = ["duracion_min", "costo_estimado", "precio_nivel", "nivel_actividad",
                    "apto_ninos", "apto_adultos_mayores", "es_comida",
                    "hora_apertura", "hora_cierre", "dias_cerrado", "ambiente"]

# Valores por defecto por categoria, en el orden de COLUMNAS_DEFECTO. Son SUPUESTOS, no datos:
# OpenStreetMap no trae duracion, precio, accesibilidad ni ambiente.
DEFECTOS_CATEGORIA = {
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

CAMPOS_OBLIGATORIOS = ["nombre", "categoria", "zona", "lat", "lon"]
ATRIBUTOS_ESTIMADOS = ["precio_nivel", "nivel_actividad", "apto_ninos", "apto_adultos_mayores",
                       "ambiente"]


def defecto(categoria, columna):
    """Valor por defecto (estimado) de una columna para una categoria, o None."""
    if categoria not in DEFECTOS_CATEGORIA:
        return None
    return DEFECTOS_CATEGORIA[categoria][COLUMNAS_DEFECTO.index(columna)]


def asignar_zona(lat, lon):
    return min(ZONAS, key=lambda z: (lat - ZONAS[z][0]) ** 2 + (lon - ZONAS[z][1]) ** 2)


# ------------------------------------------------------------------ validaciones puntuales
def _dentro_de_caja(lat, lon, margen=0.0):
    s, o, n, e = BBOX
    return (s - margen <= lat <= n + margen) and (o - margen <= lon <= e + margen)


def motivo_coordenada_invalida(lat, lon):
    """Devuelve '' si la coordenada es utilizable, o el motivo por el que no lo es."""
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return "coordenada_vacia"
    if lat == 0 and lon == 0:
        return "coordenada_cero"
    # lat y lon intercambiadas: caen dentro de la caja si se voltean
    if _dentro_de_caja(lon, lat, MARGEN_BBOX_GRADOS) and not _dentro_de_caja(lat, lon, MARGEN_BBOX_GRADOS):
        return "latitud_longitud_invertidas"
    if abs(lat) > 90 or abs(lon) > 180:
        return "coordenada_fuera_de_rango"
    if not _dentro_de_caja(lat, lon, MARGEN_BBOX_GRADOS):
        return "fuera_de_la_zona_de_estudio"
    return ""


def fuera_de_la_caja_de_descarga(lat, lon):
    """True si la coordenada es valida pero cae un poco fuera de la caja original de descarga."""
    return not motivo_coordenada_invalida(lat, lon) and not _dentro_de_caja(lat, lon)


def tiene_nombre_no_latino(nombre):
    """True si el nombre usa alfabetos no latinos (ej. japones): suele indicar un registro mal
    etiquetado o fuera de lugar para un itinerario en espanol."""
    return bool(re.search(r"[^\u0000-\u024F\u2010-\u2027\s]", str(nombre)))


def distancia_a_su_zona_km(lat, lon, zona):
    if zona not in ZONAS:
        return float("nan")
    return distancia_km(lat, lon, *ZONAS[zona])


# ------------------------------------------------------------------ duplicados
def _celda(lat, lon):
    return (round(lat / 0.002), round(lon / 0.002))        # ~200 m


def detectar_duplicados(df, radio_m=RADIO_DUPLICADO_M, radio_exacto_m=RADIO_DUPLICADO_EXACTO_M,
                        umbral_similitud=0.88):
    """Busca pares de registros que parecen el mismo lugar.

    Tipos:
      duplicado_exacto     mismo nombre normalizado y misma categoria, a <= radio_exacto_m
      misma_ubicacion      mismas coordenadas (5 decimales, ~1 m) con nombres distintos
      nombre_similar       nombre parecido (similitud >= umbral) a <= radio_m, misma categoria

    Devuelve una lista de diccionarios con id_a, id_b, tipo, distancia_m y similitud."""
    cols = ["id", "nombre", "categoria", "lat", "lon"]
    filas = [r for r in df[cols].itertuples(index=False)
             if not motivo_coordenada_invalida(r.lat, r.lon)]
    normalizados = {r.id: normalizar_nombre(r.nombre) for r in filas}
    celdas = {}
    for r in filas:
        celdas.setdefault(_celda(r.lat, r.lon), []).append(r)

    pares = []
    for (cy, cx), grupo in celdas.items():
        vecinos = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                vecinos.extend(celdas.get((cy + dy, cx + dx), []))
        for a in grupo:
            for b in vecinos:
                if a.id >= b.id:
                    continue
                dist_m = distancia_km(a.lat, a.lon, b.lat, b.lon) * 1000
                if dist_m > radio_m:
                    continue
                na, nb = normalizados[a.id], normalizados[b.id]
                sim = 1.0 if na == nb else SequenceMatcher(None, na, nb).ratio()
                if na == nb and a.categoria == b.categoria and dist_m <= radio_exacto_m:
                    tipo = "duplicado_exacto"
                elif round(a.lat, 5) == round(b.lat, 5) and round(a.lon, 5) == round(b.lon, 5):
                    tipo = "misma_ubicacion"
                elif a.categoria == b.categoria and sim >= umbral_similitud:
                    tipo = "nombre_similar"
                else:
                    continue
                pares.append({"id_a": int(a.id), "id_b": int(b.id), "tipo": tipo,
                              "distancia_m": round(dist_m, 1), "similitud": round(sim, 3)})
    pares.sort(key=lambda p: (p["id_a"], p["id_b"]))
    return pares


# ------------------------------------------------------------------ campos faltantes
def campos_faltantes(fila):
    """Campos que faltan en un registro. Los OBLIGATORIOS impiden usar el lugar; los demas son
    informacion real que OSM no trae y que se reemplaza por estimaciones."""
    obligatorios = [c for c in CAMPOS_OBLIGATORIOS
                    if pd.isna(fila.get(c)) or str(fila.get(c)).strip() == ""]
    opcionales = []
    if pd.isna(fila.get("horario_osm")):
        opcionales.append("horario_osm")
    if pd.isna(fila.get("sitio_web")):
        opcionales.append("sitio_web")
    if fila.get("es_comida") == 1 and pd.isna(fila.get("tipo_comida")):
        opcionales.append("tipo_comida")
    return obligatorios, opcionales


# ------------------------------------------------------------------ procedencia
def procedencia_costo(categoria, costo, costo_osm):
    """Devuelve (costo_final, fuente, bandera).

    OSM no trae precios. Solo trae la etiqueta `fee` (yes/no):
      fee=no   -> es gratis: costo 0, dato real ("osm_fee_no"). Solo se reemplaza si el costo
                  actual es el valor por defecto; un costo puesto a mano no se pisa.
      fee=yes  -> cobra, pero no se sabe cuanto: se conserva la estimacion de la categoria.
      sin dato -> estimacion de la categoria ("estimado_categoria") o "manual" si alguien lo editó.
    """
    por_defecto = defecto(categoria, "costo_estimado")
    es_defecto = por_defecto is not None and costo == por_defecto
    fee = str(costo_osm).strip().lower() if not pd.isna(costo_osm) else ""
    if fee == "no":
        if costo == 0:
            return 0, "osm_fee_no", ""
        if es_defecto:
            return 0, "osm_fee_no", ""
        return costo, "manual", "costo_contradice_osm_fee_no"
    if fee == "yes":
        fuente = "estimado_categoria" if es_defecto else "manual"
        return costo, fuente, ("costo_cero_pero_osm_indica_cobro" if costo == 0 else "")
    return costo, ("estimado_categoria" if es_defecto else "manual"), ""


def procedencia_horario(horario_osm):
    """('osm' | 'estimado_categoria', bandera). Solo es 'osm' si el texto se pudo interpretar."""
    if pd.isna(horario_osm):
        return "estimado_categoria", ""
    if parsear_horario_osm(horario_osm) is not None:
        return "osm", ""
    return "estimado_categoria", "horario_osm_no_interpretable"


def procedencia_atributos(fila):
    """'estimado_categoria' si precio_nivel, nivel_actividad, apto_ninos, apto_adultos_mayores y
    ambiente son los valores por defecto de la categoria; 'manual_parcial' si alguien los edito."""
    for col in ATRIBUTOS_ESTIMADOS:
        d = defecto(fila["categoria"], col)
        if d is not None and fila[col] != d:
            return "manual_parcial"
    return "estimado_categoria"


# ------------------------------------------------------------------ analisis completo
def analizar(df, raw=None):
    """Enriquece el dataset con procedencia y banderas de calidad y arma el reporte.

    Devuelve (df_enriquecido, reporte, df_problemas). No cambia el numero de filas."""
    df = df.copy()

    # --- vinculo con OSM (para poder rastrear cada registro a su fuente)
    if raw is not None:
        raw = raw.copy()
        raw["_k"] = (raw["nombre"].astype(str).str.strip() + "|" + raw["categoria"].astype(str)
                     + "|" + raw["lat"].round(6).astype(str) + "|" + raw["lon"].round(6).astype(str))
        raw_unico = raw.drop_duplicates("_k", keep="first").set_index("_k")
        claves = (df["nombre"].astype(str).str.strip() + "|" + df["categoria"].astype(str)
                  + "|" + df["lat"].round(6).astype(str) + "|" + df["lon"].round(6).astype(str))
        if "osm_id" not in df.columns:
            df["osm_id"] = pd.to_numeric(claves.map(raw_unico["osm_id"])).astype("Int64")
        if "costo_osm" not in df.columns:
            df["costo_osm"] = claves.map(raw_unico["costo_osm"])
    else:
        for col in ("osm_id", "costo_osm"):
            if col not in df.columns:
                df[col] = pd.NA

    banderas = {i: [] for i in df.index}
    nuevos_costos, fuentes_costo, fuentes_horario, fuentes_attr, faltantes = [], [], [], [], []
    usable = pd.Series(1, index=df.index)

    for i, f in df.iterrows():
        # coordenadas
        motivo = motivo_coordenada_invalida(f["lat"], f["lon"])
        if motivo:
            banderas[i].append(motivo)
            usable[i] = 0
        elif fuera_de_la_caja_de_descarga(f["lat"], f["lon"]):
            banderas[i].append("fuera_de_caja_de_descarga")       # solo advertencia
        # campos
        obligatorios, opcionales = campos_faltantes(f)
        if obligatorios:
            banderas[i].extend(f"campo_obligatorio_faltante:{c}" for c in obligatorios)
            usable[i] = 0
        faltantes.append("|".join(opcionales))
        # procedencia
        costo, fuente_c, bandera_c = procedencia_costo(f["categoria"], f["costo_estimado"], f["costo_osm"])
        nuevos_costos.append(costo)
        fuentes_costo.append(fuente_c)
        if bandera_c:
            banderas[i].append(bandera_c)
        fuente_h, bandera_h = procedencia_horario(f["horario_osm"])
        fuentes_horario.append(fuente_h)
        if bandera_h:
            banderas[i].append(bandera_h)
        fuentes_attr.append(procedencia_atributos(f))
        # otras sospechas
        if tiene_nombre_no_latino(f["nombre"]):
            banderas[i].append("nombre_no_latino_revisar")
        d = distancia_a_su_zona_km(f["lat"], f["lon"], f["zona"])
        if f["zona"] not in ZONAS:
            banderas[i].append("zona_desconocida")
        elif d > UMBRAL_LEJOS_DE_ZONA_KM:
            banderas[i].append("lejos_de_su_zona")
        elif asignar_zona(f["lat"], f["lon"]) != f["zona"]:
            banderas[i].append("zona_distinta_a_la_mas_cercana")

    df["costo_estimado"] = nuevos_costos
    df["costo_fuente"] = fuentes_costo
    df["horario_fuente"] = fuentes_horario
    df["atributos_fuente"] = fuentes_attr
    df["duracion_fuente"] = [
        "estimado_categoria" if f["duracion_min"] == defecto(f["categoria"], "duracion_min") else "manual"
        for _, f in df.iterrows()]
    df["campos_faltantes"] = faltantes

    # --- duplicados
    pares = detectar_duplicados(df)
    por_id = df.set_index("id")
    for p in pares:
        a, b = p["id_a"], p["id_b"]
        ia = df.index[df["id"] == a][0]
        ib = df.index[df["id"] == b][0]
        banderas[ia].append(f"{p['tipo']}_con_id_{b}")
        banderas[ib].append(f"{p['tipo']}_con_id_{a}")
        if p["tipo"] == "duplicado_exacto":
            # se queda el registro con mas informacion; si empatan, el de id menor
            def riqueza(idx):
                r = df.loc[idx]
                return (int(r["horario_fuente"] == "osm") + int(not pd.isna(r["sitio_web"])), -int(r["id"]))
            perdedor = ib if riqueza(ia) >= riqueza(ib) else ia
            usable[perdedor] = 0

    df["usable"] = usable
    df["calidad_flags"] = ["|".join(banderas[i]) for i in df.index]

    # --- reporte
    n = len(df)
    conteo_flags = {}
    for lista in banderas.values():
        for b in lista:
            tipo = b.split(":")[0]
            tipo = re.sub(r"_con_id_\d+$", "", tipo)
            conteo_flags[tipo] = conteo_flags.get(tipo, 0) + 1
    problemas = df[df["calidad_flags"] != ""][["id", "nombre", "categoria", "zona", "usable", "calidad_flags"]]
    reporte = {
        "total_registros": n,
        "usables": int(df["usable"].sum()),
        "no_usables": int((df["usable"] == 0).sum()),
        "registros_con_alguna_bandera": int(len(problemas)),
        "banderas": dict(sorted(conteo_flags.items(), key=lambda kv: -kv[1])),
        "duplicados": pares,
        "coordenadas_invalidas": int(sum(1 for b in banderas.values()
                                         if any(x.startswith("coordenada") or x.startswith("latitud")
                                                or x.startswith("fuera_de_la_zona") for x in b))),
        "coordenadas_en_el_borde_de_la_caja": int(sum(1 for b in banderas.values()
                                                      if "fuera_de_caja_de_descarga" in b)),
        "procedencia": {
            "horario": df["horario_fuente"].value_counts().to_dict(),
            "costo": df["costo_fuente"].value_counts().to_dict(),
            "duracion": df["duracion_fuente"].value_counts().to_dict(),
            "atributos_ninos_mayores_actividad_ambiente": df["atributos_fuente"].value_counts().to_dict(),
        },
        "porcentaje_horario_real": round(100 * (df["horario_fuente"] == "osm").mean(), 1),
        "campos_vacios": {c: int(df[c].isna().sum()) for c in
                          ["horario_osm", "sitio_web", "tipo_comida", "costo_osm", "osm_id"] if c in df},
        "por_zona": df["zona"].value_counts().to_dict(),
        "por_categoria": df["categoria"].value_counts().to_dict(),
    }
    return df, reporte, problemas


def analizar_crudo(raw):
    """Revision rapida del CSV crudo de OpenStreetMap (antes de seleccionar los ~300 lugares)."""
    invalidas = [motivo_coordenada_invalida(a, b) for a, b in zip(raw["lat"], raw["lon"])]
    sin_nombre = raw["nombre"].isna() | (raw["nombre"].astype(str).str.strip() == "")
    clave = (raw["nombre"].astype(str).str.strip().str.lower() + "|" + raw["categoria"].astype(str))
    return {
        "registros": int(len(raw)),
        "osm_id_repetidos": int(raw["osm_id"].duplicated().sum()),
        "sin_nombre": int(sin_nombre.sum()),
        "coordenadas_invalidas": {m: invalidas.count(m) for m in set(invalidas) if m},
        "mismo_nombre_y_categoria": int(clave.duplicated().sum()),
        "con_horario_osm": int(raw["horario"].notna().sum()),
        "con_sitio_web": int(raw["sitio_web"].notna().sum()),
        "con_etiqueta_fee": int(raw["costo_osm"].notna().sum()),
    }
