# Planificador inteligente de itinerarios turísticos de la CDMX

Proyecto final de Inteligencia Artificial. Una página web arma el itinerario de **un día** en la
Ciudad de México para parejas, personas solas, grupos de amigos y familias, según el tipo de grupo,
el número de personas, si hay niños o adultos mayores, el presupuesto por persona, el horario, el
nivel de caminata, la zona, el día de la semana y los intereses.

El núcleo de IA es propio (no depende de un LLM): recomendador basado en contenido, sistema experto
de reglas, y dos optimizadores del itinerario (voraz y genético) que se comparan con el mismo
criterio.

Todo el recorrido es **a pie**: los traslados se calculan caminando, el **nivel de caminata** (poco,
medio o mucho) fija cuántos kilómetros se caminan en el día (3, 6 o 10 km) y el mapa traza la ruta por
las calles peatonales.

---

## 1. Arquitectura

```
frontend/index.html  --HTTP/JSON-->  backend/app/main.py (FastAPI)
                                          |
        +---------------------------------+----------------------------------+
        |                                 |                                  |
 recomendador.py                    itinerario.py (voraz)             genetico.py
 (coseno + reglas + pesos)                 \                           /
        |                                   \                         /
 reglas.py (sistema experto)         restricciones.py  <-- UNICA fuente de reglas duras
 perfiles.py (perfil y vectores)     fitness.py        <-- UNICA funcion objetivo
        |                            horarios.py (horarios reales de OSM)
 data/lugares_limpio.csv <-- calidad_datos.py / mejorar_dataset.py
```

| Archivo | Para qué sirve |
|---|---|
| `app/perfiles.py` | Perfil del visitante, vector de 8 intereses y su validación. |
| `app/reglas.py` | Sistema experto: filtros duros y ajustes por tipo de grupo. |
| `app/recomendador.py` | Puntaje = similitud coseno + reglas + confianza de datos − precio; pesos configurables. |
| `app/horarios.py` | Interpreta el horario real de OpenStreetMap (`horario_osm`) por día de la semana. |
| `app/restricciones.py` | **Restricciones compartidas** (`revisar_parada`) y validador independiente (`validar_itinerario`). |
| `app/fitness.py` | Función fitness compartida, con desglose por término. |
| `app/itinerario.py` | Algoritmo voraz. Solo decide el orden; las reglas vienen de `restricciones.py`. |
| `app/genetico.py` | Algoritmo genético sobre las mismas reglas y el mismo fitness. |
| `app/calidad_datos.py` | Detección de duplicados, coordenadas inválidas, faltantes y procedencia de los datos. |
| `app/nombres.py` | Nombres en otro idioma: se aclaran entre paréntesis (qué es el lugar) o se eliminan. |
| `app/perfiles_prueba.py` | Perfiles de ejemplo compartidos por los scripts de evaluación y las pruebas. |
| `app/main.py` | API FastAPI. |
| `comparar_algoritmos.py` | Experimento voraz vs genético (varias semillas, exporta CSV/JSON). |
| `evaluar_pesos.py` | Análisis de sensibilidad de los pesos del recomendador. |
| `adaptar_nombres.py` | Aplica `nombres.py` al CSV (idempotente) y anota lo eliminado en `data/lugares_eliminados.csv`. |
| `../frontend/index.html` | La página: formulario, globos de kilómetros, mapa con ruta a pie. |
| `mejorar_dataset.py` | Agrega procedencia y calidad al CSV (no destructivo, idempotente). |
| `limpiar_dataset.py` | Genera el CSV desde el crudo de OSM (protegido: no sobrescribe sin `--forzar`). |
| `descargar_lugares.py`, `descargar_faltantes.py` | Descarga de lugares desde OpenStreetMap (Overpass). |
| `tests/` | Pruebas automatizadas con pytest. |

---

## 2. Instalación y ejecución (Git Bash en Windows)

Requisitos: Python 3.10 o superior y Git.

```bash
git clone https://github.com/ZayasDaniel04/planificador-itinerarios-cdmx.git
cd planificador-itinerarios-cdmx/backend
python -m venv venv
source venv/Scripts/activate          # debe aparecer (venv) al inicio de la línea
pip install -r requirements.txt
pip install -r requirements-dev.txt   # solo para correr las pruebas
```

Encender la API (dejar la terminal abierta), desde `backend/`:

```bash
uvicorn app.main:app --reload
```

- http://127.0.0.1:8000 dice "API del planificador funcionando".
- http://127.0.0.1:8000/docs permite probar los endpoints desde el navegador.

