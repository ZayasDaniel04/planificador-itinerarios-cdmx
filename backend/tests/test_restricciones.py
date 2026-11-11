"""Restricciones compartidas: revisar_parada y validar_itinerario."""
import copy

import pytest

from app.itinerario import generar_itinerario
from app.perfiles import Perfil
from app.restricciones import (EstadoDia, ESPERA_MAX, FACTOR_RODEO, MAX_KM_CAMINATA, MIN_TRASLADO,
                               VELOCIDAD_KMH, agregar_parada, distancia_km, limite_km,
                               normalizar_nombre, revisar_parada, traslado_km, traslado_min,
                               validar_itinerario)

CENTRO = (19.4326, -99.1332)


def cand(id, nombre="Lugar", cat="museo", lat=CENTRO[0], lon=CENTRO[1], ventanas=((540, 1080),),
         dur=60, costo=50.0, puntaje=1.0):
    return {"id": id, "nombre": nombre, "nombre_norm": normalizar_nombre(nombre), "categoria": cat,
            "zona": "Centro Historico", "lat": lat, "lon": lon, "ventanas": list(ventanas),
            "horario_fuente": "estimado_categoria", "duracion": dur, "costo": costo,
            "costo_fuente": "estimado_categoria", "puntaje": puntaje}


@pytest.fixture
def perfil():
    return Perfil(tipo_grupo="amigos", presupuesto_por_persona=500, hora_inicio="10:00", hora_fin="20:00")


def motivo(estado, c, perfil, **kw):
    datos, m = revisar_parada(estado, c, perfil, **kw)
    return m if datos is None else "ok"


def test_acepta_un_lugar_que_cabe_y_calcula_la_hora_de_inicio(perfil):
    datos, m = revisar_parada(EstadoDia(perfil), cand(1, ventanas=((660, 1080),)), perfil)
    assert m == "" and datos == (660, 720, 0, 60)        # abre a las 11:00: espera 60 min


@pytest.mark.parametrize("c, esperado", [
    (cand(1, ventanas=((540, 630),), dur=60), "fuera_de_horario"),       # cierra antes de terminar
    (cand(1, ventanas=((600, 1080),), dur=60, costo=501), "excede_presupuesto"),
    (cand(1, ventanas=((840, 1080),)), "espera_excesiva"),               # abre a las 14:00, espera 240
    (cand(1, ventanas=()), "fuera_de_horario"),                          # cerrado ese dia
])
def test_rechaza_cuando_incumple(perfil, c, esperado):
    assert motivo(EstadoDia(perfil), c, perfil) == esperado


def test_rechaza_si_termina_despues_de_la_hora_de_fin(perfil):
    e = EstadoDia(perfil)
    e.reloj = 18 * 60 + 30                                # ya son las 18:30
    c = cand(1, ventanas=((1140, 1320),), dur=90)         # abre 19:00, dura 90 -> 20:30 > 20:00
    assert motivo(e, c, perfil) == "excede_hora_fin"
    assert motivo(e, cand(2, ventanas=((1140, 1320),), dur=60), perfil) == "ok"   # termina justo 20:00


def test_no_repite_lugares_ni_por_id_ni_por_nombre(perfil):
    e = EstadoDia(perfil)
    datos, _ = revisar_parada(e, cand(1, "Cafe El Pendulo", "cafeteria"), perfil)
    agregar_parada(e, cand(1, "Cafe El Pendulo", "cafeteria"), datos)
    assert motivo(e, cand(1, "Otro", "museo"), perfil) == "lugar_repetido"
    assert motivo(e, cand(2, "CAFÉ  el péndulo", "museo"), perfil) == "lugar_repetido"


def test_limite_por_categoria(perfil):
    e = EstadoDia(perfil)
    agregar_parada(e, cand(1, "A", "cafeteria"), revisar_parada(e, cand(1, "A", "cafeteria"), perfil)[0])
    assert motivo(e, cand(2, "B", "cafeteria"), perfil) == "limite_por_categoria"   # maximo 1 cafeteria
    for i, n in ((3, "C"), (4, "D")):
        c = cand(i, n, "museo")
        d, _ = revisar_parada(e, c, perfil)
        agregar_parada(e, c, d)
    assert motivo(e, cand(5, "E", "museo"), perfil) == "limite_por_categoria"       # maximo 2 por defecto


