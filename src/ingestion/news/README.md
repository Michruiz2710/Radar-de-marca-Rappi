# Scraper de noticias

Lectura del RSS de Google News sobre Rappi en español de Colombia.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.5 Scraper de noticias y etiquetado | Sara | Gabriel | Jonathan | Semana 1 |

## Qué hace

Guarda cada noticia nueva con el esquema de `src/common`:

- **Datos:** `raw/fuente=news/fecha=<AAAA-MM-DD>/run_<id>.jsonl`.
- **Estado:** `state/fuente=news/enlaces_vistos.json`, con los identificadores ya guardados. No es un dato del negocio y está fuera de `raw/`.

La deduplicación usa el `id` del feed, que se guarda en `id_original`, y el enlace queda en `url`. Si una entrada no trae `id`, se usa el enlace. El estado no olvida identificadores, porque el RSS también devuelve noticias de hace meses. Si no hay noticias nuevas, no crea ningún archivo. Si la descarga falla, reintenta con espera creciente.

## Cómo se corre

Desde la raíz del repositorio, con `pip install -r requirements.txt`:

```bash
# Solo probar el RSS, sin guardar nada
python -m src.ingestion.news.scraper --dry-run

# Guardar en data/ mientras MinIO no esté disponible
RAW_BACKEND=local python -m src.ingestion.news.scraper

# Docker
docker compose -f infra/docker-compose.yml --env-file .env run --rm scraper-news
docker compose -f infra/docker-compose.yml --env-file .env run --rm scraper-news --dry-run
```

Si el scraper se lanza justo después de levantar el entorno, espera unos segundos: MinIO no tiene `healthcheck`, así que la primera conexión puede fallar.

El modo local es para correrlo desde tu computador. Dentro de Docker también funciona, pero el servicio no tiene volumen y los datos se pierden al terminar.

En PowerShell, el modo local se activa con `$env:RAW_BACKEND="local"` antes del comando.

## Variables de entorno

`NEWS_QUERY`, `NEWS_HL` y `NEWS_GL` definen la búsqueda. La conexión usa las mismas variables de `src/common`: `RAW_BACKEND`, `LOCAL_RAW_DIR` y `MINIO_*`. El servicio de Docker recibe solo las que necesita, definidas en `infra/docker-compose.yml`. `RUN_ID` es opcional y lo pasará Prefect en P2.1.

## Pruebas

```bash
python -m pytest -q tests/news
```

## Estado

Probado con el RSS real y con el entorno de P1.1 usando `docker compose run --rm scraper-news`.

**Limitaciones:** el RSS no tiene paginación. Aun así, en las pruebas trajo unas 75 noticias de al menos dos semanas, así que con corridas cada 2 horas (P2.1) el riesgo de perder una es bajo. Si Google cambiara el `id` de sus entradas, una noticia ya vista se guardaría otra vez.
