"""Nombres de lugares en otro idioma que no sea espanol.

Regla: un lugar real con nombre en otro idioma (ingles, frances, italiano, japones...) se conserva
pero se le agrega entre parentesis QUE ES, por ejemplo:

    Kabuki                ->  Kabuki (restaurante de sushi)
    Living Room Bar       ->  Living Room Bar (bar)

La aclaracion sale de la categoria del lugar y, si es comida, de la etiqueta de cocina que ya
trae OpenStreetMap (no se inventa ningun tipo de comida). Si el nombre no se puede aclarar
porque es un registro basura o mal etiquetado (por ejemplo, en japones sin ningun sentido para
un itinerario en espanol), el lugar se ELIMINA.

No se tocan los nombres en lenguas indigenas de Mexico (Tlecan, Uautli, Xkina, Cencalli...)
porque forman parte de la cultura local. Las decisiones se guardan por osm_id (estable aunque
cambien los id del CSV) junto con el nombre original esperado, para no aplicarlas al lugar
equivocado.
"""
import re
import unicodedata

# osm_id -> nombre original (como viene en OpenStreetMap)
NOMBRES_EN_OTRO_IDIOMA = {
    # bares
    5718556537: "Living Room Bar", 5441377369: "Balmori Roofbar", 12054180569: "Beer Garden Roma",
    11474173998: "Crown", 8237675817: "Fifty Mils", 4470120164: "Gin Gin Roma Norte",
    11457540741: "Hanky Panky Cocktail Bar", 11481320651: "Kinky Bar", 4518454687: "Le Tachinomi Desu",
    9380863417: "Luvina vegan-bar", 5262937122: "Maison Artemisia", 4597277989: "Parker & Lenox",
    # cafeterias
    8843502571: "Espressino", 11196610637: "Baia Café", 4532801505: "Chai", 9630394644: "Signora Mariola",
    11053915496: "Amorês Churros & Waffles", 11477023254: "BAD!", 8837172253: "Brewklyn",
    4485019178: "Caravanserai", 11458373394: "Chez Vous #Timecafé", 11495567586: "Loose Blues Dining",
    4170721389: "Maison Kayser", 9083060054: "Matcha Mio", 12763263101: "Nice Day Coffee",
    3445306342: "Patisserie Dominique", 10166786924: "Cheesecake Delivery Jardín San Ángel",
    # librerias
    12103878901: "American Bookstore", 6240899185: "Under",
    # restaurantes
    11477699071: "Ahumadas Grill & BBQ", 12132866585: "480º Pizza Lounge", 3429548470: "Kolobok",
    4456412590: "Nanaya", 1494079875: "Sushi-itto Coyoacán", 464181702: "Centanni Ristorante Vivo Polanco",
    790785747: "Tandoor", 11390850713: "Beer Stop", 13710172142: "Carolines 400", 1427373288: "Gin Chan",
    7733099285: "Izakaya KURA", 6320928285: "Kabuki", 13911276603: "Kinjo Sushi Bar",
    4164135490: "La vie en Rose", 850383273: "O'Xacobeo", 13650271190: "Ramen Ichi",
    4518454685: "Ramen-ya Rokai", 4518454684: "Rokai", 11070234724: "Taco Game Narvarte",
    11070234733: "Tokyo Rose", 11492632485: "Trattoria Enrico's", 7080840285: "Wan Wan Sakaba",
    1695367990: "Cluny", 13058870470: "Tagers", 12985207002: "Tandoor San Angel",
}
# bares: lo que dice el propio nombre (no hay etiqueta de cocina)
DESCRIPCION_MANUAL = {11457540741: "bar de cocteles", 9380863417: "bar vegano"}

# osm_id -> (nombre original, motivo). Estos lugares se eliminan.
LUGARES_A_ELIMINAR = {
    6683170185: ("シティオ", "nombre en japones, sin sentido para un itinerario en espanol; "
                             "mirador mal etiquetado"),
    2005860965: ("Sólo Entrada / Only Entrance", "nombre bilingue de un letrero de acceso, no un "
                                                 "lugar visitable; zoologico mal etiquetado"),
}

CATEGORIA_ES = {"restaurante": "restaurante", "cafeteria": "cafetería", "bar": "bar",
                "libreria": "librería", "museo": "museo", "mercado": "mercado"}

# etiquetas de cocina de OpenStreetMap -> espanol
NACIONALIDAD = {"japanese": "japonesa", "italian": "italiana", "french": "francesa", "indian": "india",
                "russian_food": "rusa", "spanish": "española", "american": "estadounidense",
                "asian": "asiática", "mexican": "mexicana", "argentinian": "argentina",
                "cuban": "cubana", "lebanese": "libanesa", "mediterranean": "mediterránea",
                "korean": "coreana", "chinese": "china", "peruvian": "peruana", "greek": "griega"}
PLATILLO = {"sushi": "sushi", "ramen": "ramen", "pizza": "pizza", "steak_house": "carnes",
            "burger": "hamburguesas", "seafood": "mariscos", "waffle": "waffles", "churros": "churros",
            "crepe": "crepas", "breakfast": "desayunos", "brunch": "brunch", "sandwich": "sándwiches",
            "cake": "pasteles", "pasta": "pasta", "tacos": "tacos", "barbecue": "carne asada"}
