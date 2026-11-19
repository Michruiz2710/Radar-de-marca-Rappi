# A4 · Falla una validación crítica

**Prioridad:** P0 · **Condición:** `sum(increase(validaciones_fallidas_total{severidad="critica"}[1h])) > 0`.

## Qué significa

Great Expectations encontró datos que rompen el contrato y **el flujo ya se detuvo**: ninguna etapa posterior corrió (limpieza, sentimiento, etc.). Cada tarea reintenta 3 veces, así que una sola falla suele contarse 4 veces.

La etiqueta `suite` de la métrica dice dónde ocurrió: `raw_news`, `raw_google_play`, `raw_youtube` (el archivo nuevo de esa fuente) o `clean_menciones` (la tabla de la capa clean).

## Qué hacer

1. **Lee qué regla falló.** El log del orquestador la trae con la ruta del archivo:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env logs orquestador | grep "Regla crítica"
   ```

2. **Abre los Data Docs** (el reporte de Great Expectations). Quedan dentro del contenedor, en `/app/data/data_docs`. Cópialos al computador y abre `index.html`:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env cp orquestador:/app/data/data_docs ./data/data_docs
   ```

   (La carpeta `data/` no se sube a Git.) Las reglas y su severidad están en `quality/README.md`.

3. **Actúa según la suite:**

   - **`raw_*`:** el archivo recién guardado está mal. Causas típicas: la fuente cambió su formato (columnas distintas), una fecha del futuro, texto vacío o calificación fuera de 1 a 5. Si la regla es de **dato personal** (por ejemplo la columna `userName`), trátalo como un incidente de privacidad: no compartas el archivo y corrige el scraper antes de seguir. El archivo malo queda en MinIO, pero la corrida no lo pasó a clean. Corrige el scraper o el contrato, y luego corre el flujo otra vez.
   - **`clean_menciones`:** la validación revisa la **tabla completa**, no solo lo nuevo. Mientras exista una fila que incumpla la regla, **cada corrida con datos nuevos volverá a fallar**. Encuentra y corrige la fila o la regla de limpieza (`src/transform/clean/`), y vuelve a correr. Si una corrida no trae archivos nuevos, la validación se omite: el error sigue ahí aunque el flujo parezca bien.

4. **Vuelve a correr** el flujo de la fuente afectada:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador prefect deployment run 'pipeline/news-dev'
   ```

## Cómo saber que quedó resuelta

La alerta mira la última hora: se resuelve sola a la hora de la última falla. **Eso no prueba que esté corregido.** Si el problema sigue, la próxima corrida vuelve a fallar y la alerta se dispara otra vez. La señal real es una corrida completa en Prefect, con `validacion_cruda` y `validacion_limpia` en verde.
