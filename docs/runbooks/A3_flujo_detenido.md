# A3 · Ningún flujo exitoso en más del doble de su intervalo

**Prioridad:** P0 · **Condición:** `time() - ultima_corrida_exitosa_timestamp` supera el doble del intervalo del flujo:

| Flujo | Corre cada | Alerta si no hay corrida exitosa en |
| --- | --- | --- |
| `pipeline:news` | 2 h | 4 h |
| `pipeline:google_play` | 3 h | 6 h |
| `pipeline:youtube` | 6 h | 12 h |

El flujo manual `pipeline` (despliegue `todas-<entorno>`) no se vigila: no tiene horario.

## Qué significa

Un flujo dejó de terminar bien por mucho más tiempo del esperado. Si el flujo falla, también habrá saltado [A1](A1_flujo_falla.md). Si no hay ni fallas, lo más probable es que **nada esté corriendo**: el orquestador, Prefect o Docker están caídos.

## Qué hacer

1. **Mira qué servicios están arriba:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env ps
   ```

   Deben estar `Up` `orquestador`, `prefect` (`healthy`), `postgres` (`healthy`), `minio`, `pushgateway` y `prometheus`. Si Docker Desktop está cerrado o el equipo estuvo dormido, empieza por abrirlo.

2. **Levanta lo que falte:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env up -d
   ```

3. **Si `orquestador` se reinicia en bucle,** lee su log:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env logs --tail 100 orquestador
   ```

   Las causas habituales son que Prefect aún no responde (espera 20 a 30 s y reinicia el orquestador con `restart orquestador`) o una variable obligatoria faltante en `.env`.

4. **Comprueba los despliegues.** En http://localhost:4200 → **Deployments** deben aparecer `news-<entorno>`, `google_play-<entorno>`, `youtube-<entorno>` y `todas-<entorno>`, con su horario activo y una próxima corrida programada. Si no están, el orquestador no se registró: reinícialo.

5. **Corre el flujo a mano** para no esperar al horario:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador prefect deployment run 'pipeline/news-dev'
   ```

## Cómo saber que quedó resuelta

El panel **Última corrida exitosa** del dashboard muestra de nuevo tiempos cortos para cada flujo. La alerta se resuelve sola en el minuto siguiente a una corrida exitosa.

**Nota:** `ultima_corrida_exitosa_timestamp` se conserva en el Pushgateway aunque el orquestador se caiga, así que esta alerta seguirá activa hasta que de verdad termine una corrida bien.
