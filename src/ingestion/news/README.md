# Scraper de noticias

Lectura del RSS de Google News sobre Rappi en español de Colombia.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.5 Scraper de noticias y etiquetado | Sara | Gabriel | Jonathan | Semana 1 |

## Qué hace

Guarda cada noticia nueva con el esquema de `src/common`:

- **Datos:** `raw/fuente=news/fecha=<AAAA-MM-DD>/run_<id>.jsonl`.
- **Estado:** `state/fuente=news/enlaces_vistos.json`, con los enlaces ya guardados.

La deduplicación usa el enlace. El estado no olvida enlaces, porque el RSS también devuelve noticias de hace meses. Si no hay noticias nuevas, no crea ningún archivo. Si la descarga falla, reintenta con espera creciente.

## Cómo se corre

Desde la raíz del repositorio, con `pip install -r requirements.txt`:

```bash
# Solo probar el RSS, sin guardar nada
python -m src.ingestion.news.scraper --dry-run

# Guardar en data/ mientras MinIO no esté disponible
RAW_BACKEND=local python -m src.ingestion.news.scraper

# Docker
docker build -f src/ingestion/news/Dockerfile -t radar-news .
docker run --rm --env-file .env --network <red-de-compose> radar-news
```

En PowerShell, el modo local se activa con `$env:RAW_BACKEND="local"` antes del comando.

## Variables de entorno

`NEWS_QUERY`, `NEWS_HL` y `NEWS_GL` definen la búsqueda. La conexión usa las mismas variables de `src/common`: `RAW_BACKEND`, `LOCAL_RAW_DIR` y `MINIO_*`. `RUN_ID` es opcional y lo pasará Prefect en P2.1.

## Pruebas

```bash
python -m pytest -q tests/news
```

## Estado

Probado con el RSS real en modo local. Pendiente de probar con MinIO real y dentro de Docker. Falta agregar el servicio a `infra/docker-compose.yml` cuando exista (P1.1).

**Limitaciones:** el RSS no tiene paginación, así que una noticia que entre y salga entre dos corridas se pierde; P2.1 correrá cada 2 horas para reducir ese riesgo. Los enlaces son redirecciones de Google News: si Google cambiara su formato, una noticia ya vista se guardaría otra vez.
