"""Interpretacion de horarios reales de OpenStreetMap (etiqueta opening_hours).

El dataset trae `horario_osm` para la mayoria de los lugares, pero hasta ahora no se
usaba: `hora_apertura` y `hora_cierre` son un valor por defecto por categoria (una
ESTIMACION). Este modulo convierte `horario_osm` en ventanas de apertura por dia de la
semana. Si el texto no se puede interpretar con certeza se devuelve None y el sistema
usa la estimacion por categoria, marcandola como tal. Nunca se inventa un horario.

Subconjunto de la sintaxis de OSM que se entiende:
  "Mo-Su 08:30-19:30"                      rangos de dias
  "Mo-Sa 09:00-19:00; Su 09:00-18:00"      varias reglas (la ultima manda para sus dias)
  "Fr,Sa 10:00-01:00"                      listas de dias y horarios que cruzan la medianoche
  "Tu-Sa 13:00-17:00,19:00-23:00"          varios tramos en un dia
  "Mo-Sa 13:00-21:00; Su off"              dias cerrados
  "09:00-17:00" / "24/7"                   todos los dias
Los dias festivos (PH/SH) se ignoran, y lo que no se entiende (sunrise, "+", etc.)
hace que todo el texto se considere no interpretable.
"""
import re
import unicodedata
from functools import lru_cache

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_OSM_DIA = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6}
MIN_DIA = 24 * 60

_RE_SEP_GRUPOS = re.compile(r"(?<=\d),\s*(?=(?:Mo|Tu|We|Th|Fr|Sa|Su|PH|SH)\b)")
_RE_GRUPO = re.compile(
    r"^\s*(?P<dias>(?:[A-Za-z]{2}(?:\s*-\s*[A-Za-z]{2})?\s*,?\s*)*)"
    r"(?P<horas>off|closed|\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}(?:\s*,\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})*)\s*$",
    re.IGNORECASE,
)
_RE_TRAMO = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def normalizar_dia(texto):
    """'Sábado' -> 'sabado'. Devuelve '' si el texto esta vacio."""
    if texto is None or texto != texto:        # None o NaN (casilla vacia del CSV)
        return ""
    s = unicodedata.normalize("NFKD", str(texto).strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def indice_dia(nombre_dia):
    """'sabado' -> 5. Devuelve None si no es un dia valido."""
    d = normalizar_dia(nombre_dia)
    return DIAS.index(d) if d in DIAS else None


def _dias_de(texto):
    """Convierte 'Mo-We,Fr' en {0,1,2,4}. Devuelve None si algo no se entiende."""
    dias = set()
    for token in [t.strip() for t in texto.split(",") if t.strip()]:
        if token.upper() in ("PH", "SH"):
            continue                           # festivos: no se modelan
        partes = [p.strip() for p in token.split("-")]
        if len(partes) == 1 and partes[0] in _OSM_DIA:
            dias.add(_OSM_DIA[partes[0]])
        elif len(partes) == 2 and partes[0] in _OSM_DIA and partes[1] in _OSM_DIA:
            a, b = _OSM_DIA[partes[0]], _OSM_DIA[partes[1]]
            i = a
            while True:                        # admite rangos que dan la vuelta (Su-Th)
                dias.add(i)
                if i == b:
                    break
                i = (i + 1) % 7
        else:
            return None
    return dias


def _tramos_de(texto):
    """Convierte '13:00-17:00,19:00-02:00' en [(780, 1020), (1140, 1560)] (minutos)."""
    tramos = []
    for h1, m1, h2, m2 in _RE_TRAMO.findall(texto):
        ini = int(h1) * 60 + int(m1)
        fin = int(h2) * 60 + int(m2)
        if not (0 <= int(m1) < 60 and 0 <= int(m2) < 60) or ini > MIN_DIA or fin > MIN_DIA:
            return None
        if fin <= ini:
            fin += MIN_DIA                     # cruza la medianoche (ej. 18:00-02:00)
        tramos.append((ini, fin))
    return tramos or None


@lru_cache(maxsize=4096)
def parsear_horario_osm(texto):
    """Devuelve {dia: ((ini, fin), ...)} con minutos desde las 00:00 (fin puede pasar de 1440
    si el horario cruza la medianoche), o None si el texto no es interpretable.
    Los dias que no aparecen en ninguna regla se consideran cerrados (semantica de OSM)."""
    if texto is None or str(texto).strip() == "" or str(texto).lower() == "nan":
        return None
    t = str(texto).strip()
    if t == "24/7":
        return {d: ((0, MIN_DIA),) for d in range(7)}
    if "+" in t or re.search(r"sunrise|sunset|dawn|dusk|week|\[|\"|easter", t, re.IGNORECASE):
        return None

    horario = {}
    hubo_dias = False
    for regla in [r.strip() for r in t.split(";") if r.strip()]:
        for grupo in _RE_SEP_GRUPOS.split(regla):
            m = _RE_GRUPO.match(grupo)
            if not m:
                return None
            dias_txt = m.group("dias").strip().strip(",").strip()
            horas = m.group("horas").strip().lower()
            if dias_txt:
                dias = _dias_de(dias_txt)
                if dias is None:
                    return None
                if not dias:                   # regla solo de festivos: se ignora
                    continue
                hubo_dias = True
            else:
                dias = set(range(7))
            if horas in ("off", "closed"):
                tramos = ()
            else:
                tramos = _tramos_de(horas)
                if tramos is None:
                    return None
                tramos = tuple(tramos)
            for d in dias:
                horario[d] = tramos            # la regla posterior reemplaza a la anterior
    if not horario:
        return None
    return {d: horario.get(d, ()) for d in range(7)}


def ventanas_del_dia(horario, dia):
    """Ventanas (ini, fin) en que el lugar esta abierto el dia `dia` (0=lunes), recortadas a
    las 24:00. Incluye el tramo que viene del dia anterior si ese horario cruzaba la medianoche."""
    ventanas = []
    previo = horario.get((dia - 1) % 7, ())
    for ini, fin in previo:
        if fin > MIN_DIA:
            ventanas.append((0, fin - MIN_DIA))
    for ini, fin in horario.get(dia, ()):
        ventanas.append((ini, min(fin, MIN_DIA)))
    return sorted(ventanas)


def dias_cerrado_osm(horario):
    """Nombres de los dias en que un horario interpretado nunca abre (para reportes)."""
    return [DIAS[d] for d in range(7) if not ventanas_del_dia(horario, d)]


def a_min(hhmm):
    """'13:30' -> 810."""
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def a_hhmm(minutos):
    """810 -> '13:30'."""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def ventanas_lugar(lugar, dia_semana, usar_horarios_osm=True):
    """Ventanas de apertura de un lugar para un dia concreto.

    Devuelve (ventanas, fuente):
      - fuente "osm": viene de `horario_osm` (dato real) y ya considera los dias cerrados.
      - fuente "estimado_categoria": se usa hora_apertura/hora_cierre y dias_cerrado, que son
        valores por defecto de la categoria (no datos reales).
    `lugar` puede ser una fila de pandas o un diccionario."""
    dia = indice_dia(dia_semana)
    if usar_horarios_osm and dia is not None:
        horario = parsear_horario_osm(lugar.get("horario_osm"))
        if horario is not None:
            return ventanas_del_dia(horario, dia), "osm"
    if dia is not None and DIAS[dia] in normalizar_dia(lugar.get("dias_cerrado")):
        return [], "estimado_categoria"
    return [(a_min(lugar["hora_apertura"]), a_min(lugar["hora_cierre"]))], "estimado_categoria"
