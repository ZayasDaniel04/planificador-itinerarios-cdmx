"""Interpretacion de horarios reales de OpenStreetMap."""
import pytest

from app.horarios import (parsear_horario_osm, ventanas_del_dia, ventanas_lugar, indice_dia,
                          normalizar_dia, a_min, a_hhmm)


def ventanas(texto, dia):
    return ventanas_del_dia(parsear_horario_osm(texto), dia)


def test_rango_simple_todos_los_dias():
    for d in range(7):
        assert ventanas("Mo-Su 08:30-19:30", d) == [(510, 1170)]


def test_dias_no_listados_estan_cerrados():
    assert ventanas("Mo-Sa 09:00-19:00", 6) == []          # domingo cerrado
    assert ventanas("Mo-Sa 09:00-19:00", 5) == [(540, 1140)]


def test_regla_posterior_reemplaza_a_la_anterior():
    t = "Mo-Su 10:00-19:00; Su 11:00-15:00"
    assert ventanas(t, 0) == [(600, 1140)]
    assert ventanas(t, 6) == [(660, 900)]


def test_horario_que_cruza_la_medianoche_pasa_al_dia_siguiente():
    t = "Fr,Sa 18:00-02:00"
    assert ventanas(t, 4) == [(1080, 1440)]                 # viernes hasta 24:00
    assert ventanas(t, 5) == [(0, 120), (1080, 1440)]       # sabado: viene del viernes y abre otra vez
    assert ventanas(t, 6) == [(0, 120)]                     # domingo: solo lo que viene del sabado


def test_varios_tramos_en_un_dia_y_grupos_separados_por_coma():
    assert ventanas("Mo-Th 09:00-14:00, 15:00-18:00; Fr 09:00-13:00", 1) == [(540, 840), (900, 1080)]
    t = "Mo-We 12:00-24:00, Th-Sa 12:00-02:00, Su 17:00-24:00"
    assert ventanas(t, 2) == [(720, 1440)]
    assert ventanas(t, 6)[-1] == (1020, 1440)


def test_dias_con_vuelta_su_th():
    t = "Su-Th 07:30-21:30; Fr,Sa 07:30-22:00"
    assert ventanas(t, 6) == [(450, 1290)]
    assert ventanas(t, 4) == [(450, 1320)]


def test_off_y_24_7_y_horario_sin_dias():
    assert ventanas("Mo-Sa 13:00-21:00; Su off", 6) == []
    assert ventanas("24/7", 3) == [(0, 1440)]
    assert ventanas("09:00-17:00", 2) == [(540, 1020)]


def test_festivos_se_ignoran():
    t = "Tu-Sa 13:00-17:00,19:00-23:00; Su 13:00-17:00; PH closed"
    assert ventanas(t, 2) == [(780, 1020), (1140, 1380)]
    assert ventanas(t, 0) == []


@pytest.mark.parametrize("texto", [
    "Tu-Sa 18:00 02:00",            # falta el guion
    "PH,Mo-Su 09:00-17:00+",        # horario abierto
    "Su", "Th",                     # solo un dia, sin horas
    "lunes a domingo 13:00 23:00",  # texto libre
    "Mo-Su sunrise-sunset",
    "", None, float("nan"),
])
def test_lo_que_no_se_entiende_devuelve_none_y_no_se_inventa(texto):
    assert parsear_horario_osm(texto) is None


def test_ventanas_lugar_usa_horario_real_si_existe():
    lugar = {"horario_osm": "Tu-Su 10:00-18:00", "hora_apertura": "09:00", "hora_cierre": "20:00",
             "dias_cerrado": ""}
    assert ventanas_lugar(lugar, "lunes") == ([], "osm")                   # cerrado lunes segun OSM
    assert ventanas_lugar(lugar, "sabado") == ([(600, 1080)], "osm")


def test_ventanas_lugar_cae_a_la_estimacion_y_lo_declara():
    lugar = {"horario_osm": float("nan"), "hora_apertura": "10:00", "hora_cierre": "17:00",
             "dias_cerrado": "lunes"}
    assert ventanas_lugar(lugar, "lunes") == ([], "estimado_categoria")
    assert ventanas_lugar(lugar, "martes") == ([(600, 1020)], "estimado_categoria")
    # con la opcion de no usar OSM se ignora el horario real
    lugar["horario_osm"] = "Mo-Su 00:00-24:00"
    assert ventanas_lugar(lugar, "martes", usar_horarios_osm=False)[1] == "estimado_categoria"


def test_dias_y_horas():
    assert indice_dia("Sábado") == 5 and indice_dia("domingo") == 6 and indice_dia("xx") is None
    assert normalizar_dia(float("nan")) == ""
    assert a_min("13:30") == 810 and a_hhmm(810) == "13:30"
