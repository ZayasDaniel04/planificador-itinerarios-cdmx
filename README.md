# Planificador inteligente de itinerarios turísticos de la CDMX

Proyecto final de Inteligencia Artificial. Una página web arma el itinerario de **un día** en la
Ciudad de México para parejas, personas solas, grupos de amigos y familias, según el tipo de grupo,
el número de personas, si hay niños o adultos mayores, el presupuesto por persona, el horario, el
nivel de caminata, la zona, el día de la semana y los intereses.

El núcleo de IA es propio (no depende de un LLM): recomendador basado en contenido, sistema experto
de reglas, y dos optimizadores del itinerario (voraz y genético) que se comparan con el mismo
criterio.

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
| `app/perfiles_prueba.py` | Perfiles de ejemplo compartidos por los scripts de evaluación y las pruebas. |
| `app/main.py` | API FastAPI. |
| `comparar_algoritmos.py` | Experimento voraz vs genético (varias semillas, exporta CSV/JSON). |
| `evaluar_pesos.py` | Análisis de sensibilidad de los pesos del recomendador. |
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
```

### API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Estado y número de lugares. |
| POST | `/recomendar` | Mejores lugares sueltos, con el desglose del puntaje (`sim`, `ajuste`, `confianza`, `precio_rel`). |
| POST | `/itinerario` | Día armado: `paradas`, `resumen`, `algoritmo`, `valido`, `violaciones`, `mensaje`. |

Campos de `/itinerario`: `tipo_grupo`, `personas`, `hay_ninos`, `hay_adultos_mayores`,
`presupuesto_por_persona`, `nivel_actividad` (1 a 3), `zona`, `dia_semana`, `intereses` (pesos de 0
a 1), `hora_inicio`, `hora_fin`, y opcionalmente `algoritmo` (`"greedy"` por defecto o `"genetico"`)
y `semilla` (solo afecta al genético: misma semilla, mismo itinerario).

- Un perfil inválido (horas al revés, presupuesto negativo, zona inexistente...) responde **422** con la lista de problemas.
- Si no hay itinerario posible responde **200** con `paradas: []` y un `mensaje` que explica por qué.
- Toda respuesta se revisa con `validar_itinerario` antes de entregarse; `valido` y `violaciones` lo reflejan.
- La página actual no manda `algoritmo`, así que sigue usando el voraz. El genético se puede probar desde `/docs`.

---

## 3. Datos

`data/lugares_limpio.csv`: 299 lugares de OpenStreetMap en 5 zonas (Centro Histórico, Roma-Condesa,
Polanco-Chapultepec, Coyoacán, San Ángel) y 15 categorías.

### Dato real vs estimación

OpenStreetMap **no** trae duración de la visita, precio, accesibilidad ni ambiente. Esos campos son
valores por defecto de la categoría (`DEFECTOS_CATEGORIA` en `app/calidad_datos.py`) y el sistema no
los presenta como datos reales. Cada procedencia queda registrada en el CSV:

| Columna | Valores | Qué significa |
|---|---|---|
| `horario_fuente` | `osm` / `estimado_categoria` | `osm`: horario real interpretado, por día de la semana. Medido: **237 de 299 (79.3%)**. |
| `costo_fuente` | `osm_fee_no` / `estimado_categoria` / `manual` | `osm_fee_no`: OSM dice que es gratis (19 lugares). El monto de los demás es una estimación. |
| `duracion_fuente` | `estimado_categoria` / `manual` | Hoy los 299 son estimados. |
| `atributos_fuente` | `estimado_categoria` / `manual_parcial` | Origen de nivel de actividad, apto niños, apto adultos mayores y ambiente (hoy todos estimados). |
| `osm_id`, `costo_osm` | | Vínculo con OSM y su etiqueta `fee`. |
| `campos_faltantes` | | Información real que OSM no trae para ese lugar. |
| `usable` | 1 / 0 | 0 = no se puede usar (coordenadas inválidas, campos obligatorios vacíos o duplicado exacto). `cargar_lugares()` lo respeta. |
| `calidad_flags` | | Alertas para revisar (ver abajo). |

Reglas que se siguen: no se inventan horarios, precios ni condiciones de accesibilidad. El único
valor que se corrige a partir de OSM es el costo 0 cuando OSM dice `fee=no` y el costo era el valor por
defecto (9 museos y 3 zoológicos cambiaron de $80 o $50 a $0); un costo puesto a mano nunca se pisa.
Los horarios que no se pueden interpretar con certeza (6 textos, por ejemplo `Su`, `Th`, un `+` abierto o
una falta de guion) se tratan como estimados y se marcan.

### Revisión de calidad (`python mejorar_dataset.py`)

Resultado sobre el dataset actual (`data/reporte_calidad.json`, `data/calidad_registros.csv`):

| Revisión | Resultado |
|---|---|
| Coordenadas inválidas (vacías, en cero, invertidas, fuera de la zona de estudio) | 0 |
| Pares de posibles duplicados (mismo nombre normalizado, misma ubicación o nombre muy parecido y cercano) | 0 |
| Lugares a más de 5 km del centro de la zona asignada (`lejos_de_su_zona`) | 24 |
| Horario de OSM que no se pudo interpretar | 6 |
| Nombre en alfabeto no latino, para revisar a mano (`シティオ`) | 1 |
| Coordenada apenas fuera de la caja de descarga, solo advertencia (Zoológico de San Juan de Aragón) | 1 |
| Campos vacíos: `horario_osm` / `sitio_web` / `tipo_comida` | 56 / 104 / 205 |

El script **solo detecta y etiqueta**; no borra lugares. Revisar a mano lo marcado es decisión del equipo.

### Flujo de datos

```
descargar_lugares.py / descargar_faltantes.py  ->  data/lugares_raw.csv (5,288 lugares)
limpiar_dataset.py   (solo para regenerar desde cero)  ->  data/lugares_limpio.csv
mejorar_dataset.py   (procedencia y calidad, seguro de repetir)
```

`limpiar_dataset.py` regenera el CSV desde el crudo y **borraría las correcciones manuales**; por eso
se niega a sobrescribirlo sin `--forzar`. Al verificarlo, regenera exactamente los 299 lugares actuales
más los 3 que el equipo borró a mano (Vips, Sólo Salida / Only Exit, Forum Buenavista). Decisión de
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
| similitud ×0 (apagada) | 41% | 28% | 100% |
| reglas ×0 | 87% | 61% | 99% |
| confianza ×0 | 56% | 48% | 94% |
| precio ×0 | 80% | 68% | 99% |
| esquema original (sitio web = "popularidad") | 61% | 38% | 87% |

Lectura: como la similitud es igual para toda una categoría, el orden **dentro** de cada categoría lo
deciden `confianza`, `precio` y las reglas; por eso un peso de solo 0.10 mueve tanto el top 10. El
esquema original producía un itinerario muy distinto (solo 38% de lugares en común con el nuevo) y con
menos lugares de horario verificable. Este análisis mide **cuánto cambian** las recomendaciones, no cuál
es "mejor": eso requiere usuarios reales.

### 4.3 Restricciones compartidas (`restricciones.py`)

El voraz y el genético llaman a **la misma función** (`revisar_parada`); antes cada uno tenía su propia
copia. Un itinerario inválido no puede salir de ninguno:

1. No se repiten lugares (ni por `id` ni por nombre normalizado).
2. La visita completa cabe en una ventana de apertura de ese día (horario real de OSM; si no hay, estimación por categoría).
3. La última salida no pasa de la hora de fin.
4. El gasto acumulado por persona no pasa del presupuesto.
5. Duración exacta de cada visita; traslado Haversine a 18 km/h (mínimo 5 min); no se llega antes de terminar el lugar anterior más el traslado.
6. Espera máxima de 120 min antes de una visita.
7. Máximo por categoría: 1 cafetería, 1 librería y 1 cine; 2 de cualquier otra.
8. Una sola comida fuerte (restaurante o mercado), que empiece entre 12:30 y 16:00.
9. Perfil del visitante: todo lugar debe pasar `pasa_filtros`.

`validar_itinerario(ruta, perfil, df)` revisa todo esto de forma **independiente** (recalcula desde las
paradas, sin reutilizar el estado de la simulación) y se usa en la API, en el experimento y en las pruebas.

### 4.4 Voraz (`itinerario.py`)

En cada paso elige, entre los lugares que sí se pueden agregar, el de mayor valor inmediato
(`puntaje − 0.01·traslado − 0.005·espera − 0.15 si repite categoría + 0.5 si es la primera comida`).
Prefiere esperas ≤ 45 min y solo si no hay opciones las relaja hasta 120. Si el grupo es nocturno,
reserva presupuesto para un bar (heurística propia del voraz, no una restricción). Nunca reconsidera una
decisión, por eso puede quedar en un óptimo local.

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
- Voraz: determinista, una corrida por perfil. Genético: **10 semillas** (0 a 9) en dos variantes: `sin_semilla` (población aleatoria, comparación justa) y `con_semilla_greedy` (el voraz entra a la población).
- Líneas base con las mismas restricciones: `aleatorio` (orden aleatorio, una corrida por semilla) y `orden_por_puntaje` (candidatos en el orden del recomendador, sin optimizar).
- Cada itinerario se valida con `validar_itinerario`.
- Métricas: validez, fitness, lugares, gasto y % del presupuesto, duración total, traslado, espera y tiempo de ejecución.
- Regla para no declarar ganadores sin evidencia: A supera a B en un perfil solo si el **peor** resultado de A es mayor que el **mejor** de B; a nivel global se usa la prueba de Wilcoxon sobre las medias por perfil (p < 0.05).
- Salida: `data/resultados/comparacion_detalle.csv` (cada corrida), `comparacion_resumen.csv` y `comparacion.json`.

---

## 6. Resultados reales

Corrida completa: 9 perfiles, 10 semillas, 80 generaciones, población 60, 299 lugares. **288 de 288
itinerarios fueron válidos** según la validación independiente. Promedios sobre los 9 perfiles:

| Algoritmo | Corridas | Fitness | Lugares | % presupuesto | Duración (min) | Traslado (min) | Espera (min) | Tiempo (s) |
|---|---|---|---|---|---|---|---|---|
| aleatorio | 90 | 1.51 | 5.8 | 44.9 | 491 | 103 | 29.7 | 0.000 |
| orden_por_puntaje | 9 | 1.70 | 5.7 | 37.2 | 475 | 89 | 28.6 | 0.000 |
| voraz (greedy) | 9 | 2.68 | 6.2 | 57.0 | 481 | 49 | 20.8 | 0.001 |
| genético sin semilla | 90 | 3.25 | 7.2 | 60.6 | 504 | 43 | 0.1 | 0.448 |
| genético con semilla del voraz | 90 | 3.25 | 7.2 | 58.3 | 501 | 42 | 0.0 | 0.455 |

Fitness por perfil, voraz contra genético sin semilla (media, mínimo–máximo entre las 10 semillas):

| Perfil | Voraz | Genético sin semilla |
|---|---|---|
| Adultos mayores | 2.80 | 3.36 (3.09–3.61) |
| Amigos de fiesta | 2.60 | 3.14 (3.10–3.17) |
| Amigos en el Centro | 1.86 | 2.59 (2.57–2.61) |
| Familia con niños | 2.89 | 3.28 (3.08–3.41) |
| Lunes de museos | 2.67 | 3.27 (3.23–3.28) |
| Pareja económica | 2.87 | 3.49 (3.32–3.62) |
| Pareja romántica | 2.54 | 3.50 (3.46–3.54) |
| Presupuesto mínimo | 2.60 | 3.12 (2.97–3.24) |
| Solo cultural | 3.24 | 3.54 (3.36–3.59) |

**Qué se puede afirmar con estos datos**

- El genético obtuvo mayor fitness que el voraz en los 9 perfiles, y su peor corrida superó al voraz en todos (0 de 90 corridas peores). Diferencia media +0.58; Wilcoxon p = 0.0039 (es el valor más pequeño posible con 9 perfiles, porque los 9 favorecen al genético).
- Ambos superan con claridad a las líneas base (el voraz +1.17 sobre el azar; el genético +1.75).
- Meter el voraz en la población inicial no cambió el resultado del genético (3.251 contra 3.252).
- El genético coloca más lugares (7.2 contra 6.2) y casi elimina las esperas, a cambio de cientos de veces más tiempo de cómputo (~0.45 s contra ~0.001 s, unas 600 veces).

**Qué no se puede afirmar**

- Que los itinerarios del genético le gusten más a la gente. Es una ventaja **en nuestro fitness**, y el genético lo optimiza directamente mientras el voraz decide con un criterio miope; una ventaja ahí era esperable. Falta la validación con personas (la encuesta ciega).
- Que los resultados valgan para otros perfiles: son 9 perfiles diseñados por el equipo, no usuarios reales.

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

183 pruebas, todas pasan (~7 s). Cubren:

- **Horarios:** rangos, días con vuelta, cruce de medianoche, `off`, festivos, y que lo ininterpretable devuelva `None` en lugar de inventar.
- **Restricciones:** cada motivo de rechazo (presupuesto, horario, fin del día, repetidos, categoría, comida, espera, traslado) y que `validar_itinerario` detecte cada tipo de violación.
- **Datos:** coordenadas inválidas, duplicados, campos faltantes, procedencia real/estimada e invariantes del CSV real.
- **Recomendador:** coseno, fórmula del puntaje, que la confianza no sea popularidad, validación y efecto de los pesos, filtros duros y reproducibilidad.
- **Algoritmos (en los 9 perfiles, voraz y las dos variantes del genético):** validez, presupuesto, horarios, ausencia de duplicados, que ambos usen las mismas reglas (la ruta del voraz se reproduce idéntica en el simulador del genético), que el genético con semilla no quede peor que el voraz, reproducibilidad, casos sin solución y casos límite (0, 1 y 2 candidatos).
- **API:** los endpoints principales, ambos algoritmos, reproducibilidad con `semilla`, errores 422, casos sin solución y que el valor por defecto siga siendo el voraz.

Para comprobar que las pruebas no son decorativas se introdujeron 11 fallos a propósito en el código
(quitar el presupuesto, permitir repetidos, ignorar el cierre, quitar la semilla fija, etc.): las pruebas
detectaron los 8 que cambian el comportamiento; los otros 3 eran equivalentes (no cambian nada).

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
| Búsqueda heurística voraz y óptimos locales | `itinerario.py`. |
| Algoritmos evolutivos (población, selección, cruce de orden, mutación, elitismo) | `genetico.py`. |
| Función objetivo / utilidad | `fitness.py`. |
| Evaluación experimental (líneas base, semillas, significancia, reproducibilidad) | `comparar_algoritmos.py`, `evaluar_pesos.py`, `tests/`. |

---

## 9. Limitaciones

- **Duración, precio, accesibilidad, nivel de actividad y ambiente son estimaciones por categoría**, no datos de OSM. Lo único real sobre el precio es la etiqueta `fee=no` (19 lugares).
- **El 20.7% de los lugares (62 de 299) no tiene horario real interpretable** y usa un horario estimado por categoría; en los itinerarios cada parada declara su `horario_fuente`. Los horarios de OSM los editan voluntarios y pueden estar desactualizados; los festivos no se modelan.
- **La popularidad real no se mide.** Falta una columna `fama` con datos reales.
- **Hay 24 lugares a más de 5 km del centro de la zona que tienen asignada** (por ejemplo, un mercado de Xochimilco etiquetado "Coyoacán"). La zona se asigna por el centro más cercano de solo 5. Están marcados, no excluidos.
- Una sola sucursal por nombre y categoría: se perdieron las demás sucursales de las cadenas.
- Quedan registros dudosos por revisar a mano: `シティオ` (marcado automáticamente) y "Sólo Entrada / Only Entrance" (categoría zoológico, sin sitio web), que podría ser una puerta del Zoológico de Chapultepec y no un lugar visitable, parecida a "Sólo Salida / Only Exit", que el equipo ya había borrado. Conviene revisarlos; el script no los borra.
- Traslados en línea recta (Haversine) a velocidad constante de 18 km/h, sin tráfico ni rutas reales.
- Itinerario de un solo día, solo para la CDMX, con 40 candidatos por perfil.
- El fitness es propio del sistema; que un algoritmo lo optimice mejor no prueba que a la gente le gusten más sus itinerarios. Falta la encuesta ciega con personas.
- La evaluación usa 9 perfiles sintéticos; los pesos de los términos del fitness no se han sometido a un análisis de sensibilidad.
- La página todavía no tiene selector de algoritmo (la API sí).