Abrir la página (desde la raíz del proyecto, con la API encendida):

```bash
start frontend/index.html             # si ya estaba abierta, Ctrl + F5
```

Scripts de evaluación y pruebas (desde `backend/`, con `(venv)` activo):

```bash
python -m pytest                      # pruebas automatizadas
python comparar_algoritmos.py         # experimento voraz vs genético (~1 minuto)
python evaluar_pesos.py               # sensibilidad de los pesos
python mejorar_dataset.py --solo-reporte   # reporte de calidad de datos sin modificar nada
python adaptar_nombres.py --solo-reporte   # nombres en otro idioma: qué se aclararía o eliminaría
```

### API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Estado y número de lugares. |
| POST | `/recomendar` | Mejores lugares sueltos, con el desglose del puntaje (`sim`, `ajuste`, `confianza`, `precio_rel`). |
| POST | `/itinerario` | Día armado: `paradas`, `resumen`, `algoritmo`, `valido`, `violaciones`, `mensaje`, `limite_km_caminata`. |

Campos de `/itinerario`: `tipo_grupo`, `personas`, `hay_ninos`, `hay_adultos_mayores`,
`presupuesto_por_persona`, `nivel_actividad` (nivel de caminata: 1 poco, 2 medio, 3 mucho; límite de 3,
6 o 10 km al día), `zona`, `dia_semana`, `intereses` (pesos de 0
a 1), `hora_inicio`, `hora_fin`, y opcionalmente `algoritmo` (`"greedy"` por defecto o `"genetico"`)
y `semilla` (solo afecta al genético: misma semilla, mismo itinerario).

- Un perfil inválido (horas al revés, presupuesto negativo, zona inexistente...) responde **422** con la lista de problemas.
- Si no hay itinerario posible responde **200** con `paradas: []` y un `mensaje` que explica por qué.
- Toda respuesta se revisa con `validar_itinerario` antes de entregarse; `valido` y `violaciones` lo reflejan.
- La página actual no manda `algoritmo`, así que sigue usando el voraz. El genético se puede probar desde `/docs`.
- Cada parada trae `traslado_min` y `traslado_km` (a pie desde la parada anterior) y el `resumen` trae `km_caminados`.

### La página (`frontend/index.html`)

- **Nivel de caminata:** tres botones (Poco, Medio, Mucho). Al pasar el mouse o tocar uno aparece un **globo** que dice cuántos kilómetros representa: *Poco, hasta 3 km (unos 35 min a pie); Medio, hasta 6 km (1 h 10 min); Mucho, hasta 10 km (2 h)*. Debajo de cada nombre también se lee el límite. El límite es una restricción real del algoritmo, no solo una etiqueta (ver 4.3).
- **Mapa a pie:** la ruta se traza por las calles peatonales con el servicio de rutas peatonales de OpenStreetMap (`routing.openstreetmap.de/routed-foot`). Mientras carga, y si el servicio falla o no hay internet, se muestra una línea recta punteada aproximada con un aviso. Bajo el mapa se lee la distancia y el tiempo reales de la ruta por calles.
- **Resumen:** en lugar de "en traslados" ahora dice los **km caminados** y los **minutos a pie**; cada parada indica cuánto se camina desde la anterior.
- Los kilómetros que muestran las tarjetas son **estimados** (línea recta × 1.3); la ruta por calles de la página puede dar un número un poco distinto.
---

## 3. Datos

`data/lugares_limpio.csv`: 297 lugares de OpenStreetMap en 5 zonas (Centro Histórico, Roma-Condesa,
Polanco-Chapultepec, Coyoacán, San Ángel) y 15 categorías.

### Dato real vs estimación

OpenStreetMap **no** trae duración de la visita, precio, accesibilidad ni ambiente. Esos campos son
valores por defecto de la categoría (`DEFECTOS_CATEGORIA` en `app/calidad_datos.py`) y el sistema no
los presenta como datos reales. Cada procedencia queda registrada en el CSV:

