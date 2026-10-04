ruta = "app/itinerario.py"
s = open(ruta, encoding="utf-8").read()

cambios = [
    (
'MAX_POR_CATEGORIA = 2\n',
'MAX_POR_CATEGORIA = {"cafeteria": 1, "libreria": 1, "cine": 1}\nMAX_DEFAULT = 2\n',
    ),
    (
'if por_cat.get(cat, 0) >= MAX_POR_CATEGORIA:',
'if por_cat.get(cat, 0) >= MAX_POR_CATEGORIA.get(cat, MAX_DEFAULT):',
    ),
    (
"""    comio = False
    ruta = []
""",
"""    comio = False
    ruta = []
    # si el grupo quiere vida nocturna, se reserva presupuesto para un bar
    nocturno = perfil.intereses.get("vida_nocturna", 0) >= 0.5 and fin_dia >= 21 * 60
    bares = pool[pool["categoria"] == "bar"]
    reserva = float(bares["costo_estimado"].min()) if (nocturno and not bares.empty) else 0.0
    bar_hecho = False
""",
    ),
    (
"""                if gasto + l["costo_estimado"] > presupuesto:
                    continue
""",
"""                if gasto + l["costo_estimado"] > presupuesto:
                    continue
                if cat != "bar" and not bar_hecho and gasto + l["costo_estimado"] + reserva > presupuesto:
                    continue
""",
    ),
    (
"""            comio = True
    return ruta
""",
"""            comio = True
        if l["categoria"] == "bar":
            bar_hecho = True
    return ruta
""",
    ),
]

for viejo, nuevo in cambios:
    if viejo not in s:
        raise SystemExit("No se encontro este bloque: " + viejo[:40])
    s = s.replace(viejo, nuevo, 1)

open(ruta, "w", encoding="utf-8").write(s)
print("Parche aplicado")
