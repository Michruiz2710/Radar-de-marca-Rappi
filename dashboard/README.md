# Dashboard de negocio

App de Streamlit: sentimiento, top de quejas, calificación por versión, respuesta de Rappi y cruce con noticias.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.3 Dashboard de negocio | Katalina | Jonathan | Michelle | Semana 3 |

## Estado

Listo para revisión. App de Streamlit que lee solo del esquema `analytics` (modelos dbt de P3.4, tabla `fct_menciones`).

- **Resumen:** menciones, % negativo, calificación promedio y tema más quejado.
- **Sentimiento y noticias:** % negativo diario por fuente, con las noticias marcadas sobre la curva.
- **Quejas:** top de temas negativos de los últimos 7 días del rango, con ejemplos anonimizados (se tapan correos y teléfonos).
- **App y respuesta:** calificación por versión (Google Play) y tiempo de respuesta de Rappi a reseñas de 1 o 2 estrellas.
- Filtros por rango de fechas (hora de Colombia) y fuente.

### Cómo se corre

Con Docker, desde la raíz: `docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env up -d --build dashboard` y abrir http://localhost:8502 (puerto en `DASHBOARD_PORT`).

En local, desde `dashboard/`: `PYTHONPATH=.. POSTGRES_HOST=localhost streamlit run app.py` (http://localhost:8501). El tema de colores está en `.streamlit/config.toml`.

### Pendiente

- Necesita que `dbt build` haya corrido (P3.4) para que existan las tablas de `analytics`.
