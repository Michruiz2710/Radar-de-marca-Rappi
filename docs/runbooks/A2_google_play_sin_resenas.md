# A2 · Google Play extrae 0 reseñas en 6 horas

**Prioridad:** P0 · **Condición:** `increase(registros_extraidos_total{fuente="google_play"}[6h]) == 0`.

## Qué significa

En las últimas 6 horas (dos corridas de Google Play como mínimo) no se guardó ninguna reseña nueva. Puede ser un bloqueo de Google (error 429), un cambio en la librería `google-play-scraper`, una marca de agua mal puesta o que el flujo no esté corriendo.

**Ojo:** casi nunca habrá errores HTTP que lo confirmen. La librería convierte un 429 en una página vacía en vez de lanzar un error, así que `errores_http_total{fuente="google_play"}` suele quedar en 0 (ver `src/observability/README.md`). Esta alerta es la señal confiable.

También salta en un entorno recién levantado, antes de la primera extracción de Google Play. Si acabas de hacer `make up`, espera a la primera corrida.

## Qué hacer

1. **¿El flujo está corriendo?** En el dashboard mira **Última corrida exitosa** y **Fallas consecutivas**. Si el flujo `pipeline:google_play` falla o no corre, atiende primero [A1](A1_flujo_falla.md) o [A3](A3_flujo_detenido.md).

2. **Pide reseñas directamente a Google Play desde el contenedor:**

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador python -c "from google_play_scraper import reviews, Sort; r, _ = reviews('com.grability.rappi', lang='es', country='co', sort=Sort.NEWEST, count=5); print(len(r), r[0]['at'] if r else None)"
   ```

   - **Imprime `0 None`:** Google está bloqueando o la librería dejó de funcionar. Espera unos minutos y repite; si sigue en 0, revisa los *issues* de `google-play-scraper` (versión fijada: 1.2.7) por un cambio en el sitio y actualiza la versión en `requirements.txt`.
   - **Imprime reseñas recientes:** Google responde bien; el problema es nuestro. Sigue con el paso 3.

3. **Revisa la marca de agua.** Es la reseña más nueva ya vista; la extracción se detiene al encontrarla:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador cat data/estado/google_play_marca_agua.json
   ```

   Si la fecha es posterior a las reseñas que devuelve el paso 2, la marca de agua está adelantada y no entra nada. Como último recurso, borrar ese archivo hace que la siguiente corrida empiece desde cero (trae hasta `GP_MAX_REVIEWS_PER_RUN` reseñas ya conocidas; la limpieza no duplica).

4. **Revisa `GP_APP_ID`, `GP_COUNTRY` y `GP_LANG` en `.env`.** Deben ser `com.grability.rappi`, `co` y `es`. Si cambias algo, recrea el servicio con `up -d orquestador`.

5. **Fuerza una corrida** para comprobarlo:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador prefect deployment run 'pipeline/google_play-dev'
   ```

## Cómo saber que quedó resuelta

El panel **Registros extraídos por fuente** vuelve a mostrar Google Play por encima de 0. La alerta se resuelve sola cuando `increase(...[6h])` deja de ser 0, normalmente en el minuto siguiente a la corrida que traiga reseñas.
