"""Endpoints principales de la API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

PERFIL = {"tipo_grupo": "pareja", "personas": 2, "presupuesto_por_persona": 800, "nivel_actividad": 1,
          "zona": "", "dia_semana": "sabado", "hora_inicio": "10:00", "hora_fin": "21:00",
          "intereses": {"comida": 0.9, "arte": 0.7, "fotografia": 0.6}}
CAMPOS_PARADA = {"orden", "id", "nombre", "categoria", "zona", "lat", "lon", "llegada", "salida",
                 "duracion_min", "traslado_min", "espera_min", "costo_estimado", "puntaje"}
CAMPOS_RESUMEN = {"lugares", "gasto_por_persona", "traslado_total_min", "espera_total_min",
                  "incluye_comida", "hora_inicio", "hora_fin"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_raiz(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["lugares"] >= 250 and "funcionando" in r.json()["mensaje"]


def test_recomendar(client):
    r = client.post("/recomendar", json={**PERFIL, "n": 6})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == len(d["lugares"]) == 6
    primero = d["lugares"][0]
    assert {"id", "nombre", "categoria", "puntaje", "sim", "ajuste", "confianza", "precio_rel"} <= set(primero)
    puntajes = [x["puntaje"] for x in d["lugares"]]
    assert puntajes == sorted(puntajes, reverse=True)


def test_recomendar_respeta_los_filtros_del_perfil(client):
    r = client.post("/recomendar", json={"tipo_grupo": "familia", "hay_ninos": True, "n": 30,
                                         "presupuesto_por_persona": 600, "intereses": {"naturaleza": 0.9}})
    assert r.status_code == 200
    assert "bar" not in {x["categoria"] for x in r.json()["lugares"]}


@pytest.mark.parametrize("algoritmo", ["greedy", "genetico"])
def test_itinerario_es_valido_con_cada_algoritmo(client, algoritmo):
    r = client.post("/itinerario", json={**PERFIL, "algoritmo": algoritmo})
    assert r.status_code == 200
    d = r.json()
    assert d["algoritmo"] == algoritmo and d["valido"] is True and d["violaciones"] == []
    assert d["paradas"] and CAMPOS_PARADA <= set(d["paradas"][0])
    assert CAMPOS_RESUMEN <= set(d["resumen"])
    assert d["resumen"]["lugares"] == len(d["paradas"])
    assert d["resumen"]["gasto_por_persona"] <= PERFIL["presupuesto_por_persona"]
    assert d["paradas"][0]["llegada"] >= PERFIL["hora_inicio"]
    assert d["paradas"][-1]["salida"] <= PERFIL["hora_fin"]
    assert len({p["id"] for p in d["paradas"]}) == len(d["paradas"])


def test_el_valor_por_defecto_sigue_siendo_el_voraz(client):
    """El frontend actual no manda 'algoritmo': debe seguir recibiendo el itinerario del voraz."""
    r = client.post("/itinerario", json=PERFIL).json()
    assert r["algoritmo"] == "greedy"
    assert r["paradas"] == client.post("/itinerario", json={**PERFIL, "algoritmo": "greedy"}).json()["paradas"]


def test_reproducibilidad_por_la_api(client):
    cuerpo = {**PERFIL, "algoritmo": "genetico", "semilla": 11}
    a, b = client.post("/itinerario", json=cuerpo).json(), client.post("/itinerario", json=cuerpo).json()
    assert a == b
    v = client.post("/itinerario", json=PERFIL).json()
    assert v == client.post("/itinerario", json=PERFIL).json()


def test_sin_solucion_devuelve_200_vacio_con_mensaje(client):
    r = client.post("/itinerario", json={**PERFIL, "presupuesto_por_persona": 0,
                                         "hora_inicio": "10:00", "hora_fin": "10:20"})
    assert r.status_code == 200
    d = r.json()
    assert d["paradas"] == [] and d["resumen"]["lugares"] == 0 and d["mensaje"]
    assert d["valido"] is True                    # vacio no incumple nada; el mensaje explica por que
    g = client.post("/itinerario", json={**PERFIL, "algoritmo": "genetico", "presupuesto_por_persona": 0,
                                         "hora_inicio": "10:00", "hora_fin": "10:20"})
    assert g.status_code == 200 and g.json()["paradas"] == []


@pytest.mark.parametrize("cambio, texto", [
    ({"hora_inicio": "20:00", "hora_fin": "10:00"}, "hora_fin"),
    ({"hora_inicio": "25:00"}, "hora_inicio"),
    ({"hora_fin": "tarde"}, "hora_fin"),
    ({"presupuesto_por_persona": -10}, "presupuesto"),
    ({"tipo_grupo": "alienigenas"}, "tipo_grupo"),
    ({"zona": "Narnia"}, "zona"),
    ({"dia_semana": "sunday"}, "dia_semana"),
    ({"nivel_actividad": 7}, "nivel_actividad"),
    ({"personas": 0}, "personas"),
    ({"intereses": {"surf": 1.0}}, "interes"),
    ({"intereses": {"comida": 3.0}}, "entre 0 y 1"),
])
def test_perfil_invalido_responde_422_con_el_motivo(client, cambio, texto):
    # /recomendar no recibe horas, asi que los campos de hora solo se validan en /itinerario
    rutas = ("/itinerario",) if any(k.startswith("hora") for k in cambio) else ("/itinerario", "/recomendar")
    for ruta in rutas:
        r = client.post(ruta, json={**PERFIL, **cambio})
        assert r.status_code == 422
        assert any(texto in e for e in r.json()["detail"]), r.json()


def test_algoritmo_desconocido_responde_422(client):
    assert client.post("/itinerario", json={**PERFIL, "algoritmo": "quantum"}).status_code == 422


def test_lunes_no_incluye_lugares_cerrados(client, lugares):
    from app.horarios import ventanas_lugar
    r = client.post("/itinerario", json={**PERFIL, "dia_semana": "lunes",
                                         "intereses": {"cultura": 0.9, "arte": 0.9}}).json()
    assert r["valido"] and r["paradas"]
    por_id = lugares.set_index("id")
    assert all(ventanas_lugar(por_id.loc[p["id"]], "lunes")[0] for p in r["paradas"])