def test_una_sola_comida_fuerte_y_dentro_de_su_ventana(perfil):
    e = EstadoDia(perfil)
    e.reloj = 11 * 60                                     # son las 11:00
    c = cand(1, "Fonda", "restaurante", ventanas=((540, 1380),), dur=75)
    datos, _ = revisar_parada(e, c, perfil)
    assert datos[0] == 750 and datos[3] == 90             # se empuja a las 12:30 (espera 90 min)
    agregar_parada(e, c, datos)
    assert motivo(e, cand(2, "Mercado", "mercado", ventanas=((540, 1380),)), perfil) == "segunda_comida_fuerte"
    e2 = EstadoDia(perfil)
    e2.reloj = 16 * 60 + 30                               # son las 16:30: ya paso la ventana de comida
    assert motivo(e2, cand(3, "Cena", "restaurante", ventanas=((540, 1380),)), perfil) == "fuera_de_ventana_de_comida"


def test_usa_la_segunda_ventana_si_la_primera_no_alcanza(perfil):
    c = cand(1, ventanas=((540, 630), (840, 1080)), dur=60)
    e = EstadoDia(perfil)
    e.reloj = 13 * 60                                     # ya son las 13:00: la primera ventana paso
    datos, _ = revisar_parada(e, c, perfil)
    assert datos[0] == 840


def test_espera_max_solo_puede_endurecerse(perfil):
    c = cand(1, ventanas=((690, 1080),))                  # abre 11:30, espera 90 min
    assert motivo(EstadoDia(perfil), c, perfil, espera_max=45) == "espera_excesiva"
    assert motivo(EstadoDia(perfil), c, perfil, espera_max=10_000) == "ok"
    c2 = cand(2, ventanas=((840, 1080),))                 # espera 240 > ESPERA_MAX aunque se pida mas
    assert motivo(EstadoDia(perfil), c2, perfil, espera_max=10_000) == "espera_excesiva"
    assert ESPERA_MAX == 120


def test_el_gasto_acumulado_cuenta(perfil):
    e = EstadoDia(perfil)
    for i, costo in ((1, 300), (2, 150)):
        c = cand(i, f"L{i}", "museo" if i == 1 else "parque", costo=costo)
        d, _ = revisar_parada(e, c, perfil)
        agregar_parada(e, c, d)
    assert motivo(e, cand(3, "L3", "galeria", costo=51), perfil) == "excede_presupuesto"
    assert motivo(e, cand(4, "L4", "galeria", costo=50), perfil) == "ok"        # justo el presupuesto


def test_el_traslado_se_suma_y_tiene_minimo(perfil):
    a = cand(1, lat=19.4326, lon=-99.1332)
    b = cand(2, "Cerca", lat=19.4450, lon=-99.1332)       # ~1.4 km al norte
    assert traslado_min(a, a) == MIN_TRASLADO == 5
    assert traslado_min(a, b) > 15
    e = EstadoDia(perfil)
    agregar_parada(e, a, revisar_parada(e, a, perfil)[0])
    datos, _ = revisar_parada(e, b, perfil)
    assert datos[2] == traslado_min(a, b) and datos[0] == e.reloj + datos[2]


def test_los_traslados_son_caminando_y_no_en_vehiculo():
    """Antes se calculaban a 18 km/h (vehiculo). Ahora son a pie: 5 km/h por calles."""
    assert VELOCIDAD_KMH <= 6 and FACTOR_RODEO >= 1.0
    a, b = cand(1, lat=19.4326, lon=-99.1332), cand(2, "Otro", lat=19.4326, lon=-99.1332 + 0.018)  # ~1.9 km
    recto = distancia_km(a["lat"], a["lon"], b["lat"], b["lon"])
    assert traslado_km(a, b) == pytest.approx(recto * FACTOR_RODEO)             # las calles rodean manzanas
    assert traslado_min(a, b) == round(traslado_km(a, b) / VELOCIDAD_KMH * 60)
    assert 20 <= traslado_min(a, b) <= 40                                       # ~2 km a pie, no ~7 min en vehiculo


