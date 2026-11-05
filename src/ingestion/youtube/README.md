# Scraper de YouTube

Búsqueda diaria de videos y descarga incremental de comentarios con YouTube Data API v3, controlando la cuota.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.4 Scraper de YouTube | Gabriel | Michelle | Katalina | Semana 1 |

## Qué hace

1. Busca videos con `YT_QUERY` (acepta varios términos separados por coma) en `YT_LANG` y `YT_REGION`. Hace como máximo `YT_MAX_SEARCHES_PER_DAY` búsquedas; cada una cuesta 100 unidades y trae hasta 50 videos.
   Solo se queda con los videos que nombran la marca (`YT_BRAND_TERMS`, por defecto `rappi`) en el título, la descripción o el nombre del canal. Cuenta "RappiTurbo", "rappitendero" o "#rappi", pero no palabras como "trappist". Los descartados no gastan cuota y se cuentan en el log.
2. Baja los comentarios de primer nivel de cada video, del más nuevo al más viejo (1 unidad por página de 100), hasta `YT_MAX_COMMENTS_PER_VIDEO`. Salta los videos con comentarios desactivados.
3. Convierte cada comentario en un `RegistroMencion` (contrato v1.0.0). El autor se guarda solo como `autor_hash`. Si un comentario no cumple el contrato (por ejemplo, texto vacío), se descarta y se cuenta en el log.
4. Guarda la corrida con `guardar_registros()`: `raw/fuente=youtube/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl`.
5. Es incremental: guarda la fecha del comentario más nuevo en `estado/youtube.json` y la siguiente corrida solo baja comentarios posteriores.
6. Se detiene sola al llegar a `YT_QUOTA_BUDGET` unidades y guarda lo que alcanzó.

| Campo del contrato | Viene de |
| --- | --- |
| `id_original` | ID del comentario |
| `texto` | `textOriginal` |
| `fecha_publicacion` | `publishedAt` |
| `autor_hash` | `hash_autor(authorDisplayName)` |
| `likes` | `likeCount` |
| `id_contenedor` | ID del video |
| `url` | enlace al comentario dentro del video |

## Cómo se corre

Desde la raíz del repositorio, con el `.env` completo (`YOUTUBE_API_KEY` y `HASH_SALT`):

```bash
pip install -r requirements.txt
python -m pytest -q tests/youtube

# Sin Docker: guarda en data/raw/...
RAW_BACKEND=local python -m src.ingestion.youtube.scraper

# Con el entorno de P1.1 arriba (make up), desde tu terminal:
MINIO_ENDPOINT=localhost:9000 python -m src.ingestion.youtube.scraper

# Ignorar la marca de agua y bajar todo otra vez:
python -m src.ingestion.youtube.scraper --full
```

Con Docker:

```bash
docker build -f src/ingestion/youtube/Dockerfile -t radar-youtube .
docker run --rm --env-file .env --network radar-rappi_default radar-youtube
```

## Relevancia

Los comentarios no se filtran uno por uno en la capa raw: en un video sobre Rappi, "el domiciliario llegó tarde" es relevante aunque no nombre la marca. El filtro está a nivel de video. La medición de cuántos comentarios nombran la marca queda para las validaciones (P2.2) y los modelos dbt (P3.4).

## Cuota

La API da 10.000 unidades al día por proyecto de Google Cloud, y la clave es compartida por el equipo. Con los valores por defecto (3 búsquedas y hasta 500 comentarios por video) una corrida gasta 300 unidades en búsquedas y como máximo unas 750 en comentarios.

## Estado

Terminado en la Semana 1 (v0.1.0). Pendiente: correrlo como flujo de Prefect (P2.1).
