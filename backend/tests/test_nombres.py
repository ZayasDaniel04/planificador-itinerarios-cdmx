"""Nombres en otro idioma: se aclaran entre parentesis o se eliminan."""
import re

import pandas as pd
import pytest

from app.calidad_datos import analizar, tiene_nombre_no_latino
from app.nombres import (LUGARES_A_ELIMINAR, NOMBRES_EN_OTRO_IDIOMA, adaptar, descripcion_lugar,
                         nombre_aclarado, parece_otro_idioma)


# ------------------------------------------------------------ que es el lugar
@pytest.mark.parametrize("categoria, cocina, esperado", [
    ("restaurante", "japanese;sushi", "restaurante de comida japonesa"),
    ("restaurante", "sushi", "restaurante de sushi"),
    ("restaurante", "pizza;italian;pasta", "restaurante de comida italiana"),      # la nacionalidad en las 2 primeras
    ("restaurante", "steak_house;burger;american", "restaurante de carnes"),       # americana va 3a: manda la 1a
    ("restaurante", "Russian_food", "restaurante de comida rusa"),
    ("restaurante", "taquería", "taquería"),
    ("restaurante", None, "restaurante"),                                           # sin dato: no se inventa
    ("restaurante", float("nan"), "restaurante"),
    ("restaurante", "algo_raro", "restaurante"),
    ("cafeteria", "coffee_shop", "cafetería"),
    ("cafeteria", "teahouse", "casa de té"),
    ("cafeteria", "waffle;churros;crepe", "cafetería de waffles"),
    ("cafeteria", "Bakery,_tea,_dessert", "pastelería"),
    ("bar", "american;japanese;korean;mexican", "bar"),                             # en un bar no se usa la cocina
    ("libreria", None, "librería"),
])
def test_descripcion_usa_solo_la_categoria_y_la_cocina_de_osm(categoria, cocina, esperado):
    assert descripcion_lugar(categoria, cocina) == esperado


def test_nombre_aclarado_agrega_el_parentesis():
    assert nombre_aclarado("Kabuki", "restaurante", "sushi") == "Kabuki (restaurante de sushi)"
    assert nombre_aclarado("Living Room Bar", "bar") == "Living Room Bar (bar)"
    assert nombre_aclarado("Hanky Panky Cocktail Bar", "bar", None, 11457540741) == \
        "Hanky Panky Cocktail Bar (bar de cocteles)"


# ------------------------------------------------------------ detector
@pytest.mark.parametrize("nombre", ["Living Room Bar", "Kabuki", "シティオ", "Sólo Entrada / Only Entrance",
                                    "Patisserie Dominique", "Ramen Ichi", "Maison Kayser"])
def test_detecta_nombres_en_otro_idioma(nombre):
    assert parece_otro_idioma(nombre)


@pytest.mark.parametrize("nombre", ["Museo Nacional de Antropología", "La Casa de los Tacos", "Café de Tacuba",
                                    "Parque Lira", "Jardín Botánico", "Contramar", "Tlecān", "Xkina Reforma",
                                    "Parque John F. Kennedy", "Foro Shakespeare"])
def test_no_marca_nombres_en_espanol_ni_nombres_propios_ni_lenguas_indigenas(nombre):
    assert not parece_otro_idioma(nombre)


# ------------------------------------------------------------ adaptar
def fila(id, osm_id, nombre, categoria="restaurante", cocina=None):
    return {"id": id, "osm_id": osm_id, "nombre": nombre, "categoria": categoria, "tipo_comida": cocina}


def test_adaptar_aclara_elimina_y_conserva_el_original():
    kabuki = [o for o, n in NOMBRES_EN_OTRO_IDIOMA.items() if n == "Kabuki"][0]
    sin_sentido = [o for o, (n, _) in LUGARES_A_ELIMINAR.items() if n == "シティオ"][0]
    df = pd.DataFrame([fila(1, kabuki, "Kabuki", cocina="sushi"),
                       fila(2, 999, "La Casa de los Tacos", cocina="mexican"),
                       fila(3, sin_sentido, "シティオ", "mirador")])
    nuevo, eliminados = adaptar(df)
    assert nuevo["id"].tolist() == [1, 2]
    assert nuevo.loc[0, "nombre"] == "Kabuki (restaurante de sushi)"
    assert nuevo.loc[0, "nombre_original"] == "Kabuki"
    assert nuevo.loc[1, "nombre"] == "La Casa de los Tacos"                          # en espanol: no se toca
    assert [e["nombre"] for e in eliminados] == ["シティオ"] and eliminados[0]["motivo"]