def test_limite_de_kilometros_por_nivel_de_caminata():
    assert MAX_KM_CAMINATA == {1: 3.0, 2: 6.0, 3: 10.0}
    for nivel, km in MAX_KM_CAMINATA.items():
        assert limite_km(Perfil(nivel_actividad=nivel)) == km


def test_rechaza_si_se_pasa_del_limite_de_caminata():
    cerca = cand(1, "A")
    lejos = cand(2, "B", lat=CENTRO[0] + 0.030)           # ~3.3 km en linea recta, ~4.3 km por calles
    for nivel, esperado in ((1, "excede_caminata"), (2, "ok"), (3, "ok")):
        p = Perfil(tipo_grupo="amigos", presupuesto_por_persona=500, hora_inicio="09:00",
                   hora_fin="23:00", nivel_actividad=nivel)
        e = EstadoDia(p)
        agregar_parada(e, cerca, revisar_parada(e, cerca, p)[0])
        assert motivo(e, lejos, p) == esperado, nivel


def test_el_limite_cuenta_los_kilometros_acumulados():
    p = Perfil(tipo_grupo="amigos", presupuesto_por_persona=500, hora_inicio="09:00", hora_fin="23:00",
               nivel_actividad=1)                         # 3 km
    e = EstadoDia(p)
    lugares = [cand(i, f"L{i}", ("museo", "parque", "galeria", "mirador")[i % 4],
                    lat=CENTRO[0] + 0.007 * i) for i in range(5)]     # saltos de ~0.8 km a pie
    metidos = 0
    for c in lugares:
        d, m = revisar_parada(e, c, p)
        if d is None:
            assert m == "excede_caminata"
            break
        agregar_parada(e, c, d)
        metidos += 1
    assert 2 <= metidos < 5 and e.km <= 3.0
    assert e.ruta[-1]["traslado_km"] > 0 and e.ruta[0]["traslado_km"] == 0
    assert sum(x["traslado_km"] for x in e.ruta) == pytest.approx(e.km, abs=0.05)


# ---------------------------------------------------------------- validar_itinerario
@pytest.fixture(scope="module")
def ruta_valida(lugares):
    p = Perfil(tipo_grupo="pareja", personas=2, presupuesto_por_persona=800, nivel_actividad=2,
               hora_inicio="10:00", hora_fin="20:00", intereses={"comida": 0.9, "arte": 0.7})
    ruta = generar_itinerario(lugares, p)["paradas"]
    assert len(ruta) >= 4
    return p, ruta


def test_una_ruta_correcta_no_tiene_violaciones(ruta_valida, lugares):
    p, ruta = ruta_valida
    assert validar_itinerario(ruta, p, lugares) == []
    assert validar_itinerario([], p, lugares) == []       # ruta vacia = "no hay solucion", no es error


def mutar(ruta, i, **cambios):
    r = copy.deepcopy(ruta)
    r[i].update(cambios)
    return r


@pytest.mark.parametrize("cambio, texto", [
    ({"salida": "23:00"}, "despues de la hora de fin"),
    ({"costo_estimado": 5000.0}, "excede el presupuesto"),
    ({"duracion_min": 500}, "deberia durar"),
    ({"llegada": "03:00", "salida": "04:00", "duracion_min": 60}, "horario de apertura"),
])
def test_detecta_cada_tipo_de_violacion(ruta_valida, lugares, cambio, texto):
    p, ruta = ruta_valida
    problemas = validar_itinerario(mutar(ruta, 1, **cambio), p, lugares)
    assert any(texto in x for x in problemas), problemas


