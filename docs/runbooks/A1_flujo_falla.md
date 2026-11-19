# A1 · Un flujo falla 2 corridas seguidas

**Prioridad:** P0 · **Condición:** `fallas_consecutivas >= 2` en algún flujo (la etiqueta `flujo` dice cuál: `pipeline:news`, `pipeline:google_play`, `pipeline:youtube` o `pipeline`).

## Qué significa

Dos corridas seguidas del mismo flujo terminaron en error. Cada tarea ya reintentó 3 veces antes de que la corrida se diera por fallida, así que no es un fallo pasajero. Mientras tanto no entran datos nuevos de esa fuente (o no llegan a clean, validación o sentimiento).

## Qué hacer

1. **Abre la corrida fallida.** En Prefect (http://localhost:4200) entra a **Runs**, filtra por estado *Failed* y abre la más reciente del flujo. La tarea en rojo dice dónde falló:

   | Tarea que falló | Causa probable | Dónde seguir |
   | --- | --- | --- |
   | `extraer_<fuente>` | La fuente bloquea, no responde o se acabó la cuota; o MinIO está caído | [A2](A2_google_play_sin_resenas.md) (Google Play), [A7](A7_cuota_youtube.md) (YouTube) o el paso 2 |
   | `validacion_cruda` o `validacion_limpia` | Una regla crítica falló | [A4](A4_validacion_critica.md) |
   | `limpieza` | Postgres caído o esquema sin crear | Paso 2 |
   | `sentimiento` | Memoria agotada o modelo sin cargar | Paso 3 |

2. **Comprueba que los servicios estén arriba:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env ps
   ```

   `minio`, `postgres`, `prefect` y `orquestador` deben estar `Up` (los dos primeros y Prefect, `healthy`). Si alguno no, levántalo con `up -d` y sigue con el paso 4.

3. **Si falló `sentimiento`:** la etapa corre dentro del orquestador, que tiene un límite de 4 GB. Revisa si lo mató por memoria:

   ```bash
   docker inspect radar-rappi-orquestador-1 --format "{{.State.OOMKilled}}"
   ```

   Si dice `true`, baja `NLP_BATCH_SIZE` en `.env` (por ejemplo a 16) y recrea el servicio con `up -d orquestador`. El error `Quedaron N registros sin resultado` significa que el análisis no terminó: reintenta (el análisis es idempotente y solo procesa lo pendiente).

4. **Reintenta a mano:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador prefect deployment run 'pipeline/news-dev'
   ```

   Cambia `news-dev` por el despliegue del flujo afectado (`google_play-dev`, `youtube-dev`, `todas-dev`) y `dev` por el entorno (`staging`, `prod`).

## Cómo saber que quedó resuelta

Una corrida exitosa pone `fallas_consecutivas` en 0. En el dashboard «Pipeline técnico» el panel **Fallas consecutivas** vuelve a verde y, en un par de minutos, llega el correo `[RESOLVED]`.

## Logs

Los logs del orquestador son JSON con `run_id` y `fuente`. Para ver los de una corrida: copia su `run_id` desde Prefect y filtra con
`docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env logs orquestador | grep <run_id>`.
