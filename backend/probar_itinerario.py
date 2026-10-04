from app.perfiles import Perfil
from app.recomendador import cargar_lugares
from app.itinerario import generar_itinerario

df = cargar_lugares()

ejemplos = {
    "Pareja romantica": Perfil(tipo_grupo="pareja", personas=2, presupuesto_por_persona=800,
                               nivel_actividad=1, hora_inicio="10:00", hora_fin="21:00",
                               intereses={"comida": 0.9, "arte": 0.7, "fotografia": 0.6}),
    "Familia con ninos": Perfil(tipo_grupo="familia", personas=4, hay_ninos=True,
                                presupuesto_por_persona=500, nivel_actividad=2,
                                hora_inicio="10:00", hora_fin="19:00",
                                intereses={"naturaleza": 0.9, "cultura": 0.6, "comida": 0.7}),
    "Amigos de fiesta": Perfil(tipo_grupo="amigos", personas=4, presupuesto_por_persona=700,
                               nivel_actividad=3, hora_inicio="12:00", hora_fin="23:30",
                               intereses={"vida_nocturna": 1.0, "comida": 0.8}),
}

for nombre, perfil in ejemplos.items():
    it = generar_itinerario(df, perfil)
    print(f"\n=== {nombre} ===")
    for p in it["paradas"]:
        print(f'{p["llegada"]}-{p["salida"]}  {p["nombre"][:30]:30}  {p["categoria"]:11}'
              f' traslado {p["traslado_min"]:>2} min  ${p["costo_estimado"]:.0f}')
    r = it["resumen"]
    print(f'-> {r["lugares"]} lugares | gasto ${r["gasto_por_persona"]:.0f} p/p | '
          f'traslados {r["traslado_total_min"]} min | espera {r["espera_total_min"]} min | '
          f'comida: {"si" if r["incluye_comida"] else "NO"}')