def test_detecta_lugares_repetidos_y_traslado_imposible(ruta_valida, lugares):
    p, ruta = ruta_valida
    r = copy.deepcopy(ruta)
    r.append(copy.deepcopy(r[0]))
    assert any("repetido" in x for x in validar_itinerario(r, p, lugares))
    r2 = copy.deepcopy(ruta)
    r2[2]["llegada"] = r2[1]["salida"]                    # llega sin tiempo de traslado
    r2[2]["salida"] = r2[1]["salida"][:-2] + "59"
    assert any("traslado" in x or "dura" in x for x in validar_itinerario(r2, p, lugares))


def test_detecta_dos_comidas_fuertes_y_limite_de_categoria(ruta_valida, lugares):
    p, ruta = ruta_valida
    extra = copy.deepcopy(ruta[0])
    extra.update({"id": 999991, "nombre": "Otro Restaurante", "categoria": "restaurante",
                  "llegada": "19:00", "salida": "19:30", "duracion_min": 30, "costo_estimado": 0.0})
    problemas = validar_itinerario(ruta + [extra], p, lugares)
    assert any("comida" in x for x in problemas)


def test_detecta_filtros_del_perfil(lugares):
    """Un bar en un itinerario con ninos incumple las reglas del perfil."""
    p = Perfil(tipo_grupo="familia", hay_ninos=True, presupuesto_por_persona=900,
               hora_inicio="10:00", hora_fin="23:00")
    bar = lugares[lugares["categoria"] == "bar"].iloc[0]
    ruta = [{"orden": 1, "id": int(bar["id"]), "nombre": bar["nombre"], "categoria": "bar",
             "zona": bar["zona"], "lat": bar["lat"], "lon": bar["lon"], "llegada": "21:00",
             "salida": "22:30", "duracion_min": int(bar["duracion_min"]), "traslado_min": 0,
             "espera_min": 0, "costo_estimado": float(bar["costo_estimado"]), "puntaje": 1.0}]
    assert any("filtros del perfil" in x for x in validar_itinerario(ruta, p, lugares))


def _par_lejano(lugares, km_min, km_max):
    """Primer par de lugares (no comida) cuya caminata esta entre km_min y km_max."""
    for _, a in lugares[lugares["categoria"] == "parque"].iterrows():
        for _, b in lugares[lugares["categoria"] == "museo"].iterrows():
            if km_min < traslado_km(a, b) < km_max:
                return a, b
    raise AssertionError("no hay un par de lugares a esa distancia")


def _ruta_de_dos(a, b):
    ruta, reloj, anterior = [], 9 * 60, None
    for i, l in enumerate((a, b), 1):
        tras = traslado_min(anterior, l) if anterior is not None else 0
        ini = reloj + tras
        fin = ini + int(l["duracion_min"])
        ruta.append({"orden": i, "id": int(l["id"]), "nombre": l["nombre"], "categoria": l["categoria"],
                     "zona": l["zona"], "lat": l["lat"], "lon": l["lon"],
                     "llegada": f"{ini // 60:02d}:{ini % 60:02d}", "salida": f"{fin // 60:02d}:{fin % 60:02d}",
                     "duracion_min": int(l["duracion_min"]), "traslado_min": int(tras), "espera_min": 0,
                     "costo_estimado": float(l["costo_estimado"]), "puntaje": 1.0})
        reloj, anterior = fin, l
    return ruta


def test_detecta_que_se_camina_mas_del_limite(lugares):
    a, b = _par_lejano(lugares, 3.2, 9.0)                       # mas de 3 km, menos de 10
    ruta = _ruta_de_dos(a, b)
    base = dict(tipo_grupo="amigos", presupuesto_por_persona=900, hora_inicio="08:00", hora_fin="23:59",
                dia_semana="sabado")
    poco = validar_itinerario(ruta, Perfil(**base, nivel_actividad=1), lugares)
    assert any("se caminan" in x and "limite de 3 km" in x for x in poco), poco
    assert not any("se caminan" in x for x in validar_itinerario(ruta, Perfil(**base, nivel_actividad=3), lugares))