ESPECIAL = {"teahouse": "casa de té", "taquería": "taquería", "bakery": "pastelería"}


def _etiquetas(tipo_comida):
    if not isinstance(tipo_comida, str):
        return []
    return [t.strip("_ ").lower() for t in re.split(r"[;,]", tipo_comida) if t.strip("_ ")]


def descripcion_lugar(categoria, tipo_comida=None):
    """Que es el lugar, en espanol. Usa solo la categoria y las etiquetas de cocina de OSM."""
    base = CATEGORIA_ES.get(categoria, categoria)
    if categoria not in ("restaurante", "cafeteria"):
        return base
    etiquetas = _etiquetas(tipo_comida)
    especial = [t for t in etiquetas if t in ESPECIAL]
    if especial:                                    # ej. teahouse, taquería, bakery
        return ESPECIAL[especial[0]]
    nacionalidad = [t for t in etiquetas[:2] if t in NACIONALIDAD]
    if nacionalidad:
        return f"{base} de comida {NACIONALIDAD[nacionalidad[0]]}"
    platillo = [t for t in etiquetas if t in PLATILLO]
    if platillo:
        return f"{base} de {PLATILLO[platillo[0]]}"
    return base


# Palabras de otros idiomas que aparecen en los nombres del dataset. Sirve para DETECTAR
# nombres que quedaron sin aclarar (por ejemplo, al regenerar el CSV); no decide por si sola.
PALABRAS_OTRO_IDIOMA = {
    "only", "entrance", "living", "room", "roofbar", "garden", "crown", "fifty", "mils", "hanky",
    "panky", "cocktail", "kinky", "tachinomi", "desu", "vegan", "maison", "espressino", "baia",
    "chai", "signora", "waffles", "brewklyn", "caravanserai", "chez", "vous", "timecafe", "loose",
    "blues", "dining", "kayser", "matcha", "nice", "coffee", "patisserie", "cheesecake", "delivery",
    "bookstore", "american", "grill", "bbq", "lounge", "kolobok", "nanaya", "itto", "tandoor",
    "beer", "carolines", "izakaya", "kura", "kabuki", "kinjo", "sakaba", "xacobeo", "ichi",
    "rokai", "tokyo", "trattoria", "ristorante", "tagers", "parker", "lenox", "john", "kennedy",
    "shakespeare",
}
# Excepciones: nombres propios que se dejan tal cual (no son un lugar "en otro idioma")
EXCEPCIONES_OTRO_IDIOMA = {"john", "kennedy", "shakespeare", "american"}


def _tokens(nombre):
    s = unicodedata.normalize("NFKD", str(nombre).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", s)


def parece_otro_idioma(nombre):
    """True si el nombre usa otro alfabeto o contiene palabras de otro idioma conocidas."""
    if re.search(r"[^\u0000-\u024F\u2010-\u2027\s]", str(nombre)):
        return True
    return any(t in PALABRAS_OTRO_IDIOMA and t not in EXCEPCIONES_OTRO_IDIOMA for t in _tokens(nombre))


def nombre_aclarado(original, categoria, tipo_comida=None, osm_id=None):
    """'Kabuki' -> 'Kabuki (restaurante de sushi)'."""
    desc = DESCRIPCION_MANUAL.get(osm_id) or descripcion_lugar(categoria, tipo_comida)
    return f"{original} ({desc})"


def adaptar(df):
    """Aplica las decisiones al DataFrame de lugares. Es idempotente (se puede repetir).

    Devuelve (df_nuevo, eliminados) con `eliminados` como lista de diccionarios. Guarda el nombre
    como venia de OSM en la columna `nombre_original`."""
    df = df.copy()
    if "nombre_original" not in df.columns:
        df["nombre_original"] = df["nombre"]
    eliminar = []
    for i, f in df.iterrows():
        osm = f.get("osm_id")
        if osm is None or osm != osm:                        # sin osm_id (NaN): no hay decision
            continue
        osm = int(osm)
        original = f["nombre_original"]
        if osm in LUGARES_A_ELIMINAR:
            esperado, motivo = LUGARES_A_ELIMINAR[osm]
            _verificar(original, esperado, osm)
            eliminar.append({"id": int(f["id"]), "osm_id": osm, "nombre": original,
                             "categoria": f["categoria"], "motivo": motivo})
        elif osm in NOMBRES_EN_OTRO_IDIOMA:
            _verificar(original, NOMBRES_EN_OTRO_IDIOMA[osm], osm)
            df.at[i, "nombre"] = nombre_aclarado(original, f["categoria"], f.get("tipo_comida"), osm)
    ids = {e["id"] for e in eliminar}
    return df[~df["id"].isin(ids)].reset_index(drop=True), eliminar


def _verificar(original, esperado, osm):
    if str(original).strip() != esperado:
        raise ValueError(f"osm_id {osm}: se esperaba {esperado!r} pero el CSV dice {original!r}. "
                         "No se aplica la decision para no cambiar el lugar equivocado.")
