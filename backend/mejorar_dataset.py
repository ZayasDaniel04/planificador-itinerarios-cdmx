"""Enriquece data/lugares_limpio.csv con procedencia y calidad de los datos (NO destructivo).

Parte del CSV actual (con tus correcciones manuales) y del crudo de OpenStreetMap. Agrega:
  osm_id, costo_osm        vinculo con OpenStreetMap y su etiqueta de cobro (fee), si existe
  horario_fuente           "osm" (dato real interpretado) o "estimado_categoria"
  costo_fuente             "osm_fee_no" (gratis segun OSM), "estimado_categoria" o "manual"
  duracion_fuente          "estimado_categoria" o "manual"
  atributos_fuente         origen de nivel de actividad, aptitud ninos/mayores y ambiente
  campos_faltantes         informacion real que OSM no trae para ese lugar
  usable                   0 si el registro no se puede usar (coordenadas invalidas, campos
                           obligatorios vacios o duplicado exacto); cargar_lugares() lo respeta
  calidad_flags            alertas para revisar (duplicados, lejos de su zona, nombre no latino...)

No borra lugares ni cambia valores, salvo poner costo 0 cuando OSM dice fee=no y el costo era
el valor por defecto. Es seguro correrlo varias veces (idempotente).

Uso (desde backend/):
    python mejorar_dataset.py                # actualiza el CSV y escribe el reporte
    python mejorar_dataset.py --solo-reporte # solo muestra el reporte, no modifica nada
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from app.calidad_datos import analizar, analizar_crudo

DATOS = Path(__file__).resolve().parents[1] / "data"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-reporte", action="store_true", help="no modifica el CSV")
    ap.add_argument("--limpio", default=str(DATOS / "lugares_limpio.csv"))
    ap.add_argument("--crudo", default=str(DATOS / "lugares_raw.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.limpio)
    raw = pd.read_csv(args.crudo)
    df2, reporte, problemas = analizar(df, raw)
    reporte["crudo_osm"] = analizar_crudo(raw)

    if not args.solo_reporte:
        df2.to_csv(args.limpio, index=False, encoding="utf-8-sig")
        problemas.to_csv(DATOS / "calidad_registros.csv", index=False, encoding="utf-8-sig")
        with open(DATOS / "reporte_calidad.json", "w", encoding="utf-8") as f:
            json.dump(reporte, f, ensure_ascii=False, indent=2, default=int)

    print(f"Registros: {reporte['total_registros']}  (usables: {reporte['usables']}, "
          f"no usables: {reporte['no_usables']})")
    print(f"Horario real de OSM interpretado: {reporte['porcentaje_horario_real']}% "
          f"({reporte['procedencia']['horario']})")
    print(f"Costo: {reporte['procedencia']['costo']}")
    print(f"Duracion: {reporte['procedencia']['duracion']}")
    print(f"Atributos (ninos/mayores/actividad/ambiente): "
          f"{reporte['procedencia']['atributos_ninos_mayores_actividad_ambiente']}")
    print(f"Coordenadas invalidas: {reporte['coordenadas_invalidas']}")
    print(f"Pares de posibles duplicados: {len(reporte['duplicados'])}")
    print(f"Campos vacios: {reporte['campos_vacios']}")
    print("Banderas de calidad:")
    for b, n in reporte["banderas"].items():
        print(f"  {b:42} {n}")
    print("Crudo OSM:", reporte["crudo_osm"])
    if args.solo_reporte:
        print("\n(--solo-reporte: no se modifico ningun archivo)")
    else:
        print(f"\nActualizado: {args.limpio}\nReporte: {DATOS / 'reporte_calidad.json'}")


if __name__ == "__main__":
    main()
