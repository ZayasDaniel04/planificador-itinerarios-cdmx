"""Aclara o elimina los lugares cuyo nombre esta en otro idioma que no sea espanol.

    Kabuki           ->  Kabuki (restaurante de sushi)
    Living Room Bar  ->  Living Room Bar (bar)

Los registros sin sentido para un itinerario en espanol se eliminan (y quedan anotados en
data/lugares_eliminados.csv). El nombre original se conserva en la columna `nombre_original`.
Las decisiones estan en app/nombres.py. Es seguro correrlo varias veces (idempotente).

Orden recomendado si se regenera el dataset desde cero:
    python limpiar_dataset.py  ->  python mejorar_dataset.py  ->  python adaptar_nombres.py

Uso (desde backend/):
    python adaptar_nombres.py                 # modifica data/lugares_limpio.csv
    python adaptar_nombres.py --solo-reporte  # solo muestra lo que haria
"""
import argparse
from pathlib import Path

import pandas as pd

from app.nombres import adaptar, parece_otro_idioma

DATOS = Path(__file__).resolve().parents[1] / "data"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-reporte", action="store_true", help="no modifica ningun archivo")
    ap.add_argument("--csv", default=str(DATOS / "lugares_limpio.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    nuevo, eliminados = adaptar(df)
    cambiados = nuevo[nuevo["nombre"] != nuevo["nombre_original"]]
    pendientes = nuevo[nuevo["nombre"].map(parece_otro_idioma) & ~nuevo["nombre"].str.contains(r"\(", regex=True)]

    print(f"Lugares: {len(df)} -> {len(nuevo)}")
    print(f"Nombres aclarados: {len(cambiados)} | eliminados: {len(eliminados)}")
    for e in eliminados:
        print(f"  ELIMINADO {e['nombre']!r}: {e['motivo']}")
    if len(pendientes):
        print("Todavia parecen estar en otro idioma (revisar a mano):", pendientes["nombre"].tolist())

    if args.solo_reporte:
        print("\n(--solo-reporte: no se modifico ningun archivo)")
        return
    nuevo.to_csv(args.csv, index=False, encoding="utf-8-sig")
    ruta_log = DATOS / "lugares_eliminados.csv"
    previos = pd.read_csv(ruta_log) if ruta_log.exists() else pd.DataFrame()
    log = pd.concat([previos, pd.DataFrame(eliminados)], ignore_index=True)
    if len(log):
        log = log.drop_duplicates("osm_id")
        log.to_csv(ruta_log, index=False, encoding="utf-8-sig")
    print(f"\nActualizado: {args.csv}")


if __name__ == "__main__":
    main()