| Columna | Valores | Qué significa |
|---|---|---|
| `horario_fuente` | `osm` / `estimado_categoria` | `osm`: horario real interpretado, por día de la semana. Medido: **236 de 297 (79.5%)**. |
| `costo_fuente` | `osm_fee_no` / `estimado_categoria` / `manual` | `osm_fee_no`: OSM dice que es gratis (18 lugares). El monto de los demás es una estimación. |
| `duracion_fuente` | `estimado_categoria` / `manual` | Hoy los 297 son estimados. |
| `atributos_fuente` | `estimado_categoria` / `manual_parcial` | Origen de nivel de actividad, apto niños, apto adultos mayores y ambiente (hoy todos estimados). |
| `osm_id`, `costo_osm` | | Vínculo con OSM y su etiqueta `fee`. |
| `campos_faltantes` | | Información real que OSM no trae para ese lugar. |
| `usable` | 1 / 0 | 0 = no se puede usar (coordenadas inválidas, campos obligatorios vacíos o duplicado exacto). `cargar_lugares()` lo respeta. |
| `calidad_flags` | | Alertas para revisar (ver abajo). |

Reglas que se siguen: no se inventan horarios, precios ni condiciones de accesibilidad. El único
valor que se corrige a partir de OSM es el costo 0 cuando OSM dice `fee=no` y el costo era el valor por
defecto (9 museos y 2 zoológicos cambiaron de $80 o $50 a $0); un costo puesto a mano nunca se pisa.
Los horarios que no se pueden interpretar con certeza (6 textos, por ejemplo `Su`, `Th`, un `+` abierto o
una falta de guion) se tratan como estimados y se marcan.

### Revisión de calidad (`python mejorar_dataset.py`)

Resultado sobre el dataset actual (`data/reporte_calidad.json`, `data/calidad_registros.csv`):

| Revisión | Resultado |
|---|---|
| Coordenadas inválidas (vacías, en cero, invertidas, fuera de la zona de estudio) | 0 |
| Pares de posibles duplicados (mismo nombre normalizado, misma ubicación o nombre muy parecido y cercano) | 1: *Ramen-ya Rokai* y *Rokai*, a 8.5 m, con el mismo horario y sitio web (parece el mismo restaurante capturado dos veces) |
| Lugares a más de 5 km del centro de la zona asignada (`lejos_de_su_zona`) | 24 |
| Horario de OSM que no se pudo interpretar | 6 |
| Nombres en otro idioma sin aclarar (`nombre_otro_idioma_sin_aclarar`) | 0 (ver la sección siguiente) |
| Coordenada apenas fuera de la caja de descarga, solo advertencia (Zoológico de San Juan de Aragón) | 1 |
| Campos vacíos: `horario_osm` / `sitio_web` / `tipo_comida` | 55 / 102 / 203 |

El script **solo detecta y etiqueta**; no borra lugares. Revisar a mano lo marcado es decisión del equipo.

### Nombres en otro idioma (`adaptar_nombres.py`)

Los nombres que no están en español se resolvieron así (decisiones en `app/nombres.py`, guardadas por
`osm_id`):

- **Se conserva el lugar y se aclara qué es entre paréntesis** (54 lugares). La aclaración sale de la
  categoría y, si es comida, de la etiqueta de cocina que ya trae OpenStreetMap; **no se inventa ningún
  tipo de comida** (si OSM no dice la cocina, solo se pone "restaurante"). Ejemplos:
  `Kabuki (restaurante de sushi)`, `Tokyo Rose (restaurante de comida japonesa)`,
  `La vie en Rose (restaurante de comida francesa)`, `Living Room Bar (bar)`,
  `Caravanserai (casa de té)`, `Patisserie Dominique (pastelería)`.
- **Se elimina el lugar** cuando el nombre no tiene sentido en un itinerario en español (2 lugares):
  `シティオ` (japonés, mirador mal etiquetado) y `Sólo Entrada / Only Entrance` (letrero de acceso, no
  un lugar visitable). Quedan anotados en `data/lugares_eliminados.csv`.
- **No se tocan** los nombres en lenguas indígenas de México (Tlecān, Uautli, Xkina, Cencalli...) ni los
  nombres propios de personas (Parque John F. Kennedy, Foro Shakespeare).
- El nombre original se conserva en la columna `nombre_original`. La detección de qué es "otro idioma"
  la hizo una revisión a mano de los 299 nombres, no un traductor automático, así que puede haber
  casos discutibles; el detector de calidad avisa si aparece uno nuevo sin aclarar.

### Flujo de datos

```
descargar_lugares.py / descargar_faltantes.py  ->  data/lugares_raw.csv (5,288 lugares)
limpiar_dataset.py   (solo para regenerar desde cero)  ->  data/lugares_limpio.csv
mejorar_dataset.py   (procedencia y calidad, seguro de repetir)
adaptar_nombres.py   (nombres en otro idioma, seguro de repetir)
```

