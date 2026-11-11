"""La pagina: globos de kilometros y ruta a pie."""
import re
from pathlib import Path

import pytest

from app.restricciones import FACTOR_RODEO, MAX_KM_CAMINATA, VELOCIDAD_KMH

HTML = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")


def globo(nivel):
    m = re.search(rf'<button[^>]*class="nivel[^"]*"[^>]*data-nivel="{nivel}".*?<span class="globo"[^>]*>(.*?)</span>', HTML, re.S)
    assert m, f"no hay globo para el nivel {nivel}"
    return re.sub(r"<[^>]+>", "", m.group(1))


@pytest.mark.parametrize("nivel, palabra", [(1, "Poco"), (2, "Medio"), (3, "Mucho")])
def test_cada_nivel_tiene_un_globo_con_sus_kilometros(nivel, palabra):
    texto = globo(nivel)
    assert texto.startswith(f"{palabra}: hasta {MAX_KM_CAMINATA[nivel]:.0f} km")     # coincide con el backend
    etiqueta = re.search(rf'<button[^>]*data-nivel="{nivel}"[^>]*>[^<]*<small>(.*?)</small>', HTML)
    assert etiqueta and etiqueta.group(1) == f"hasta {MAX_KM_CAMINATA[nivel]:.0f} km"   # y con la etiqueta del boton


def test_los_minutos_del_globo_corresponden_a_los_km_a_pie():
    """3 km a 5 km/h son 36 min; 6 km, 72 min (1 h 10); 10 km, 120 min (2 h)."""
    assert VELOCIDAD_KMH == 5
    assert "35 min" in globo(1) and "1 h 10 min" in globo(2) and "2 h" in globo(3)


def test_el_selector_viejo_ya_no_existe_y_hay_tres_botones():
    assert 'id="actividad"' not in HTML
    assert len(re.findall(r'class="nivel', HTML)) == 3
    assert 'class="nivel activo" data-nivel="2"' in HTML                              # medio por defecto


def test_los_globos_se_muestran_con_mouse_y_con_toque():
    assert ".nivel:hover .globo" in HTML and ".nivel:focus .globo" in HTML


def test_la_ruta_se_traza_a_pie_y_no_en_carro():
    assert "routed-foot" in HTML
    assert "routed-car" not in HTML and "driving" not in HTML
    assert "?overview=full&geometries=geojson" in HTML
    assert "Ruta a pie por las calles" in HTML
    assert "línea punteada es una ruta aproximada" in HTML                            # respaldo si no carga


def test_muestra_kilometros_y_minutos_caminando():
    assert "km_caminados" in HTML and "traslado_km" in HTML
    assert "A pie desde el anterior" in HTML
    assert "Traslado desde el anterior" not in HTML and "en traslados" not in HTML


def test_el_perfil_manda_el_nivel_elegido():
    assert "nivel_actividad: nivel" in HTML


def test_el_factor_de_rodeo_esta_documentado_en_la_pagina():
    assert "aproximados" in HTML and FACTOR_RODEO > 1
