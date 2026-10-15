"""Calidad de datos: deteccion de problemas y procedencia (dato real vs estimado)."""
import pandas as pd
import pytest

from app.calidad_datos import (DEFECTOS_CATEGORIA, analizar, campos_faltantes, defecto,
                               detectar_duplicados, fuera_de_la_caja_de_descarga,
                               motivo_coordenada_invalida, procedencia_atributos,
                               procedencia_costo, procedencia_horario, tiene_nombre_no_latino)

CENTRO = (19.4326, -99.1332)


def lugar(id, nombre, cat="museo", lat=CENTRO[0], lon=CENTRO[1], **extra):
    fila = {"id": id, "nombre": nombre, "categoria": cat, "zona": "Centro Historico", "lat": lat,
            "lon": lon, "ambiente": "cultural|tranquilo", "duracion_min": 90, "costo_estimado": 80,
            "precio_nivel": 2, "nivel_actividad": 1, "apto_ninos": 1, "apto_adultos_mayores": 1,
            "es_comida": 0, "tipo_comida": None, "hora_apertura": "10:00", "hora_cierre": "17:00",
            "dias_cerrado": "lunes", "horario_osm": None, "sitio_web": None}
    fila.update(extra)
    return fila


# ------------------------------------------------------------ coordenadas
@pytest.mark.parametrize("lat, lon, esperado", [
    (19.4326, -99.1332, ""),
    (None, -99.1, "coordenada_vacia"),
    (float("nan"), float("nan"), "coordenada_vacia"),
    (0, 0, "coordenada_cero"),
    (-99.13, 19.43, "latitud_longitud_invertidas"),
    (40.7, -74.0, "fuera_de_la_zona_de_estudio"),                # Nueva York
    (95, -99.1, "coordenada_fuera_de_rango"),
])
def test_coordenadas_invalidas(lat, lon, esperado):
    assert motivo_coordenada_invalida(lat, lon) == esperado


def test_un_poco_fuera_de_la_caja_es_advertencia_no_error():
    """Un area de OSM cuyo centro cae a ~130 m de la caja de descarga sigue siendo valida."""
    assert motivo_coordenada_invalida(19.4612, -99.0837) == ""
    assert fuera_de_la_caja_de_descarga(19.4612, -99.0837)
    assert not fuera_de_la_caja_de_descarga(*CENTRO)


# ------------------------------------------------------------ duplicados
def test_detecta_duplicado_exacto_aunque_cambie_acento_y_mayusculas():
    df = pd.DataFrame([lugar(1, "Café El Péndulo", "cafeteria"),
                       lugar(2, "CAFE EL PENDULO", "cafeteria", lat=CENTRO[0] + 0.0003)])
    pares = detectar_duplicados(df)
    assert [(p["id_a"], p["id_b"], p["tipo"]) for p in pares] == [(1, 2, "duplicado_exacto")]


def test_detecta_nombre_similar_y_misma_ubicacion():
    df = pd.DataFrame([lugar(1, "Museo Nacional de Arte"), lugar(2, "Museo Nacional de Artes", lat=CENTRO[0] + 0.0004),
                       lugar(3, "Galeria X", "galeria", lat=19.40, lon=-99.17),
                       lugar(4, "Otra Cosa Distinta", "parque", lat=19.40, lon=-99.17)])
    tipos = {(p["id_a"], p["id_b"]): p["tipo"] for p in detectar_duplicados(df)}
    assert tipos[(1, 2)] == "nombre_similar"
    assert tipos[(3, 4)] == "misma_ubicacion"


def test_no_marca_lugares_distintos_ni_lejanos():
    df = pd.DataFrame([lugar(1, "Starbucks", "cafeteria"),
                       lugar(2, "Starbucks", "cafeteria", lat=19.40, lon=-99.17),   # otra sucursal, lejos
                       lugar(3, "Museo del Chocolate", lat=19.41, lon=-99.15)])
    assert detectar_duplicados(df) == []


def test_duplicado_exacto_deja_inutilizable_al_que_tiene_menos_datos():
    df = pd.DataFrame([lugar(1, "Cafe Uno", "cafeteria"),
                       lugar(2, "cafe uno", "cafeteria", sitio_web="https://uno.mx")])
    r, rep, _ = analizar(df)
    assert r.set_index("id")["usable"].to_dict() == {1: 0, 2: 1}
    assert rep["no_usables"] == 1


def test_coordenada_invalida_y_campo_obligatorio_vacio_dejan_inutilizable():
    df = pd.DataFrame([lugar(1, "Bien"), lugar(2, "Mal", lat=0, lon=0),
                       lugar(3, None, lat=19.41, lon=-99.15)])
    r, rep, prob = analizar(df)
    assert r["usable"].tolist() == [1, 0, 0]
    assert "coordenada_cero" in r.loc[1, "calidad_flags"]
    assert "campo_obligatorio_faltante:nombre" in r.loc[2, "calidad_flags"]
    assert set(prob["id"]) == {2, 3}


