"""Compara el algoritmo voraz y el genetico con evidencia experimental.

Metodologia:
  * Mismos perfiles, MISMOS candidatos (un solo pool por perfil), mismas restricciones
    (restricciones.revisar_parada) y misma funcion fitness para todos los algoritmos.
  * El voraz es determinista: se corre una vez por perfil.
  * El genetico es aleatorio: se corre con varias semillas (--semillas, por defecto 10) y en
    dos variantes:
        genetico_con_semilla_greedy  el voraz entra a la poblacion inicial (no puede quedar peor)
        genetico_sin_semilla         poblacion inicial aleatoria (comparacion justa del algoritmo)
  * Lineas base, tambien con las mismas restricciones:
        aleatorio           orden aleatorio de los candidatos (una corrida por semilla)
        orden_por_puntaje   candidatos en el orden del recomendador, sin optimizar
  * Cada itinerario se valida con restricciones.validar_itinerario (independiente del algoritmo).
  * Se registra: validez, fitness, lugares, gasto y % del presupuesto, duracion total, traslado,
    espera y tiempo de ejecucion.

Salida (carpeta data/resultados/): comparacion_detalle.csv (cada corrida),
comparacion_resumen.csv (por perfil y algoritmo) y comparacion.json (todo + conclusiones).

Uso (desde backend/):
    python comparar_algoritmos.py
    python comparar_algoritmos.py --semillas 5 --generaciones 40     # mas rapido
"""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd

from app.genetico import genetico, simular, preparar, POBLACION, GENERACIONES
from app.itinerario import construir_desde_candidatos, construir_pool, resumen
from app.fitness import fitness
from app.perfiles_prueba import perfiles_prueba
from app.recomendador import cargar_lugares, RUTA_DATOS
from app.restricciones import validar_itinerario

SALIDA = Path(__file__).resolve().parents[1] / "data" / "resultados"
ORDEN_ALGORITMOS = ["aleatorio", "orden_por_puntaje", "greedy",
                    "genetico_sin_semilla", "genetico_con_semilla_greedy"]


def registrar(filas, perfil_nombre, perfil, df, algoritmo, semilla, ruta, segundos):
    r = resumen(ruta)
    problemas = validar_itinerario(ruta, perfil, df)
    con_solucion = len(ruta) > 0
    filas.append({
        "perfil": perfil_nombre, "algoritmo": algoritmo, "semilla": semilla,
        "con_solucion": con_solucion,
        "valido": con_solucion and not problemas,
        "violaciones": len(problemas),
        "fitness": fitness(ruta, perfil) if con_solucion else np.nan,
        "lugares": r["lugares"],
        "gasto_por_persona": r["gasto_por_persona"],
        "presupuesto_usado_pct": round(100 * r["gasto_por_persona"] / perfil.presupuesto_por_persona, 1)
        if perfil.presupuesto_por_persona > 0 else np.nan,
        "duracion_total_min": r["duracion_total_min"],
        "tiempo_en_lugares_min": r["tiempo_en_lugares_min"],
        "traslado_total_min": r["traslado_total_min"],
        "espera_total_min": r["espera_total_min"],
        "segundos": round(segundos, 4),
    })


