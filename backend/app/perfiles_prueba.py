"""Perfiles de ejemplo compartidos por comparar_algoritmos.py, evaluar_pesos.py y las pruebas.

Los seis primeros son los que ya usaba el comparador; los demas cubren casos que antes no se
probaban (adultos mayores, presupuesto muy ajustado, dia lunes con muchos museos cerrados,
horario corto y un caso sin solucion posible).
"""
from app.perfiles import Perfil


def perfiles_prueba():
    return {
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
        "Adultos mayores": Perfil(tipo_grupo="familia", personas=3, hay_adultos_mayores=True,
                                  presupuesto_por_persona=600, nivel_actividad=1,
                                  hora_inicio="10:00", hora_fin="18:00",
                                  intereses={"cultura": 0.8, "historia": 0.7, "comida": 0.6}),
        "Presupuesto minimo": Perfil(tipo_grupo="solo", personas=1, presupuesto_por_persona=100,
                                     nivel_actividad=2, hora_inicio="10:00", hora_fin="19:00",
                                     intereses={"cultura": 0.8, "naturaleza": 0.6}),
        "Lunes de museos": Perfil(tipo_grupo="pareja", personas=2, presupuesto_por_persona=700,
                                  nivel_actividad=2, dia_semana="lunes",
                                  hora_inicio="10:00", hora_fin="19:00",
                                  intereses={"cultura": 0.9, "historia": 0.8, "arte": 0.7}),
    }


def perfil_sin_solucion():
    """Presupuesto 0 y solo 1 hora: ningun itinerario razonable cabe (sirve para probar casos limite)."""
    return Perfil(tipo_grupo="solo", personas=1, presupuesto_por_persona=0, nivel_actividad=1,
                  hora_inicio="10:00", hora_fin="10:20", intereses={"comida": 1.0})
