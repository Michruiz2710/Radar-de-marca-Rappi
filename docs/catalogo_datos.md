# Catálogo de datos

**Paquete:** P3.5 Gobierno, linaje y cierre · **Autora:** Michelle · **Coautora:** Katalina · **Revisor:** Gabriel

Lista de todos los datos que guarda el proyecto: dónde están, quién responde por ellos, qué tan sensibles son y cuándo se borran. Si un paquete crea o cambia una tabla, su autor actualiza este catálogo en el mismo Pull Request.

Las reglas generales (finalidad, seudonimización, retención) están en [`politica_datos.md`](politica_datos.md) y el recorrido de los datos en [`linaje.md`](linaje.md).

## Niveles de sensibilidad

| Nivel | Qué significa | Quién accede |
| --- | --- | --- |
| **Restringido** | Texto tal como lo escribió la persona, sin enmascarar: puede contener correos, teléfonos o nombres que el autor escribió en su reseña | Solo el pipeline y quien tenga las credenciales del entorno |
| **Interno** | Datos seudonimizados y con datos personales enmascarados. Sirven para análisis, pero no se publican fila por fila | Integrantes del equipo |
| **Público** | Agregados (conteos, porcentajes, promedios) y metadatos sin información de personas | Cualquiera (dashboard, presentación) |

Ningún conjunto guarda nombres de usuario, fotos ni enlaces a perfiles: el contrato de datos los rechaza (`extra="forbid"` en `src/common/schema.py`).

## Dónde vive cada entorno

| Entorno | Bucket de MinIO | Esquema clean | Esquema analytics | Dónde corre |
| --- | --- | --- | --- | --- |
| dev | `radar-rappi` | `clean` | `analytics` | Docker de cada integrante |
| staging | `radar-rappi-staging` | `clean_staging` | `analytics_staging` | Runner de GitHub Actions al fusionar en `main` |
| prod | `radar-rappi-prod` | `clean_prod` | `analytics_prod` | Runner de GitHub Actions al publicar una release |

Los runners de staging y prod son máquinas temporales: el CD termina con `docker compose down -v`, así que esos datos se borran al final de cada despliegue. Los datos que se conservan están solo en el Docker de cada integrante (dev).

## Conjuntos de datos

### Capa raw (MinIO)

| Conjunto | Ubicación | Dueño | Escribe | Lee | Sensibilidad | Retención |
| --- | --- | --- | --- | --- | --- | --- |
| Reseñas de Google Play | `raw/fuente=google_play/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl` | Katalina (P1.3) | Scraper de Google Play | Validación cruda (P2.2), limpieza (P2.3) | Restringido | Hasta el fin del curso |
| Comentarios de YouTube | `raw/fuente=youtube/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl` | Gabriel (P1.4) | Scraper de YouTube | Validación cruda, limpieza | Restringido | Hasta el fin del curso |
| Noticias de Google News | `raw/fuente=news/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl` | Sara (P1.5) | Scraper de noticias | Validación cruda, limpieza | Interno (titulares de medios, sin autores) | Hasta el fin del curso |

- **Campos:** los del contrato de datos v1.3.0, en [`contrato_datos.md`](contrato_datos.md).
- **Inmutable:** cada corrida escribe un archivo nuevo y nadie modifica ni borra archivos de raw. Una reseña editada aparece de nuevo en otra corrida y la limpieza conserva la versión más reciente.
- **Por qué es restringido:** el campo `texto` es la reseña original. El autor ya está seudonimizado (`autor_hash`), pero el texto puede traer datos personales que la persona escribió. Se enmascaran recién en la capa clean.

### Estado interno de los scrapers

| Conjunto | Ubicación | Dueño | Para qué sirve | Sensibilidad | Retención |
| --- | --- | --- | --- | --- | --- |
| Enlaces de noticias vistos | MinIO, `state/fuente=news/enlaces_vistos.json` | Sara (P1.5) | No volver a guardar noticias ya leídas | Interno | Hasta el fin del curso |
| Marca de agua de Google Play | Volumen Docker `google_play_estado`, `estado/google_play_marca_agua.json` | Katalina (P1.3) | Pedir solo reseñas nuevas en cada corrida | Interno (fechas e IDs, sin texto) | Hasta el fin del curso |

No siguen el contrato de datos y nadie más debe leerlos.