`limpiar_dataset.py` regenera el CSV desde el crudo y **borraría las correcciones manuales**; por eso
se niega a sobrescribirlo sin `--forzar`. Al verificarlo, el flujo completo (`limpiar`, `mejorar`,
`adaptar`) regenera exactamente los 297 lugares actuales más los 3 que el equipo borró a mano (Vips,
Sólo Salida / Only Exit, Forum Buenavista). Decisión de
diseño que conviene conocer: conserva **una sola sucursal por nombre y categoría** (descarta 840
registros del crudo, por ejemplo 116 de las 117 sucursales de Starbucks), para que las cadenas no llenen
los cupos.

---

## 4. Algoritmos

### 4.1 Sistema experto (`reglas.py`)

**Filtros duros** (`pasa_filtros`): con niños no hay lugares no aptos ni bares; con adultos mayores solo
lugares aptos y de nivel de actividad ≤ 2; la familia nunca recibe bares; nivel de actividad del lugar ≤
pedido + 1; ningún lugar puede costar más del 60% del presupuesto (80% si es comida); filtro por zona;
**lugar abierto ese día** (con el horario real de OSM si existe) y **que la visita quepa dentro del
horario del usuario** (por ejemplo, un bar que abre a las 17:00 se descarta para quien termina a las 14:00).

**Ajustes** (`ajuste_reglas`): bono o penalización por categoría según el grupo, y +0.10 si el ambiente
del lugar encaja con el grupo.

### 4.2 Recomendador (`recomendador.py`)

```
puntaje = 0.60 · similitud + 0.25 · reglas + 0.10 · confianza (+ 0.10 · fama, si existe) − 0.15 · precio
```

| Término | Qué mide | Qué **no** mide |
|---|---|---|
| `similitud` | Coseno entre el vector de intereses del usuario (8 ejes) y el vector de la **categoría** del lugar. | Todos los lugares de una categoría empatan. No mide la calidad de un lugar concreto. |
| `reglas` | Ajustes del sistema experto por grupo y ambiente. | |
| `confianza` | Qué tan **verificable** es la información: 0.50 si el horario real se interpretó, 0.25 si tiene sitio web, 0.25 si trae tipo de comida (comida) o etiqueta de costo (el resto). | **No es popularidad ni calidad.** |
| `fama` | Popularidad real de 1 a 5, **solo si** el CSV tiene una columna `fama`. | Hoy no existe ese dato, así que no actúa. |
| `precio` | `costo / presupuesto`, recortado a [0, 1]. Se resta. | |

**Corrección de un indicador engañoso.** Antes el 10% del puntaje era "popularidad" y se calculaba como
1 si el lugar tiene sitio web. Un sitio web no dice cuánta gente visita o aprecia un lugar. Se reemplazó
por `confianza`, que sí mide lo que dice (verificabilidad de los datos). OSM no trae calificaciones ni
visitas, por lo que **la popularidad real no se está midiendo**; si se agrega una columna `fama`
(por ejemplo, de Google Maps o de una encuesta), el recomendador la usa sin más cambios.

El orden es reproducible: los empates se desempatan por `id`.

**Sensibilidad de los pesos** (`python evaluar_pesos.py` → `data/resultados/sensibilidad_pesos.csv`).
Promedio sobre 9 perfiles, contra los pesos por defecto:

| Variante | Top 10 en común | Itinerario del voraz en común | Top 10 con horario real |
|---|---|---|---|
| similitud ×0 (apagada) | 41% | 23% | 100% |
| reglas ×0 | 88% | 91% | 99% |
| confianza ×0 | 57% | 29% | 93% |
| precio ×0 | 80% | 52% | 98% |
| esquema original (sitio web = "popularidad") | 61% | 26% | 86% |

Lectura: como la similitud es igual para toda una categoría, el orden **dentro** de cada categoría lo
deciden `confianza`, `precio` y las reglas; por eso un peso de solo 0.10 mueve tanto el top 10. El
esquema original producía un itinerario muy distinto (solo 26% de lugares en común con el nuevo) y con
menos lugares de horario verificable. Este análisis mide **cuánto cambian** las recomendaciones, no cuál
es "mejor": eso requiere usuarios reales.

### 4.3 Restricciones compartidas (`restricciones.py`)

El voraz y el genético llaman a **la misma función** (`revisar_parada`); antes cada uno tenía su propia
copia. Un itinerario inválido no puede salir de ninguno:

