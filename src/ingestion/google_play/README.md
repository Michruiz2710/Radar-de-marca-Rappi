# Scraper de Google Play

Extracción incremental de reseñas de la app de Rappi con `google-play-scraper` (país `co`, idioma `es`).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.3 Scraper de Google Play | Katalina | Jonathan | Michelle | Semana 1 |

## Funcionamiento

1. Lee la marca de agua de la corrida anterior (`data/estado/google_play_marca_agua.json`).
2. Pide reseñas de la más nueva a la más antigua (`Sort.NEWEST`), en páginas de 100, con pausa de 2 s entre páginas.
3. Se detiene al encontrar una reseña ya vista o al llegar a `GP_MAX_REVIEWS_PER_RUN`.
4. Convierte cada reseña en `RegistroMencion` (autor con `hash_autor`, nunca el nombre) y descarta las que no cumplen el contrato, dejando un aviso en el log.
5. Guarda la corrida con `guardar_registros()` y, solo si se guardó bien, actualiza la marca de agua.

Si Google responde con error (por ejemplo 429), la librería devuelve una lista vacía en vez de lanzar una excepción; por eso una página vacía se reintenta hasta 3 veces con espera creciente (2, 4 y 8 s) antes de registrar el error.

## Archivos

| Archivo | Qué hace |
| --- | --- |
| `scraper.py` | Flujo completo de una corrida (`correr()`). |
| `marca_agua.py` | Lee y guarda la marca de agua (ID y fecha de la reseña más nueva). |
| `Dockerfile` | Imagen del scraper. |
| `tests/test_google_play.py` | Pruebas con respuestas simuladas: marca de agua, tope, duplicados y privacidad. |

## Ejecución

En local, con el venv activo y el `.env` configurado:

```bash
python -m src.ingestion.google_play.scraper
```

Con Docker, desde la raíz del repo:

```bash
docker build -f src/ingestion/google_play/Dockerfile -t radar-google-play .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" radar-google-play
```

El volumen `-v .../data:/app/data` es necesario: ahí viven la marca de agua y los archivos en modo local. Sin él, cada corrida empezaría desde cero. En Git Bash para Windows usa `$(pwd -W)` en lugar de `$(pwd)`.

## Variables de entorno

| Variable | Para qué | Valor por defecto |
| --- | --- | --- |
| `GP_APP_ID` | ID de la app en Play Store | `com.grability.rappi` |
| `GP_COUNTRY` | País | `co` |
| `GP_LANG` | Idioma | `es` |
| `GP_MAX_REVIEWS_PER_RUN` | Tope de reseñas por corrida | `500` |
| `HASH_SALT`, `RAW_BACKEND`, `LOCAL_RAW_DIR`, `MINIO_*` | Las del módulo común | ver `src/common/README.md` |

## Pruebas

```bash
python -m pytest -q tests/test_google_play.py
```

Ninguna prueba se conecta a Google Play.

## Estado

Terminado. Verificado el 5 de noviembre de 2026 con datos reales: la primera corrida trajo 500 reseñas y guardó 453; la segunda, unas horas después, trajo solo 6 nuevas; una tercera, ya dentro de Docker, trajo 0. No hubo duplicados entre corridas.