### Capa clean (Postgres)

| Tabla | Dueño | Escribe | Lee | Sensibilidad | Retención |
| --- | --- | --- | --- | --- | --- |
| `menciones` | Michelle (P2.3) | Limpieza (`src/transform/clean`) | Validación limpia (P2.2), sentimiento (P2.4), dbt (P3.4) | Interno | Hasta el fin del curso |
| `sentimiento` | Jonathan (P2.4) | Sentimiento y temas (`src/transform/nlp`) | dbt (P3.4) | Interno | Hasta el fin del curso |

**`menciones`:** una fila por mención (`id_registro`), con el texto limpio y los datos personales enmascarados (`[CORREO]`, `[URL]`, `[TELEFONO]`, `[NUMERO]`). No guarda el texto original. Marca los bots sin borrarlos (`es_bot`, `motivo_bot`). Columnas y garantías en [`contrato_clean.md`](contrato_clean.md). Volumen actual: 11.090 filas (507 Google Play, 10.520 YouTube, 63 noticias).

**`sentimiento`:** una fila por mención analizada (solo español y sin bots).

| Columna | Descripción |
| --- | --- |
| `id_registro` | Clave, la misma de `menciones` |
| `hash_texto` | Hash del texto analizado. Si cambia en `menciones`, se vuelve a analizar |
| `sentimiento` | `positivo`, `neutro` o `negativo` |
| `prob_sentimiento`, `prob_positivo`, `prob_neutro`, `prob_negativo` | Probabilidades del modelo |
| `tema` | Tema principal según el diccionario de palabras clave (`otro` si no hay coincidencias) |
| `temas_detectados` | Todos los temas encontrados, separados por coma |
| `version_modelo`, `version_nlp` | Versión exacta del modelo y del código, para explicar cada resultado |
| `procesado_en` | Cuándo se analizó (UTC) |

Exactitud medida contra las 200 reseñas etiquetadas en [`evaluacion_nlp.md`](evaluacion_nlp.md).

### Capa analytics (Postgres, dbt)

La construye dbt (P3.4, dueño: Gabriel) a partir de `clean.menciones` y `clean.sentimiento`. Corre como última etapa del flujo de Prefect (`flows/modelos.py`) o a mano con `make dbt`. Cada `dbt build` reconstruye las tablas y corre 44 pruebas (`unique`, `not_null`, `accepted_values`, rangos y que el resumen cuadre con clean). Retención de todo el esquema: hasta el fin del curso.

| Objeto | Tipo | Grano | Qué contiene | Lee | Sensibilidad |
| --- | --- | --- | --- | --- | --- |
| `stg_menciones` | Vista | Una fila por mención | Copia ordenada de `clean.menciones` | Modelos de dbt | Interno |
| `stg_sentimiento` | Vista | Una fila por mención analizada | Copia ordenada de `clean.sentimiento` | Modelos de dbt | Interno |
| `fct_menciones` | Tabla | Una fila por mención real (sin bots) | Texto limpio, fecha en hora de Colombia, calificación, versión de la app, respuesta de Rappi, sentimiento y tema vigentes | Dashboard (P3.3) | Interno: tiene texto e identificadores |
| `agg_sentimiento_diario` | Tabla | Día y fuente | Menciones, analizadas, positivas, neutras, negativas, `pct_negativo` e índice neto | Análisis | Público |
| `agg_temas_semanal` | Tabla | Semana, fuente y tema | Menciones, negativas, `pct_negativo` y calificación promedio | Análisis | Público |
| `agg_calificacion_version` | Tabla | Versión de la app (mayor.menor) | Reseñas, calificación promedio, % de 1 y 2 estrellas y si la muestra es suficiente (10 o más reseñas) | Análisis | Público |
| `agg_respuesta_marca_semanal` | Tabla | Semana | Tasa de respuesta de Rappi (general y en 1 y 2 estrellas) y mediana de horas hasta responder | Análisis | Público |
| `agg_noticias_vs_sentimiento` | Tabla | Día | Noticias publicadas y sentimiento negativo en reseñas y comentarios, para ver si coinciden | Análisis | Público |
| `resumen_fuentes` | Tabla | Fuente | Totales de toda la historia: menciones, bots, analizadas y cuántas entran a los modelos. Es el único modelo que cuenta los bots | Análisis, control de calidad | Público |