1. No se repiten lugares (ni por `id` ni por nombre normalizado).
2. La visita completa cabe en una ventana de apertura de ese día (horario real de OSM; si no hay, estimación por categoría).
3. La última salida no pasa de la hora de fin.
4. El gasto acumulado por persona no pasa del presupuesto.
5. Duración exacta de cada visita; los traslados son **a pie**: distancia Haversine × 1.3 (las calles rodean manzanas) a 5 km/h, mínimo 5 min; no se llega antes de terminar el lugar anterior más el traslado.
6. **Los kilómetros caminados en el día no pasan del límite del nivel de caminata** (poco 3 km, medio 6 km, mucho 10 km).
7. Espera máxima de 120 min antes de una visita.
8. Máximo por categoría: 1 cafetería, 1 librería y 1 cine; 2 de cualquier otra.
9. Una sola comida fuerte (restaurante o mercado), que empiece entre 12:30 y 16:00.
10. Perfil del visitante: todo lugar debe pasar `pasa_filtros`.

`validar_itinerario(ruta, perfil, df)` revisa todo esto de forma **independiente** (recalcula desde las
paradas, sin reutilizar el estado de la simulación) y se usa en la API, en el experimento y en las pruebas.

**Nivel de caminata.** Es lo que significa cada botón de la página (globo con kilómetros):

| Nivel | Límite de caminata en el día | Tiempo a pie (5 km/h) |
|---|---|---|
| Poco (1) | 3 km | unos 35 min |
| Medio (2) | 6 km | 1 h 10 min |
| Mucho (3) | 10 km | 2 h |

Cuentan solo los kilómetros **entre un lugar y otro** (no lo que se camina dentro de un museo o un
parque). Los límites de 3, 6 y 10 km son un criterio del equipo, no un estándar. Un solo lugar
muy lejano ya no cabe: por ejemplo, de Coyoacán al Centro son unos 13 km a pie.

### 4.4 Voraz (`itinerario.py`)

En cada paso elige, entre los lugares que sí se pueden agregar, el de mayor valor inmediato
(`puntaje − 0.01·traslado − 0.005·espera − 0.15 si repite categoría + 0.5 si es la primera comida`).
Prefiere esperas ≤ 45 min y solo si no hay opciones las relaja hasta 120. Si el grupo es nocturno,
reserva presupuesto para un bar (heurística propia del voraz, no una restricción). Nunca reconsidera una
decisión, por eso puede quedar en un óptimo local.

**Reinicios múltiples.** Como ahora se camina y hay límite de kilómetros, la primera parada decide en qué
parte de la ciudad se queda todo el día: si el lugar mejor puntuado está aislado, el voraz simple arma un
día de 2 o 3 paradas (en el perfil *Familia con niños* armaba 2). Por eso, por defecto el voraz **prueba
cada candidato como primera parada**, sigue voraz desde ahí y se queda con el día de mayor fitness. Sigue
siendo determinista. `reinicios=False` da el voraz simple de una sola corrida; el experimento compara
ambos.

### 4.5 Genético (`genetico.py`)

- **Individuo:** permutación de los 40 candidatos. `simular` recorre el orden y se queda con lo que cumple las restricciones, así que **todo individuo produce un itinerario válido** (restricciones por construcción, sin penalizaciones).
- **Selección:** torneo de 3. **Cruce:** de orden (OX), probabilidad 0.9. **Mutación:** intercambio (0.4) y movimiento de un lugar (0.4). **Elitismo:** 2.
- Población 60, 80 generaciones. Misma `semilla` y mismos datos dan el mismo resultado.
- Opcionalmente el voraz entra a la población inicial (`con_semilla=True`).

### 4.6 Función fitness (`fitness.py`)

```
fitness = Σ puntaje de cada lugar
          − 0.01 · minutos de traslado
          − 0.005 · minutos de espera
          + 0.5   si el día incluye comida fuerte
          − 0.15  por cada par seguido de la misma categoría
          + 0.4   si el grupo es nocturno (interés ≥ 0.5, termina a las 21:00 o después) y hay un bar
```

Un itinerario vacío vale −1e9 (inválido). El fitness es una **métrica propia** del sistema, no una
medida de satisfacción real de las personas. `desglose_fitness` devuelve cada término por separado.

---

## 5. Metodología de evaluación (`comparar_algoritmos.py`)

