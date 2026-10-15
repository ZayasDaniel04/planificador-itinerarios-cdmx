"""Voraz y genetico: cumplen las mismas reglas, son validos y reproducibles."""
import pytest

from app.fitness import FITNESS_INVALIDO, desglose_fitness, fitness
from app.genetico import comparar, generar_itinerario_genetico, genetico, preparar, simular
from app.itinerario import (construir_desde_candidatos, construir_pool, generar_itinerario,
                            resumen)
from app.horarios import a_min
from app.perfiles_prueba import perfil_sin_solucion, perfiles_prueba
from app.restricciones import validar_itinerario

GEN, POB = 30, 30          # corridas cortas para que las pruebas sean rapidas
NOMBRES = list(perfiles_prueba())


@pytest.fixture(scope="module")
def corridas(lugares):
    """Por perfil: candidatos y rutas del voraz y de las dos variantes del genetico."""
    out = {}
    for nombre, perfil in perfiles_prueba().items():
        pool = construir_pool(lugares, perfil)
        cands = preparar(pool, perfil)
        ruta_g = construir_desde_candidatos(cands, perfil)
        pos = {c["id"]: i for i, c in enumerate(cands)}
        sem = [pos[p["id"]] for p in ruta_g]
        ga_sem, f_sem, _ = genetico(cands, perfil, sem, POB, GEN, seed=1)
        ga_libre, f_libre, _ = genetico(cands, perfil, None, POB, GEN, seed=1)
        out[nombre] = dict(perfil=perfil, pool=pool, cands=cands, greedy=ruta_g,
                           ga_semilla=ga_sem, f_semilla=f_sem, ga_libre=ga_libre, f_libre=f_libre)
    return out


@pytest.mark.parametrize("nombre", NOMBRES)
@pytest.mark.parametrize("algoritmo", ["greedy", "ga_semilla", "ga_libre"])
def test_todo_itinerario_es_valido(corridas, lugares, nombre, algoritmo):
    c = corridas[nombre]
    ruta = c[algoritmo]
    assert ruta, f"{nombre}: {algoritmo} no encontro itinerario"
    assert validar_itinerario(ruta, c["perfil"], lugares) == []


@pytest.mark.parametrize("nombre", NOMBRES)
def test_presupuesto_horarios_y_sin_repetidos(corridas, nombre):
    c = corridas[nombre]
    p = c["perfil"]
    for ruta in (c["greedy"], c["ga_semilla"], c["ga_libre"]):
        assert sum(x["costo_estimado"] for x in ruta) <= p.presupuesto_por_persona
        assert a_min(ruta[0]["llegada"]) >= a_min(p.hora_inicio)
        assert a_min(ruta[-1]["salida"]) <= a_min(p.hora_fin)
        assert len({x["id"] for x in ruta}) == len(ruta)
        for a, b in zip(ruta, ruta[1:]):                       # nunca se traslapan
            assert a_min(b["llegada"]) >= a_min(a["salida"]) + b["traslado_min"]
        assert [x["orden"] for x in ruta] == list(range(1, len(ruta) + 1))


@pytest.mark.parametrize("nombre", NOMBRES)
def test_las_dos_estrategias_usan_las_mismas_reglas(corridas, nombre):
    """Si el voraz y el genetico compartieran reglas distintas, la ruta del voraz no sobreviviria
    al simulador del genetico. Reproducirla en ese orden debe dar exactamente la misma ruta."""
    c = corridas[nombre]
    pos = {x["id"]: i for i, x in enumerate(c["cands"])}
    reproducida = simular([pos[p["id"]] for p in c["greedy"]], c["cands"], c["perfil"])
    assert [(p["id"], p["llegada"], p["salida"]) for p in reproducida] == \
           [(p["id"], p["llegada"], p["salida"]) for p in c["greedy"]]
    # y al reves: la ruta del genetico tambien se reproduce igual
    ga = c["ga_libre"]
    again = simular([pos[p["id"]] for p in ga], c["cands"], c["perfil"])
    assert [(p["id"], p["llegada"]) for p in again] == [(p["id"], p["llegada"]) for p in ga]


