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

Las publica el orquestador al final de cada corrida del flujo `pipeline`, en el grupo `job="radar_pipeline"` del Pushgateway.

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

Dos de apoyo para P3.2: `ultima_corrida_fallida_timestamp{flujo}` y `fallas_consecutivas{flujo}` (alerta A1: `fallas_consecutivas >= 2`).

`flujo` vale `pipeline:news`, `pipeline:google_play`, `pipeline:youtube` o `pipeline` (las tres fuentes).

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

## Logs

Cada línea es un objeto JSON con `timestamp`, `nivel`, `fuente`, `run_id`, `logger` y `mensaje`, más los campos que se pasen con `extra`. Dentro del orquestador, `run_id` es el id de la corrida en Prefect y `fuente` la de la tarea que está corriendo, así que los logs de los scrapers, la limpieza y las validaciones quedan unidos a su corrida.

Lo usan el orquestador, los tres scrapers, la limpieza y el NLP cuando se corren solos. Las líneas internas de Prefect (por ejemplo `Finished in state Completed`) conservan el formato de Prefect.

## Pruebas

```bash
python -m pytest -q tests/observability tests/flows
```

## Estado

Hecho: Prometheus y Pushgateway en el compose, las 8 métricas, logs JSON y la métrica de sentimiento negativo de 24 h al final del flujo. Probado con una corrida real de Prefect contra un Pushgateway simulado.

**Pendiente:**

- **Criterio de aceptación:** comprobar en Docker que las métricas aparecen en Prometheus después de una corrida completa.
- **Sentimiento en el pipeline:** la etapa de sentimiento sigue `pendiente`, porque la imagen del orquestador no tiene el modelo (ver `src/transform/nlp/README.md`). Mientras no se decida cómo correrla, `sentimiento_negativo_24h_ratio` solo tiene datos después de `make nlp`.
- **Google Play:** la librería no siempre informa el código HTTP; esos errores quedan con `codigo="error"`.