- 9 perfiles (`app/perfiles_prueba.py`): los 6 originales más adultos mayores, presupuesto mínimo y un lunes de museos.
- **Mismos candidatos** (un solo pool por perfil), mismas restricciones y mismo fitness para todos los algoritmos.
- Voraz: determinista, una corrida por perfil, en dos versiones: `greedy_simple` (una corrida) y `greedy` (con reinicios). Genético: **10 semillas** (0 a 9) en dos variantes: `sin_semilla` (población aleatoria, comparación justa) y `con_semilla_greedy` (el voraz entra a la población).
- Líneas base con las mismas restricciones: `aleatorio` (orden aleatorio, una corrida por semilla) y `orden_por_puntaje` (candidatos en el orden del recomendador, sin optimizar).
- Cada itinerario se valida con `validar_itinerario`.
- Métricas: validez, fitness, lugares, gasto y % del presupuesto, duración total, traslado (min y km caminados, contra el límite del nivel), espera y tiempo de ejecución.
- Regla para no declarar ganadores sin evidencia: A supera a B en un perfil solo si el **peor** resultado de A es mayor que el **mejor** de B; a nivel global se usa la prueba de Wilcoxon sobre las medias por perfil (p < 0.05).
- Salida: `data/resultados/comparacion_detalle.csv` (cada corrida), `comparacion_resumen.csv` y `comparacion.json`.

---

## 6. Resultados reales

Corrida completa con traslados a pie y límite de kilómetros: 9 perfiles, 10 semillas, 80 generaciones,
población 60, 297 lugares. **297 de 297 itinerarios fueron válidos** según la validación independiente y
**ninguno pasó su límite de kilómetros**. Promedios sobre los 9 perfiles:

| Algoritmo | Corridas | Fitness | Lugares | % presupuesto | Duración (min) | Traslado (min) | Km caminados | Espera (min) | Tiempo (s) |
|---|---|---|---|---|---|---|---|---|---|
| aleatorio | 90 | 0.77 | 3.1 | 27.6 | 279 | 61 | 5.0 | 22.3 | 0.000 |
| orden_por_puntaje | 9 | 1.20 | 3.3 | 35.3 | 304 | 54 | 4.5 | 20.0 | 0.000 |
| voraz simple | 9 | 1.91 | 4.4 | 41.3 | 382 | 47 | 3.9 | 10.3 | 0.000 |
| voraz con reinicios | 9 | 2.26 | 5.0 | 49.2 | 400 | 35 | 2.8 | 5.3 | 0.008 |
| genético sin semilla | 90 | 2.43 | 5.7 | 53.0 | 407 | 46 | 3.7 | 0.4 | 0.332 |
| genético con semilla del voraz | 90 | 2.44 | 5.6 | 55.7 | 426 | 42 | 3.3 | 0.3 | 0.327 |

Fitness por perfil (media; para el genético, mínimo–máximo entre las 10 semillas):

| Perfil | Límite de caminata | Voraz simple | Voraz con reinicios | Genético sin semilla |
|---|---|---|---|---|
| Adultos mayores | 3 km | 2.24 | 2.24 | 2.41 (2.28–2.45) |
| Amigos de fiesta | 10 km | 2.44 | 2.80 | 2.95 (2.80–3.00) |
| Amigos en el Centro | 10 km | 1.83 | 2.11 | 2.10 (2.05–2.21) |
| Familia con niños | 6 km | 1.01 | 2.18 | 2.25 (2.17–2.26) |
| Lunes de museos | 6 km | 2.48 | 2.62 | 2.79 (2.50–2.92) |
| Pareja económica | 6 km | 1.39 | 2.14 | 2.18 (2.14–2.24) |
| Pareja romántica | 3 km | 1.63 | 1.63 | 2.21 (2.20–2.29) |
| Presupuesto mínimo | 6 km | 1.60 | 1.79 | 1.94 (1.68–1.98) |
| Solo cultural | 6 km | 2.59 | 2.87 | 3.01 (2.35–3.35) |

**Qué se puede afirmar con estos datos**

- Los reinicios mejoran claramente al voraz: +0.35 de fitness en promedio sobre el voraz simple (Wilcoxon p = 0.0156), y en *Familia con niños* pasan de 2 a 5 paradas.
- El genético obtuvo en promedio más fitness que el voraz con reinicios: +0.16 (Wilcoxon p = 0.0078 con las medias de los 9 perfiles). Pero **la ventaja es pequeña y no es pareja**: con la regla de que el peor resultado del genético supere al mejor del voraz, solo se ve una diferencia clara en 3 de 9 perfiles (Adultos mayores, Amigos de fiesta y Pareja romántica); en los otros 6 no hay diferencia clara, y el genético sin semilla quedó por debajo del voraz en 13 de las 90 corridas (por ejemplo, en *Amigos en el Centro* la media del genético, 2.10, es prácticamente igual a la del voraz, 2.11).
- Ambos superan con claridad a las líneas base (el voraz con reinicios +1.50 sobre el azar; el genético +1.66).
- Meter el voraz en la población inicial del genético casi no cambia el resultado (2.44 contra 2.43).
- El genético coloca algo más de lugares (5.7 contra 5.0) y casi elimina las esperas, a cambio de mucho más tiempo de cómputo (~0.33 s contra ~0.008 s del voraz con reinicios).

