# A8 · Prometheus no ve el Pushgateway

**Prioridad:** P0 · **Condición:** `up{job="pushgateway"} == 0` durante 1 minuto. Es una alerta extra: no está en la tabla de la ruta de trabajo (A1 a A7).

## Qué significa

Prometheus no puede leer el Pushgateway, que es donde el orquestador publica las métricas al final de cada corrida. Mientras esté caído **todas las demás alertas están ciegas**: sin métricas nuevas, A1 a A7 devuelven «sin datos» y no se disparan aunque el pipeline falle. Por eso esta alerta es P0.

El pipeline sigue corriendo y no se detiene. Si el Pushgateway no responde, el orquestador deja solo un aviso en el log (`No se pudieron publicar las métricas`) y acumula los contadores en `data/estado/metricas.json`, así que no se pierden: la primera publicación después de levantarlo manda los totales.

## Qué hacer

1. **Mira el estado del servicio:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env ps pushgateway
   ```

2. **Si está apagado o reiniciándose, lee por qué:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env logs --tail 50 pushgateway
   ```

   Las causas habituales son que Docker Desktop esté cerrado, que el puerto `PUSHGATEWAY_PORT` lo esté usando otro programa o que el archivo de persistencia (`pushgateway.db`, en el volumen `pushgateway_data`) esté dañado. En ese último caso, el log lo dice y hay que borrar el volumen (`docker volume rm radar-rappi_pushgateway_data`); lo único que se pierde es la última foto de las métricas, que se vuelve a publicar en la siguiente corrida.

3. **Levántalo:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env up -d pushgateway
   ```

4. **Comprueba que Prometheus lo ve.** En http://localhost:9090/targets el destino `pushgateway` debe estar **UP**. Si el servicio corre pero sigue en rojo, revisa que `infra/prometheus/prometheus.yml` apunte a `pushgateway:9091`.

5. **Revisa lo que no se vigiló.** Mientras estuvo caído nadie te avisó de nada más: mira en Prefect (http://localhost:4200) si hubo corridas fallidas y consulta el dashboard «Pipeline técnico». Fuerza una corrida si hace falta para que se publiquen los totales acumulados.

## Cómo saber que quedó resuelta

El destino `pushgateway` vuelve a estar **UP**, la alerta se resuelve en un par de minutos y llega el correo `[RESOLVED]`. El dashboard recupera los valores en cuanto Prometheus lo lee (cada 30 segundos).

**Nota:** si lo que se cae es Prometheus (no el Pushgateway), esta alerta no puede avisarlo: Grafana no puede consultar nada y las reglas P0 pasan a estado de error, que también envía correo. Si lo que se cae es Grafana, nadie avisa; por eso conviene mirar el dashboard antes de la demo.