@pytest.mark.parametrize("nombre", NOMBRES)
def test_ambos_eligen_solo_entre_los_candidatos_del_mismo_pool(corridas, nombre):
    c = corridas[nombre]
    ids_pool = set(c["pool"]["id"])
    for ruta in (c["greedy"], c["ga_semilla"], c["ga_libre"]):
        assert {p["id"] for p in ruta} <= ids_pool


@pytest.mark.parametrize("nombre", NOMBRES)
def test_el_genetico_con_semilla_nunca_queda_peor_que_el_voraz(corridas, nombre):
    c = corridas[nombre]
    assert c["f_semilla"] >= fitness(c["greedy"], c["perfil"]) - 1e-9


@pytest.mark.parametrize("nombre", NOMBRES)
def test_fitness_reportado_coincide_con_el_de_la_ruta(corridas, nombre):
    c = corridas[nombre]
    assert c["f_libre"] == pytest.approx(fitness(c["ga_libre"], c["perfil"]))
    assert c["f_semilla"] == pytest.approx(fitness(c["ga_semilla"], c["perfil"]))


# ---------------------------------------------------------------- reproducibilidad
def test_voraz_es_determinista(lugares, perfiles):
    p = perfiles["Pareja romantica"]
    a, b = generar_itinerario(lugares, p), generar_itinerario(lugares, p)
    assert a == b


def test_genetico_misma_semilla_mismo_resultado(corridas):
    c = corridas["Pareja romantica"]
    r1 = genetico(c["cands"], c["perfil"], None, POB, GEN, seed=7)
    r2 = genetico(c["cands"], c["perfil"], None, POB, GEN, seed=7)
    assert r1 == r2


def test_genetico_semillas_distintas_exploran_distinto(corridas):
    c = corridas["Pareja romantica"]
    historiales = {tuple(genetico(c["cands"], c["perfil"], None, POB, 10, seed=s)[2]) for s in range(4)}
    assert len(historiales) > 1


def test_comparar_usa_mismos_candidatos_y_devuelve_validez(lugares, perfiles):
    r = comparar(lugares, perfiles["Solo cultural"], generaciones=GEN, poblacion=POB, seed=3)
    for alg in ("greedy", "genetico"):
        assert r[alg]["violaciones"] == [] and r[alg]["ruta"]
        assert r[alg]["fitness"] == pytest.approx(fitness(r[alg]["ruta"], perfiles["Solo cultural"]))
    again = comparar(lugares, perfiles["Solo cultural"], generaciones=GEN, poblacion=POB, seed=3)
    assert [p["id"] for p in r["genetico"]["ruta"]] == [p["id"] for p in again["genetico"]["ruta"]]
    assert r["genetico"]["historial"] == again["genetico"]["historial"]


# ---------------------------------------------------------------- casos sin solucion y limites
def test_perfil_sin_solucion_devuelve_vacio_sin_fallar(lugares):
    p = perfil_sin_solucion()
    assert comparar(lugares, p) is None
    assert generar_itinerario(lugares, p)["paradas"] == []
    vacio = generar_itinerario_genetico(lugares, p)
    assert vacio["paradas"] == [] and vacio["resumen"]["lugares"] == 0


def test_candidatos_todos_cerrados_no_producen_itinerario(corridas):
    c = corridas["Solo cultural"]
    cerrados = [dict(x, ventanas=[]) for x in c["cands"]]
    assert construir_desde_candidatos(cerrados, c["perfil"]) == []
    ruta, f, hist = genetico(cerrados, c["perfil"], None, 10, 5, seed=0)
    assert ruta == [] and f == FITNESS_INVALIDO and len(hist) == 5