**Qué no se puede afirmar**

- Que los itinerarios del genético le gusten más a la gente. Es una ventaja **en nuestro fitness**, y el genético lo optimiza directamente mientras el voraz decide con un criterio miope. Falta la validación con personas (la encuesta ciega).
- Que los resultados valgan para otros perfiles: son 9 perfiles diseñados por el equipo, no usuarios reales.
- Que los resultados anteriores a la caminata (traslados a 18 km/h, sin límite de km) sean comparables con estos: el modelo de traslados cambió, y por eso se volvió a correr todo.

**Efecto de usar los horarios reales.** La versión anterior (commit `9c7615d`) se ejecutó con los mismos 9
perfiles y sus itinerarios se validaron contra los horarios reales de OSM: **8 de 9** itinerarios del
voraz y **5 de 9** del genético tenían al menos un problema (una parada en un lugar cerrado ese día o
que incumple las reglas del perfil). Contando solo las paradas en lugares cerrados según OSM: 8 de 61
(13.1%) en el voraz y 6 de 68 (8.8%) en el genético. Con el código actual esto no puede ocurrir. Aviso: esta medición toma el horario de OSM como verdad, pero OSM lo editan voluntarios y
puede estar desactualizado.

---

## 7. Pruebas automatizadas

```bash
cd backend
python -m pytest
```

265 pruebas, todas pasan (~6 s). Cubren:

- **Horarios:** rangos, días con vuelta, cruce de medianoche, `off`, festivos, y que lo ininterpretable devuelva `None` en lugar de inventar.
- **Restricciones:** cada motivo de rechazo (presupuesto, horario, fin del día, repetidos, categoría, comida, espera, traslado, **límite de kilómetros**) y que `validar_itinerario` detecte cada tipo de violación.
- **Caminata:** que los traslados sean a pie (5 km/h, no 18), que los kilómetros se acumulen y se rechace al pasar el límite de cada nivel, y que ningún itinerario de los 9 perfiles lo exceda.
- **Datos:** coordenadas inválidas, duplicados, campos faltantes, procedencia real/estimada e invariantes del CSV real.
- **Recomendador:** coseno, fórmula del puntaje, que la confianza no sea popularidad, validación y efecto de los pesos, filtros duros y reproducibilidad.
- **Algoritmos (en los 9 perfiles, voraz y las dos variantes del genético):** validez, presupuesto, horarios, ausencia de duplicados, que ambos usen las mismas reglas (la ruta del voraz se reproduce idéntica en el simulador del genético), que el genético con semilla no quede peor que el voraz, reproducibilidad, casos sin solución y casos límite (0, 1 y 2 candidatos).
- **API:** los endpoints principales, ambos algoritmos, reproducibilidad con `semilla`, errores 422, casos sin solución, que el valor por defecto siga siendo el voraz y que cada nivel de caminata devuelva su límite de km.
- **Nombres:** qué es el lugar a partir de la categoría y la cocina de OSM (sin inventar), el detector de otro idioma, que las decisiones no se apliquen al lugar equivocado, la idempotencia y que **ningún nombre del dataset quede en otro idioma sin aclarar**.
- **Página:** que los globos digan los mismos kilómetros que el límite del backend (en el botón y en el globo), que la ruta sea peatonal (`routed-foot`, nunca en carro) y que el perfil mande el nivel elegido.

Para comprobar que las pruebas no son decorativas se introducen fallos a propósito en el código. En la
primera versión de la suite se probaron 11 (quitar el presupuesto, permitir repetidos, ignorar el cierre,
quitar la semilla fija, etc.): se detectaron los 8 que cambian el comportamiento; los otros 3 eran
equivalentes (no cambian nada). Al agregar la caminata, los nombres y la página se repitió con 11 fallos
nuevos (quitar el límite de km, volver a 18 km/h, cambiar el límite de "mucho" a 20 km, quitar los
reinicios, no aclarar nombres, dibujar la ruta en carro, etc.): se detectaron 10 y el undécimo (una
etiqueta de botón que decía 7 km con un globo de 6 km) reveló un hueco en una prueba, que ya se reforzó
y ahora lo detecta.

