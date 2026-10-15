"""Recomendador: similitud coseno, reglas, pesos y reproducibilidad."""
import numpy as np
import pandas as pd
import pytest

from app.perfiles import Perfil, INTERESES, vector_lugar
from app.recomendador import (PESOS_POR_DEFECTO, confianza_datos, puntuar, recomendar,
                              resolver_pesos)


def test_similitud_coseno_es_1_para_vectores_iguales_y_0_para_ortogonales(lugares):
    p = Perfil(tipo_grupo="solo", presupuesto_por_persona=1000, intereses={"comida": 1.0})
    r = puntuar(lugares, p)
    rest = r[r["categoria"] == "restaurante"]["sim"]
    assert np.allclose(rest, 1.0)                                  # restaurante = solo "comida"
    assert np.allclose(r[r["categoria"] == "mirador"]["sim"], 0.0)  # mirador: fotografia/naturaleza
    assert ((r["sim"] >= 0) & (r["sim"] <= 1 + 1e-9)).all()


def test_sin_intereses_la_similitud_es_cero_y_no_truena(lugares):
    r = recomendar(lugares, Perfil(tipo_grupo="amigos", presupuesto_por_persona=800), n=5)
    assert len(r) == 5 and (r["sim"] == 0).all()


def test_el_puntaje_es_la_combinacion_documentada(lugares):
    p = Perfil(tipo_grupo="pareja", presupuesto_por_persona=800, intereses={"arte": 0.9, "comida": 0.5})
    r = puntuar(lugares, p)
    w = PESOS_POR_DEFECTO
    esperado = (w["similitud"] * r["sim"] + w["reglas"] * r["ajuste"] + w["confianza"] * r["confianza"]
                - w["precio"] * r["precio_rel"])
    assert np.allclose(r["puntaje"], esperado)


def test_la_confianza_no_es_popularidad_ni_depende_solo_del_sitio_web():
    """Antes 'tiene sitio web' valia como popularidad. Ahora un sitio web solo aporta 0.25 de la
    confianza en los datos, y un lugar con horario real pero sin web puede superarlo."""
    df = pd.DataFrame({
        "horario_osm": [None, "Mo-Su 10:00-18:00"],
        "sitio_web": ["https://x.mx", None],
        "es_comida": [0, 0], "tipo_comida": [None, None], "costo_osm": [None, None]})
    c = confianza_datos(df)
    assert c[0] == pytest.approx(0.25) and c[1] == pytest.approx(0.50)
    assert c[1] > c[0]
    completo = df.assign(horario_osm="Mo-Su 10:00-18:00", sitio_web="x", costo_osm="no")
    assert confianza_datos(completo).max() == pytest.approx(1.0)


def test_el_horario_no_interpretable_no_da_confianza():
    df = pd.DataFrame({"horario_osm": ["lunes a domingo 13:00 23:00"], "sitio_web": [None]})
    assert confianza_datos(df)[0] == 0.0


def test_los_pesos_se_validan():
    assert resolver_pesos()["similitud"] == 0.60
    assert resolver_pesos({"precio": 0.3})["precio"] == 0.3
    with pytest.raises(ValueError):
        resolver_pesos({"popularidad": 0.1})
    with pytest.raises(ValueError):
        resolver_pesos({"reglas": -0.1})


def test_cambiar_los_pesos_cambia_la_recomendacion(lugares):
    p = Perfil(tipo_grupo="amigos", presupuesto_por_persona=700, nivel_actividad=3,
               intereses={"comida": 0.9, "cultura": 0.5})
    base = recomendar(lugares, p, n=10)
    sin_sim = recomendar(lugares, p, n=10, pesos={"similitud": 0.0})
    assert set(base["id"]) != set(sin_sim["id"])
    barato = recomendar(lugares, p, n=10, pesos={"precio": 2.0})
    caro = recomendar(lugares, p, n=10, pesos={"precio": 0.0})
    assert barato["costo_estimado"].mean() < caro["costo_estimado"].mean()


def test_fama_real_solo_actua_si_el_dataset_la_trae(lugares):
    p = Perfil(tipo_grupo="solo", presupuesto_por_persona=1000, intereses={"cultura": 1.0})
    assert "fama_norm" not in puntuar(lugares, p).columns
    con_fama = lugares.copy()
    con_fama["fama"] = 3.0
    celebre = con_fama[(con_fama["categoria"] == "museo")].iloc[5]["id"]
    con_fama.loc[con_fama["id"] == celebre, "fama"] = 5.0
    r = puntuar(con_fama, p)
    assert "fama_norm" in r.columns
    museos = r[r["categoria"] == "museo"]
    assert museos.loc[museos["id"] == celebre, "fama_norm"].iloc[0] == 1.0


def test_reproducible_y_sin_empates_inestables(lugares, perfiles):
    for p in perfiles.values():
        a = recomendar(lugares, p, n=40, max_por_categoria=8)
        b = recomendar(lugares, p, n=40, max_por_categoria=8)
        assert a["id"].tolist() == b["id"].tolist()


def test_diversidad_y_filtros_duros(lugares, perfiles):
    r = recomendar(lugares, perfiles["Familia con ninos"], n=40, max_por_categoria=3)
    assert r["categoria"].value_counts().max() <= 3
    assert "bar" not in set(r["categoria"])                       # con ninos nunca hay bares
    assert (r["apto_ninos"] == 1).all()
    mayores = recomendar(lugares, perfiles["Adultos mayores"], n=40, max_por_categoria=40)
    assert (mayores["apto_adultos_mayores"] == 1).all() and (mayores["nivel_actividad"] <= 2).all()
    centro = recomendar(lugares, perfiles["Amigos en el Centro"], n=40, max_por_categoria=40)
    assert set(centro["zona"]) == {"Centro Historico"}


def test_no_recomienda_lo_que_esta_cerrado_ese_dia(lugares):
    """Con horario real de OSM, un lugar cerrado el lunes no aparece en un perfil de lunes."""
    from app.horarios import ventanas_lugar
    p = Perfil(tipo_grupo="pareja", presupuesto_por_persona=900, dia_semana="lunes",
               intereses={"cultura": 0.9, "arte": 0.9})
    r = recomendar(lugares, p, n=40, max_por_categoria=40)
    assert len(r) > 10
    for _, l in r.iterrows():
        assert ventanas_lugar(l, "lunes")[0], l["nombre"]
    cerrados = [l for _, l in lugares.iterrows() if not ventanas_lugar(l, "lunes")[0]]
    assert cerrados and not set(r["id"]) & {l["id"] for l in cerrados}


def test_vector_de_lugar_tiene_un_eje_por_interes():
    assert len(vector_lugar("museo")) == len(INTERESES) == 8
    assert vector_lugar("inexistente") == [0.0] * 8