- **El dashboard lee solo `fct_menciones`** y calcula ahí sus filtros por fecha y fuente. Las tablas `agg_` quedan disponibles para análisis y consultas directas.
- **Bots:** `fct_menciones` y las `agg_` excluyen los bots (prueba `fct_sin_bots`). Solo `resumen_fuentes` los cuenta, para saber cuántos se filtraron.
- **Columnas y pruebas de cada modelo:** `dbt/models/marts/_marts.yml`. Documentación navegable y linaje automático con `make dbt-docs` (http://localhost:8080).

### Otros datos

| Conjunto | Ubicación | Dueño | Para qué sirve | Sensibilidad | Retención |
| --- | --- | --- | --- | --- | --- |
| Muestra etiquetada | Git, `data/etiquetas/muestra_200.csv` | Sara (P1.5); etiquetaron Sara y Gabriel | Medir la exactitud del sentimiento y los temas | Interno (ver riesgo abajo) | Hasta el fin del curso |
| Data Docs de Great Expectations | Carpeta `data/data_docs/` del repositorio (montada en el orquestador; fuera de Git) | Katalina (P2.2) | Reportes HTML de cada validación. Se abren con `data/data_docs/index.html` | Interno (conteos y reglas, sin textos completos) | Hasta el fin del curso |
| Evaluación del modelo | Git, `docs/evaluacion_nlp.md` | Jonathan (P2.4) | Métricas del sentimiento y los temas | Público | Permanente |

### Observabilidad

| Conjunto | Ubicación | Dueño | Qué guarda | Sensibilidad | Retención |
| --- | --- | --- | --- | --- | --- |
| Métricas del pipeline | Volúmenes `pushgateway_data` y `prometheus_data` | Sara (P3.1) | Conteos por fuente, errores HTTP, duración, fallas, validaciones fallidas, % de bots, cuota de YouTube y % negativo de 24 h. Lista completa en `src/observability/README.md` | Público (solo números y etiquetas de flujo o fuente) | Hasta el fin del curso |
| Logs | Salida de cada contenedor (`docker logs`) | Sara (P3.1) | Logs en JSON con `run_id`, fuente, nivel y mensaje | Interno | Mientras exista el contenedor |
| Grafana | Volumen `grafana_data`; dashboards y alertas como código en `infra/grafana/` | Jonathan (P3.2) | Historial de alertas y estado de los avisos. El dashboard técnico y las reglas A1–A8 viven en Git | Interno | Hasta el fin del curso |
| Corridas de Prefect | Base de datos interna del servicio `prefect` | Sara (P2.1) | Estado, duración y logs de cada corrida y etapa | Interno | Hasta el fin del curso |

**Riesgo identificado en la muestra etiquetada.** Es el único dato de personas que está en Git, y el repositorio es público. Tiene 200 reseñas de Google Play con su texto original y su `id_registro`, que incluye el `reviewId` de Google Play. No trae nombres ni datos que el enmascarado detecte (se revisó con `enmascarar()`: 0 coincidencias), pero el texto y el `reviewId` permiten encontrar la reseña original en Google Play y, desde ahí, el nombre de quien la escribió. Decisión pendiente para el equipo, antes de la entrega: volver privado el repositorio al terminar el curso, o reemplazar el `id_registro` de la muestra por un identificador propio.

## Metadatos de trazabilidad

Cada fila lleva lo necesario para saber de dónde salió y con qué código se procesó:

| Campo | Dónde | Qué responde |
| --- | --- | --- |
| `run_id` | raw y `menciones` | En qué corrida del scraper se extrajo |
| `version_scraper` | raw y `menciones` | Qué versión del scraper la extrajo (hoy 0.1.0 en los tres) |
| `version_contrato` | raw y `menciones` | Con qué versión del contrato se validó (hoy 1.3.0) |
| `version_limpieza` | `menciones` | Con qué reglas de limpieza y bots se procesó (hoy 1.3.0) |
| `hash_texto` | `menciones` y `sentimiento` | Si el sentimiento corresponde al texto vigente |
| `version_modelo`, `version_nlp` | `sentimiento` | Qué modelo y qué código calcularon el sentimiento |
| `procesado_en` | `menciones` y `sentimiento` | Cuándo se procesó |