def test_adaptar_es_idempotente():
    kabuki = [o for o, n in NOMBRES_EN_OTRO_IDIOMA.items() if n == "Kabuki"][0]
    df = pd.DataFrame([fila(1, kabuki, "Kabuki", cocina="sushi")])
    una, _ = adaptar(df)
    dos, eliminados = adaptar(una)
    assert una.equals(dos) and eliminados == []


def test_no_aplica_una_decision_al_lugar_equivocado():
    kabuki = [o for o, n in NOMBRES_EN_OTRO_IDIOMA.items() if n == "Kabuki"][0]
    with pytest.raises(ValueError, match="No se aplica"):
        adaptar(pd.DataFrame([fila(1, kabuki, "Otro Lugar Distinto")]))


def test_registros_sin_osm_id_no_se_tocan():
    df = pd.DataFrame([fila(1, float("nan"), "Living Room Bar", "bar")])
    nuevo, eliminados = adaptar(df)
    assert nuevo.loc[0, "nombre"] == "Living Room Bar" and eliminados == []


def test_la_calidad_avisa_de_nombres_en_otro_idioma_sin_aclarar():
    base = dict(categoria="bar", zona="Centro Historico", lat=19.4326, lon=-99.1332, ambiente="x",
                duracion_min=90, costo_estimado=250, precio_nivel=3, nivel_actividad=1, apto_ninos=0,
                apto_adultos_mayores=0, es_comida=1, tipo_comida=None, hora_apertura="17:00",
                hora_cierre="23:59", dias_cerrado="", horario_osm=None, sitio_web=None)
    df = pd.DataFrame([{**base, "id": 1, "nombre": "Living Room Bar"},
                       {**base, "id": 2, "nombre": "Living Room Bar (bar)", "lat": 19.40, "lon": -99.17}])
    r, _, _ = analizar(df)
    assert "nombre_otro_idioma_sin_aclarar" in r.loc[0, "calidad_flags"]
    assert "nombre_otro_idioma_sin_aclarar" not in r.loc[1, "calidad_flags"]


# ------------------------------------------------------------ el dataset real
def test_ningun_nombre_del_dataset_esta_en_otro_alfabeto(lugares):
    assert not [n for n in lugares["nombre"] if tiene_nombre_no_latino(n)]


def test_todo_nombre_en_otro_idioma_del_dataset_esta_aclarado(lugares):
    sin_aclarar = [n for n in lugares["nombre"] if parece_otro_idioma(n) and "(" not in n]
    assert sin_aclarar == []


def test_los_lugares_eliminados_ya_no_estan(lugares):
    assert not set(lugares["osm_id"]) & set(LUGARES_A_ELIMINAR)
    assert not lugares["nombre"].str.contains("Only Entrance|シティオ", regex=True).any()


def test_los_aclarados_conservan_su_nombre_original_y_son_coherentes(lugares):
    por_osm = lugares.set_index("osm_id")
    for osm, original in NOMBRES_EN_OTRO_IDIOMA.items():
        assert osm in por_osm.index, f"falta {original}"
        f = por_osm.loc[osm]
        assert f["nombre_original"] == original
        assert f["nombre"].startswith(original + " (") and f["nombre"].endswith(")")
        # lo que dice el parentesis sale de la categoria y de la cocina de OSM: nada inventado
        desc = f["nombre"][len(original) + 2:-1]
        assert desc == nombre_aclarado(original, f["categoria"], f["tipo_comida"], osm)[len(original) + 2:-1]
        if "comida" in desc:                              # "restaurante de comida japonesa" -> estaba en OSM
            assert isinstance(f["tipo_comida"], str) and f["tipo_comida"].strip()


def test_los_nombres_en_espanol_no_cambiaron(lugares):
    sin_cambio = lugares[~lugares["osm_id"].isin(NOMBRES_EN_OTRO_IDIOMA)]
    assert (sin_cambio["nombre"] == sin_cambio["nombre_original"]).all()
    assert len(lugares) == 297


def test_los_itinerarios_muestran_el_nombre_aclarado(lugares):
    from app.itinerario import generar_itinerario
    from app.perfiles import Perfil
    p = Perfil(tipo_grupo="amigos", presupuesto_por_persona=900, nivel_actividad=3, dia_semana="sabado",
               hora_inicio="10:00", hora_fin="23:00", intereses={"vida_nocturna": 1.0, "comida": 0.9})
    nombres = [x["nombre"] for x in generar_itinerario(lugares, p)["paradas"]]
    assert nombres and not [n for n in nombres if parece_otro_idioma(n) and "(" not in n]
