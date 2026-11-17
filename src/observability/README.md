# Métricas y logs

Publicación de métricas a Pushgateway y logs estructurados en JSON con `run_id`.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.1 Métricas y logs | Sara | Gabriel | Jonathan | Semana 3 |

## Qué hay aquí

| Archivo | Qué hace |
| --- | --- |
| `metricas.py` | Cuenta durante la corrida, acumula en `data/estado/metricas.json` y publica todo en el Pushgateway |
| `consultas.py` | Calcula en la capa clean la proporción de bots y de sentimiento negativo de las últimas 24 h |
| `logs.py` | Formato JSON común y contexto con `run_id` y `fuente` |

## Métricas

Las publica el orquestador al final de cada corrida del flujo `pipeline`, en el grupo `job="radar_pipeline"` del Pushgateway. Son **10 en total**: las 8 que pide la ruta de trabajo y 2 de apoyo para las alertas de P3.2.

### Las 8 de la ruta de trabajo

| Métrica | Tipo | Etiquetas | De dónde sale |
| --- | --- | --- | --- |
| `registros_extraidos_total` | contador | `fuente` | Registros del archivo raw de la corrida (0 si no hubo nuevos) |
| `errores_http_total` | contador | `fuente`, `codigo` | Respuestas con error de Google News, la API de YouTube y Google Play. `conexion` si no hubo respuesta |
| `duracion_corrida_segundos` | histograma | `flujo` | Desde el inicio hasta el fin de la corrida en Prefect |
| `ultima_corrida_exitosa_timestamp` | gauge | `flujo` | Hora Unix de la última corrida exitosa (alerta A3) |
| `validaciones_fallidas_total` | contador | `suite`, `severidad` | Reglas fallidas de P2.2 (`critica` o `advertencia`) |
| `registros_bot_ratio` | gauge | `fuente` | Proporción de `es_bot` entre lo procesado en las últimas 24 h |
| `cuota_youtube_usada` | gauge | — | Unidades de la API de YouTube usadas hoy (se reinicia a medianoche del Pacífico) |
| `sentimiento_negativo_24h_ratio` | gauge | `fuente` | Proporción de negativos entre lo publicado en las últimas 24 h, sin bots |

### Las 2 de apoyo (no están en la ruta de trabajo)

| Métrica | Tipo | Etiquetas | Para qué |
| --- | --- | --- | --- |
| `fallas_consecutivas` | gauge | `flujo` | Corridas fallidas seguidas; vuelve a 0 con una exitosa (alerta A1) |
| `ultima_corrida_fallida_timestamp` | gauge | `flujo` | Hora Unix de la última corrida fallida. Solo aparece después de la primera falla |

### Valores de la etiqueta `flujo`

Sale de los parámetros de la corrida en Prefect (`flows/metricas.py`, `_nombre_flujo`): si la corrida es de una sola fuente, `flujo` es `pipeline:<fuente>`; si no, es `pipeline`.

| `flujo` | Despliegue | Frecuencia |
| --- | --- | --- |
| `pipeline:news` | `news-<entorno>` | cada 2 h |
| `pipeline:google_play` | `google_play-<entorno>` | cada 3 h |
| `pipeline:youtube` | `youtube-<entorno>` | cada 6 h |
| `pipeline` | `todas-<entorno>` (las tres fuentes) | manual, sin horario |

Como `pipeline` no tiene horario, conviene dejarlo fuera de A3: si nadie lo corre, `ultima_corrida_exitosa_timestamp{flujo="pipeline"}` envejece sin que haya un problema.

### Ideas para las alertas de P3.2

| Alerta | Expresión posible |
| --- | --- |
| A1 | `fallas_consecutivas >= 2` |
| A2 | `increase(registros_extraidos_total{fuente="google_play"}[6h]) == 0` |
| A3 | `time() - ultima_corrida_exitosa_timestamp{flujo="pipeline:news"} > 4 * 3600` (el doble de 2 h; igual con 6 h para Google Play y 12 h para YouTube) |
| A4 | `increase(validaciones_fallidas_total{severidad="critica"}[1h]) > 0` |
| A5 | `sentimiento_negativo_24h_ratio > 0.6` |
| A7 | `cuota_youtube_usada > 8000` |

A6 (menciones del día contra el promedio de 7 días) puede salir de `increase(registros_extraidos_total[1d])`.

## Decisiones de diseño

- **Pushgateway y contadores:** cada corrida es un proceso nuevo, así que los contadores no pueden vivir en memoria. Se acumulan en `data/estado/metricas.json` (volumen `google_play_estado`) y cada corrida publica el total; así nunca bajan aunque el orquestador se reinicie. Un candado evita que dos corridas que terminan a la vez se pisen.
- **Series en 0:** `registros_extraidos_total` por fuente, `errores_http_total` con 403 y 429 por fuente, y `validaciones_fallidas_total` por suite y severidad empiezan en 0, para que aparezcan en Prometheus desde la primera corrida.
- **Nunca detienen el pipeline:** si el Pushgateway o Postgres no responden, solo queda un aviso en el log.

## Errores de Google Play

`errores_http_total{fuente="google_play"}` casi siempre queda en 0, aunque Google Play responda con error. Lo comprobamos en el código de `google-play-scraper==1.2.7`:

- `utils/request.py` convierte el error HTTP en `NotFoundError` (404) o en `ExtraHTTPError("... Status code 429 returned.")`, que no guarda el código como atributo. El límite de peticiones (`PlayGatewayError`) llega como un `Exception` genérico.
- `features/reviews.py` atrapa cualquier excepción al pedir una página y devuelve la lista vacía. Por eso `reviews()` casi nunca lanza nada: un 429 se ve como una página sin reseñas.

`pedir_pagina` cuenta lo que sí alcanza a lanzar, con `codigo="error"` cuando no hay código. **Para Google Play, la alerta A2 debe basarse solo en `registros_extraidos_total`.**

## Logs

Cada línea es un objeto JSON con `timestamp`, `nivel`, `fuente`, `run_id`, `logger` y `mensaje`, más los campos que se pasen con `extra`. Dentro del orquestador, `run_id` es el id de la corrida en Prefect y `fuente` la de la tarea que está corriendo, así que los logs de los scrapers, la limpieza y las validaciones quedan unidos a su corrida.

Lo usan el orquestador, los tres scrapers, la limpieza y el NLP cuando se corren solos. Las líneas internas de Prefect (por ejemplo `Finished in state Completed`) conservan el formato de Prefect.

## Pruebas

```bash
python -m pytest -q tests/observability tests/flows
```

## Estado

Hecho: Prometheus y Pushgateway en el compose, las 8 métricas más las 2 de apoyo, logs JSON y la métrica de sentimiento negativo de 24 h al final del flujo. El criterio de aceptación se comprobó en Docker con corridas completas de `pipeline/todas-dev` (ver `infra/prometheus/README.md`).

**Pendiente:**

- **Sentimiento en el pipeline:** la etapa de sentimiento sigue `pendiente`, porque la imagen del orquestador no tiene el modelo (ver `src/transform/nlp/README.md`). Mientras no se decida cómo correrla, `sentimiento_negativo_24h_ratio` solo tiene datos después de `make nlp`.
