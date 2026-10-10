from app.perfiles import Perfil
from app.recomendador import cargar_lugares
from app.genetico import comparar

df = cargar_lugares()

perfiles = {
    "Pareja romantica": Perfil(tipo_grupo="pareja", personas=2, presupuesto_por_persona=800,
                               nivel_actividad=1, hora_inicio="10:00", hora_fin="21:00",
                               intereses={"comida": 0.9, "arte": 0.7, "fotografia": 0.6}),
    "Familia con ninos": Perfil(tipo_grupo="familia", personas=4, hay_ninos=True,
                                presupuesto_por_persona=500, nivel_actividad=2,
                                hora_inicio="10:00", hora_fin="19:00",
                                intereses={"naturaleza": 0.9, "cultura": 0.6, "comida": 0.7}),
    "Amigos de fiesta": Perfil(tipo_grupo="amigos", personas=4, presupuesto_por_persona=1200,
                               nivel_actividad=3, hora_inicio="12:00", hora_fin="23:30",
                               intereses={"vida_nocturna": 1.0, "comida": 0.8}),
    "Solo cultural": Perfil(tipo_grupo="solo", personas=1, presupuesto_por_persona=500,
                            nivel_actividad=2, hora_inicio="10:00", hora_fin="18:00",
                            intereses={"cultura": 0.9, "historia": 0.8, "arte": 0.6}),
    "Pareja economica": Perfil(tipo_grupo="pareja", personas=2, presupuesto_por_persona=300,
                               nivel_actividad=2, hora_inicio="10:00", hora_fin="20:00",
                               intereses={"comida": 0.6, "naturaleza": 0.7}),
    "Amigos en el Centro": Perfil(tipo_grupo="amigos", personas=3, presupuesto_por_persona=600,
                                  nivel_actividad=3, hora_inicio="11:00", hora_fin="20:00",
                                  zona="Centro Historico",
                                  intereses={"compras": 0.7, "comida": 0.8, "historia": 0.6}),
}

print(f'{"Perfil":20} {"Algoritmo":9} {"Fitness":>8} {"Lugares":>8} {"Traslado":>9} {"Espera":>7} {"Gasto":>6} {"Seg":>5}')
primero = None
for nombre, perfil in perfiles.items():
    r = comparar(df, perfil)
    if r is None:
        print(f"{nombre:20} sin lugares que cumplan los filtros")
        continue
    if primero is None:
        primero = (nombre, r)
    for alg in ("greedy", "genetico"):
        x = r[alg]
        s = x["resumen"]
        print(f'{nombre:20} {alg:9} {x["fitness"]:8.2f} {s["lugares"]:8d} '
              f'{s["traslado_total_min"]:6d} min {s["espera_total_min"]:4d} min '
              f'{s["gasto_por_persona"]:6.0f} {x["seg"]:5.1f}')

if primero:
    nombre, r = primero
    print(f"\n=== Itinerario del genetico: {nombre} ===")
    for p in r["genetico"]["ruta"]:
        print(f'{p["llegada"]}-{p["salida"]}  {p["nombre"][:30]:30}  {p["categoria"]:11}'
              f' traslado {p["traslado_min"]:>2} min  ${p["costo_estimado"]:.0f}')
    h = r["genetico"]["historial"]
    print(f"\nConvergencia: generacion 1 = {h[0]}, generacion {len(h)} = {h[-1]}")
