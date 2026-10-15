"""Mide como afectan los pesos del puntaje a las recomendaciones (analisis de sensibilidad).

Para cada perfil de prueba se compara el resultado con los pesos por defecto contra variantes:
  * un peso a la vez multiplicado por 0 (se apaga), 0.5, 1.5 y 2
  * "esquema_original": la formula anterior, que usaba "tiene sitio web" como popularidad
    (0.60*sim + 0.25*reglas + 0.10*sitio_web - 0.15*precio)

Metricas contra la linea base (pesos por defecto):
  traslape_top10     fraccion de lugares compartidos entre ambos top 10 (Jaccard; 1 = iguales)
  spearman           correlacion de rangos de TODOS los lugares validos (1 = mismo orden)
  costo_medio_top10  gasto estimado medio por persona de los 10 mejores
  categorias_top10   cuantas categorias distintas hay en el top 10
  pct_horario_real   % de los 10 mejores con horario real de OSM
  traslape_dia       Jaccard entre los itinerarios del voraz construidos con cada variante
  lugares_dia        lugares del itinerario del voraz

Salida: data/resultados/sensibilidad_pesos.csv

Uso (desde backend/):
    python evaluar_pesos.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from app.itinerario import construir, POOL_N, POOL_MAX_POR_CATEGORIA
from app.perfiles_prueba import perfiles_prueba
from app.recomendador import (PESOS_POR_DEFECTO, cargar_lugares, puntuar, seleccionar_diverso)

SALIDA = Path(__file__).resolve().parents[1] / "data" / "resultados"
FACTORES = (0.0, 0.5, 1.5, 2.0)
PESOS_VARIABLES = ("similitud", "reglas", "confianza", "precio")


def variantes():
    v = {"base": {}}
    for peso in PESOS_VARIABLES:
        for f in FACTORES:
            v[f"{peso} x{f:g}"] = {peso: PESOS_POR_DEFECTO[peso] * f}
    return v


def puntuar_original(df, perfil):
    """Reproduce la formula anterior (sitio web como popularidad) con los mismos componentes."""
    validos = puntuar(df, perfil, {"confianza": 0.0})
    if validos.empty:
        return validos
    web = validos["sitio_web"].notna().astype(float)
    validos["puntaje"] = (0.60 * validos["sim"] + 0.25 * validos["ajuste"] + 0.10 * web
                          - 0.15 * validos["precio_rel"])
    return validos.sort_values(["puntaje", "id"], ascending=[False, True], kind="stable")


def evaluar_variante(validos, perfil):
    """Top 10, pool de 40 e itinerario del voraz a partir de un DataFrame ya puntuado."""
    top = seleccionar_diverso(validos, 10, 3)
    pool = seleccionar_diverso(validos, POOL_N, POOL_MAX_POR_CATEGORIA)
    ruta = construir(pool, perfil)
    return validos, top, {p["id"] for p in ruta}, len(ruta)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 1.0


def main():
    df = cargar_lugares()
    filas = []
    for nombre, perfil in perfiles_prueba().items():
        base = puntuar(df, perfil)
        if base.empty:
            continue
        _, top_b, dia_b, _ = evaluar_variante(base, perfil)
        casos = {k: puntuar(df, perfil, w) for k, w in variantes().items()}
        casos["esquema_original"] = puntuar_original(df, perfil)
        for etiqueta, validos in casos.items():
            _, top, dia, n_dia = evaluar_variante(validos, perfil)
            comunes = base.index.intersection(validos.index)
            rho = spearmanr(base.loc[comunes, "puntaje"], validos.loc[comunes, "puntaje"]).statistic
            filas.append({
                "perfil": nombre, "variante": etiqueta,
                "traslape_top10": round(jaccard(top["id"], top_b["id"]), 3),
                "spearman": round(float(rho), 3) if not np.isnan(rho) else np.nan,
                "costo_medio_top10": round(float(top["costo_estimado"].mean()), 1),
                "categorias_top10": int(top["categoria"].nunique()),
                "pct_horario_real": round(100 * float((top["horario_fuente"] == "osm").mean())
                                          if "horario_fuente" in top else np.nan, 1),
                "traslape_dia": round(jaccard(dia, dia_b), 3),
                "lugares_dia": n_dia,
            })
    res = pd.DataFrame(filas)
    SALIDA.mkdir(parents=True, exist_ok=True)
    res.to_csv(SALIDA / "sensibilidad_pesos.csv", index=False, encoding="utf-8-sig")

    resumen = (res[res["variante"] != "base"].groupby("variante", sort=False)
               [["traslape_top10", "spearman", "traslape_dia", "costo_medio_top10",
                 "categorias_top10", "pct_horario_real"]].mean().round(3))
    print(f"Promedio sobre {res['perfil'].nunique()} perfiles, contra los pesos por defecto "
          f"{PESOS_POR_DEFECTO}\n")
    print(resumen.to_string())
    print(f"\nDetalle por perfil: {SALIDA / 'sensibilidad_pesos.csv'}")


if __name__ == "__main__":
    main()