def correr(df, semillas, generaciones, poblacion):
    filas, rutas_ejemplo = [], {}
    for nombre, perfil in perfiles_prueba().items():
        pool = construir_pool(df, perfil)
        if pool.empty:
            print(f"{nombre}: ningun lugar pasa los filtros, se omite")
            continue
        candidatos = preparar(pool, perfil)          # MISMOS candidatos para todos
        n = len(candidatos)

        t0 = time.perf_counter()
        ruta_g = construir_desde_candidatos(candidatos, perfil)
        registrar(filas, nombre, perfil, df, "greedy", None, ruta_g, time.perf_counter() - t0)
        rutas_ejemplo[nombre] = {"greedy": ruta_g}

        t0 = time.perf_counter()
        ruta_p = simular(list(range(n)), candidatos, perfil)
        registrar(filas, nombre, perfil, df, "orden_por_puntaje", None, ruta_p, time.perf_counter() - t0)

        pos = {c["id"]: i for i, c in enumerate(candidatos)}
        semilla_greedy = [pos[p["id"]] for p in ruta_g] if ruta_g else None
        for s in range(semillas):
            rnd = random.Random(s)
            orden = list(range(n))
            rnd.shuffle(orden)
            t0 = time.perf_counter()
            ruta_a = simular(orden, candidatos, perfil)
            registrar(filas, nombre, perfil, df, "aleatorio", s, ruta_a, time.perf_counter() - t0)

            for algoritmo, sem in (("genetico_sin_semilla", None),
                                   ("genetico_con_semilla_greedy", semilla_greedy)):
                t0 = time.perf_counter()
                ruta, _, _ = genetico(candidatos, perfil, sem, poblacion, generaciones, seed=s)
                registrar(filas, nombre, perfil, df, algoritmo, s, ruta, time.perf_counter() - t0)
                if s == 0:
                    rutas_ejemplo[nombre][algoritmo] = ruta
        print(f"  {nombre:22} listo ({n} candidatos)")
    return pd.DataFrame(filas), rutas_ejemplo


def resumir(detalle):
    """Media, desviacion y extremos por perfil y algoritmo."""
    g = detalle.groupby(["perfil", "algoritmo"], sort=False)
    r = g.agg(corridas=("fitness", "size"),
              validas=("valido", "sum"),
              con_solucion=("con_solucion", "sum"),
              fitness_media=("fitness", "mean"), fitness_desv=("fitness", "std"),
              fitness_min=("fitness", "min"), fitness_max=("fitness", "max"),
              lugares_media=("lugares", "mean"),
              gasto_media=("gasto_por_persona", "mean"),
              presupuesto_usado_pct_media=("presupuesto_usado_pct", "mean"),
              duracion_total_media=("duracion_total_min", "mean"),
              traslado_media=("traslado_total_min", "mean"),
              espera_media=("espera_total_min", "mean"),
              segundos_media=("segundos", "mean")).reset_index()
    r["algoritmo"] = pd.Categorical(r["algoritmo"], ORDEN_ALGORITMOS, ordered=True)
    return r.sort_values(["perfil", "algoritmo"], kind="stable").round(3)


def conclusiones(resumen_df, detalle):
    """Conclusiones SOLO con lo que muestran los datos (sin declarar ganador por intuicion)."""
    out = {"regla": ("A supera a B en un perfil solo si el PEOR resultado de A (minimo entre "
                     "semillas) es mayor que el mejor de B (maximo entre semillas); si se "
                     "traslapan, es 'sin diferencia clara'. A nivel global se usa la prueba de "
                     "Wilcoxon sobre las medias por perfil (p < 0.05)."),
           "por_perfil": {}, "global": {}}
    pares = [("genetico_sin_semilla", "greedy"), ("genetico_con_semilla_greedy", "greedy"),
             ("genetico_sin_semilla", "aleatorio"), ("greedy", "aleatorio")]
    piv = resumen_df.set_index(["perfil", "algoritmo"])
    for a, b in pares:
        veredictos, medias_a, medias_b = {}, [], []
        for perfil in resumen_df["perfil"].unique():
            try:
                ra, rb = piv.loc[(perfil, a)], piv.loc[(perfil, b)]
            except KeyError:
                continue
            if np.isnan(ra["fitness_media"]) or np.isnan(rb["fitness_media"]):
                veredictos[perfil] = "sin solucion en alguno"
                continue
            if ra["fitness_min"] > rb["fitness_max"]:
                v = f"{a} supera a {b}"
            elif rb["fitness_min"] > ra["fitness_max"]:
                v = f"{b} supera a {a}"
            else:
                v = "sin diferencia clara"
            veredictos[perfil] = v
            medias_a.append(ra["fitness_media"])
            medias_b.append(rb["fitness_media"])
        clave = f"{a} vs {b}"
        out["por_perfil"][clave] = veredictos
        glob = {"perfiles_comparados": len(medias_a)}
        if len(medias_a) >= 6:
            from scipy.stats import wilcoxon
            dif = np.array(medias_a) - np.array(medias_b)
            glob["diferencia_media_fitness"] = round(float(dif.mean()), 3)
            if np.allclose(dif, 0):
                glob["wilcoxon_p"] = 1.0
            else:
                glob["wilcoxon_p"] = round(float(wilcoxon(medias_a, medias_b).pvalue), 4)
            glob["conclusion"] = (f"{a} > {b} (evidencia, p<0.05)" if glob["wilcoxon_p"] < 0.05 and dif.mean() > 0
                                  else f"{b} > {a} (evidencia, p<0.05)" if glob["wilcoxon_p"] < 0.05
                                  else "no concluyente")
        else:
            glob["conclusion"] = "muestra insuficiente"
        out["global"][clave] = glob
    return out