def test_analizar_no_cambia_el_numero_de_filas_ni_pierde_columnas():
    df = pd.DataFrame([lugar(1, "A"), lugar(2, "B", "parque", lat=19.41, lon=-99.16)])
    r, _, _ = analizar(df)
    assert len(r) == 2 and set(df.columns) <= set(r.columns)


# ------------------------------------------------------------ campos y alertas
def test_campos_faltantes_separa_obligatorios_de_informacion_que_osm_no_trae():
    obligatorios, opcionales = campos_faltantes(pd.Series(lugar(1, "X", "restaurante", es_comida=1)))
    assert obligatorios == [] and set(opcionales) == {"horario_osm", "sitio_web", "tipo_comida"}
    obligatorios, _ = campos_faltantes(pd.Series(lugar(1, "X", lat=None)))
    assert obligatorios == ["lat"]


def test_nombre_no_latino_se_marca_para_revisar():
    assert tiene_nombre_no_latino("シティオ")
    assert not tiene_nombre_no_latino("Café del Ángel – Museo Ñandú")


def test_lugar_lejos_de_su_zona_se_marca():
    df = pd.DataFrame([lugar(1, "Mercado Lejano", "mercado", zona="Coyoacan", lat=19.2837, lon=-99.0980)])
    r, _, _ = analizar(df)
    assert "lejos_de_su_zona" in r.loc[0, "calidad_flags"]


# ------------------------------------------------------------ procedencia (real vs estimado)
def test_procedencia_del_horario():
    assert procedencia_horario("Mo-Su 10:00-18:00") == ("osm", "")
    assert procedencia_horario(float("nan")) == ("estimado_categoria", "")
    assert procedencia_horario("lunes a domingo 13:00 23:00") == ("estimado_categoria", "horario_osm_no_interpretable")


def test_procedencia_del_costo_no_inventa_precios():
    assert procedencia_costo("museo", 80, "no") == (0, "osm_fee_no", "")                # gratis segun OSM
    assert procedencia_costo("museo", 80, "yes") == (80, "estimado_categoria", "")      # cobra, monto desconocido
    assert procedencia_costo("museo", 80, float("nan")) == (80, "estimado_categoria", "")
    assert procedencia_costo("museo", 120, float("nan"))[1] == "manual"                 # alguien lo edito
    # un costo puesto a mano NO se pisa aunque OSM diga fee=no; solo se avisa
    assert procedencia_costo("museo", 120, "no") == (120, "manual", "costo_contradice_osm_fee_no")
    # fee=yes con costo 0 estimado: se avisa pero no se inventa un monto
    assert procedencia_costo("mirador", 0, "yes") == (0, "estimado_categoria", "costo_cero_pero_osm_indica_cobro")


def test_procedencia_de_atributos():
    f = pd.Series(lugar(1, "X"))
    assert procedencia_atributos(f) == "estimado_categoria"
    f["apto_ninos"] = 0
    assert procedencia_atributos(f) == "manual_parcial"


def test_defecto_por_categoria():
    assert defecto("museo", "duracion_min") == 90 and defecto("inexistente", "duracion_min") is None
    assert all(len(v) == 11 for v in DEFECTOS_CATEGORIA.values())


# ------------------------------------------------------------ el dataset real
def test_dataset_real_cumple_los_invariantes(lugares):
    assert len(lugares) >= 250
    assert lugares["id"].is_unique
    assert not lugares[["nombre", "categoria", "zona", "lat", "lon"]].isna().any().any()
    assert all(motivo_coordenada_invalida(a, b) == "" for a, b in zip(lugares["lat"], lugares["lon"]))
    assert detectar_duplicados(lugares, ) == [] or all(
        p["tipo"] != "duplicado_exacto" for p in detectar_duplicados(lugares))
    assert set(lugares["categoria"]) <= set(DEFECTOS_CATEGORIA)
    assert (lugares["costo_estimado"] >= 0).all() and (lugares["duracion_min"] > 0).all()


def test_dataset_real_distingue_dato_real_de_estimacion(lugares):
    assert set(lugares["horario_fuente"]) <= {"osm", "estimado_categoria"}
    assert set(lugares["costo_fuente"]) <= {"osm_fee_no", "estimado_categoria", "manual"}
    assert set(lugares["duracion_fuente"]) <= {"estimado_categoria", "manual"}
    # todo lugar marcado con horario real tiene un horario_osm que se interpreta
    from app.horarios import parsear_horario_osm
    reales = lugares[lugares["horario_fuente"] == "osm"]
    assert len(reales) > 150
    assert all(parsear_horario_osm(t) is not None for t in reales["horario_osm"])
    # y todo lugar gratis por OSM cuesta 0
    assert (lugares[lugares["costo_fuente"] == "osm_fee_no"]["costo_estimado"] == 0).all()