---

## 8. Relación con los conceptos de IA vistos en clase

Los nombres pueden variar según el temario de la materia; esta es la correspondencia habitual.

| Concepto | Dónde está |
|---|---|
| Representación del conocimiento y del estado | `Perfil` y el vector de 8 intereses (`perfiles.py`); `EstadoDia` y los candidatos (`restricciones.py`). |
| Sistemas basados en reglas / sistema experto | `reglas.py`: filtros duros y bonos por grupo. |
| Recomendación basada en contenido; espacio vectorial y similitud coseno | `recomendador.py`. |
| Incertidumbre y calidad de la información | Procedencia real/estimada, `confianza_datos`, horarios por interpretación estricta (`horarios.py`, `calidad_datos.py`). |
| Problema de satisfacción de restricciones | `revisar_parada` y `validar_itinerario`: restricciones duras compartidas. |
| Búsqueda heurística voraz, óptimos locales y reinicios múltiples (multi-start) | `itinerario.py`. |
| Algoritmos evolutivos (población, selección, cruce de orden, mutación, elitismo) | `genetico.py`. |
| Función objetivo / utilidad | `fitness.py`. |
| Modelado del mundo real (caminata, distancias, horarios) y datos multilingües | `restricciones.py` (traslados a pie y límite de km), `horarios.py`, `nombres.py`. |
| Evaluación experimental (líneas base, semillas, significancia, reproducibilidad) | `comparar_algoritmos.py`, `evaluar_pesos.py`, `tests/`. |

---

## 9. Limitaciones

- **Duración, precio, accesibilidad, nivel de actividad y ambiente son estimaciones por categoría**, no datos de OSM. Lo único real sobre el precio es la etiqueta `fee=no` (18 lugares).
- **El 20.5% de los lugares (61 de 297) no tiene horario real interpretable** y usa un horario estimado por categoría; en los itinerarios cada parada declara su `horario_fuente`. Los horarios de OSM los editan voluntarios y pueden estar desactualizados; los festivos no se modelan.
- **La popularidad real no se mide.** Falta una columna `fama` con datos reales.
- **Hay 24 lugares a más de 5 km del centro de la zona que tienen asignada** (por ejemplo, un mercado de Xochimilco etiquetado "Coyoacán"). La zona se asigna por el centro más cercano de solo 5. Están marcados, no excluidos.
- Una sola sucursal por nombre y categoría: se perdieron las demás sucursales de las cadenas.
- Queda un posible duplicado por revisar a mano: *Ramen-ya Rokai* y *Rokai* (mismo restaurante capturado dos veces en OSM); el script solo lo marca. En la práctica no pueden salir los dos en un mismo día porque solo se permite una comida fuerte.
- **Los traslados son a pie y los kilómetros son estimados**: línea recta × 1.3 a 5 km/h, sin considerar pendientes, cruces ni banquetas. La ruta real que traza la página puede dar una distancia distinta (más o menos). Los límites de 3, 6 y 10 km por nivel son un criterio del equipo, sin respaldo en un estudio. Cuentan solo los traslados entre lugares, no lo que se camina dentro de ellos.
- **La ruta por las calles depende de un servicio externo gratuito** (`routing.openstreetmap.de`): necesita internet y puede fallar o limitar el uso. Si no responde, la página dibuja una línea recta punteada aproximada y lo avisa. (Esta parte solo se pudo probar con el servicio simulado, no contra el servicio real.)
- Con un límite de caminata los lugares muy lejanos entre sí no caben en el mismo día: el itinerario se queda en una parte de la ciudad (con *Poco*, en una zona reducida). No hay transporte público ni vehículo como opción.
- **Los nombres en otro idioma se decidieron a mano** (54 aclarados y 2 eliminados, en `app/nombres.py`); puede haber casos discutibles y los lugares nuevos que se agreguen hay que revisarlos (el reporte de calidad avisa con `nombre_otro_idioma_sin_aclarar`).
- Itinerario de un solo día, solo para la CDMX, con 40 candidatos por perfil.
- El fitness es propio del sistema; que un algoritmo lo optimice mejor no prueba que a la gente le gusten más sus itinerarios. Falta la encuesta ciega con personas.
- La evaluación usa 9 perfiles sintéticos; los pesos de los términos del fitness no se han sometido a un análisis de sensibilidad.
- La página todavía no tiene selector de algoritmo (la API sí).