def imprimir(resumen_df, concl, detalle):
    print(f"\n{'Perfil':22} {'Algoritmo':28} {'Val':>4} {'Fitness (media ± desv)':>23} "
          f"{'Lug':>5} {'Gasto%':>7} {'Dur':>5} {'Tras':>5} {'Esp':>5} {'Seg':>6}")
    for _, r in resumen_df.iterrows():
        f = f"{r.fitness_media:6.2f} ± {0 if np.isnan(r.fitness_desv) else r.fitness_desv:4.2f}"
        print(f"{r.perfil:22} {r.algoritmo:28} {int(r.validas):>2}/{int(r.corridas):<2} {f:>23} "
              f"{r.lugares_media:5.1f} {r.presupuesto_usado_pct_media:7.1f} {r.duracion_total_media:5.0f} "
              f"{r.traslado_media:5.0f} {r.espera_media:5.0f} {r.segundos_media:6.3f}")
    print("\n=== Validez ===")
    total = len(detalle)
    print(f"Itinerarios con solucion: {int(detalle.con_solucion.sum())}/{total}; "
          f"validos segun la validacion independiente: {int(detalle.valido.sum())}/{int(detalle.con_solucion.sum())}")
    print("\n=== Conclusiones (regla: " + concl["regla"] + ") ===")
    for clave, g in concl["global"].items():
        extra = "" if "wilcoxon_p" not in g else f" | dif. media {g['diferencia_media_fitness']:+.3f}, p={g['wilcoxon_p']}"
        print(f"{clave:55} {g['conclusion']}{extra}")
    print("\nPor perfil (genetico_sin_semilla vs greedy):")
    for perfil, v in concl["por_perfil"]["genetico_sin_semilla vs greedy"].items():
        print(f"  {perfil:22} {v}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--semillas", type=int, default=10)
    ap.add_argument("--generaciones", type=int, default=GENERACIONES)
    ap.add_argument("--poblacion", type=int, default=POBLACION)
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()

    df = cargar_lugares()
    print(f"Lugares: {len(df)} | semillas: {args.semillas} | generaciones: {args.generaciones} | "
          f"poblacion: {args.poblacion}")
    detalle, rutas = correr(df, args.semillas, args.generaciones, args.poblacion)
    res = resumir(detalle)
    concl = conclusiones(res, detalle)
    imprimir(res, concl, detalle)

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    detalle.to_csv(salida / "comparacion_detalle.csv", index=False, encoding="utf-8-sig")
    res.to_csv(salida / "comparacion_resumen.csv", index=False, encoding="utf-8-sig")
    meta = {"lugares": len(df), "semillas": args.semillas, "generaciones": args.generaciones,
            "poblacion": args.poblacion,
            "dataset_sha1": hashlib.sha1(Path(RUTA_DATOS).read_bytes()).hexdigest()[:12],
            "pandas": pd.__version__, "numpy": np.__version__}
    with open(salida / "comparacion.json", "w", encoding="utf-8") as f:
        json.dump({"parametros": meta, "resumen": json.loads(res.to_json(orient="records")),
                   "conclusiones": concl}, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {salida}")


if __name__ == "__main__":
    main()