def test_presupuesto_insuficiente_para_todo(corridas):
    c = corridas["Solo cultural"]
    caros = [dict(x, costo=10_000.0) for x in c["cands"]]
    assert construir_desde_candidatos(caros, c["perfil"]) == []
    assert genetico(caros, c["perfil"], None, 10, 5, seed=0)[0] == []


def test_genetico_con_muy_pocos_candidatos(corridas):
    c = corridas["Solo cultural"]
    una = c["cands"][:1]
    ruta, f, _ = genetico(una, c["perfil"], None, 10, 5, seed=0)
    assert len(ruta) <= 1
    ruta0, f0, _ = genetico([], c["perfil"], None, 10, 5, seed=0)
    assert ruta0 == [] and f0 == FITNESS_INVALIDO
    dos = c["cands"][:2]
    assert genetico(dos, c["perfil"], None, 10, 5, seed=0)[0] is not None


def test_itinerario_vacio_vale_menos_que_cualquiera_valido(corridas):
    c = corridas["Solo cultural"]
    assert fitness([], c["perfil"]) == FITNESS_INVALIDO < fitness(c["greedy"], c["perfil"])
    assert resumen([])["lugares"] == 0 and resumen([])["duracion_total_min"] == 0


# ---------------------------------------------------------------- horarios reales y fitness
def test_con_horario_real_no_aparecen_lugares_cerrados_ese_dia(corridas, lugares):
    from app.horarios import ventanas_lugar
    c = corridas["Lunes de museos"]
    por_id = lugares.set_index("id")
    for ruta in (c["greedy"], c["ga_libre"]):
        for p in ruta:
            ventanas, fuente = ventanas_lugar(por_id.loc[p["id"]], "lunes")
            assert ventanas, f'{p["nombre"]} esta cerrado el lunes'
            assert p["horario_fuente"] == fuente


def test_las_paradas_declaran_si_su_horario_es_real_o_estimado(corridas):
    ruta = corridas["Pareja romantica"]["greedy"]
    assert {p["horario_fuente"] for p in ruta} <= {"osm", "estimado_categoria"}
    r = resumen(ruta)
    assert r["paradas_horario_real"] + r["paradas_horario_estimado"] == len(ruta)


def test_desglose_del_fitness_suma_el_total(corridas):
    for c in corridas.values():
        d = desglose_fitness(c["greedy"], c["perfil"])
        assert d["total"] == pytest.approx(fitness(c["greedy"], c["perfil"]))
        assert d["total"] == pytest.approx(sum(v for k, v in d.items() if k != "total"))


def test_fitness_con_un_ejemplo_calculado_a_mano(corridas):
    p = corridas["Pareja romantica"]["perfil"]
    ruta = [
        {"puntaje": 1.0, "traslado_min": 0, "espera_min": 0, "categoria": "museo"},
        {"puntaje": 0.5, "traslado_min": 10, "espera_min": 20, "categoria": "museo"},      # repite categoria
        {"puntaje": 0.8, "traslado_min": 5, "espera_min": 0, "categoria": "restaurante"},   # comida
    ]
    esperado = 2.3 - 0.01 * 15 - 0.005 * 20 + 0.5 - 0.15
    assert fitness(ruta, p) == pytest.approx(esperado)


def test_grupo_nocturno_recibe_bono_si_hay_bar(corridas):
    p = corridas["Amigos de fiesta"]["perfil"]
    con_bar = [{"puntaje": 1.0, "traslado_min": 0, "espera_min": 0, "categoria": "bar"}]
    sin_bar = [{"puntaje": 1.0, "traslado_min": 0, "espera_min": 0, "categoria": "museo"}]
    assert fitness(con_bar, p) - fitness(sin_bar, p) == pytest.approx(0.4)
    de_dia = corridas["Solo cultural"]["perfil"]
    assert fitness(con_bar, de_dia) == pytest.approx(fitness(sin_bar, de_dia))
