# Módulo común

Esquema del registro común (`schema.py`), escritura en la capa raw (`storage.py`) y hash de autores (`privacy.py`). Lo usan los 3 scrapers.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.2 Contrato de datos y módulo común | Michelle | Katalina | Sara | Semana 1 |

## Qué hay aquí

| Archivo | Qué hace |
| --- | --- |
| `schema.py` | Clase `RegistroMencion`: el contrato de datos en código. Rechaza registros que no lo cumplen. |
| `privacy.py` | `hash_autor(nombre)`: convierte el nombre del autor en un hash SHA-256 con sal. |
| `storage.py` | `guardar_registros(registros, run_id)`: escribe una corrida en MinIO o en una carpeta local. `nuevo_run_id()` genera el ID de corrida. |

El detalle de cada campo está en [`docs/contrato_datos.md`](../../docs/contrato_datos.md).

## Cómo usarlo en un scraper

```python
from src.common.privacy import hash_autor
from src.common.schema import Fuente, RegistroMencion
from src.common.storage import guardar_registros, nuevo_run_id

run_id = nuevo_run_id()
registros = [
    RegistroMencion(
        fuente=Fuente.GOOGLE_PLAY,
        id_original=r["reviewId"],
        texto=r["content"],
        fecha_publicacion=r["at"],
        autor_hash=hash_autor(r["userName"]),   # nunca guardar userName
        calificacion=r["score"],
        likes=r["thumbsUpCount"],
        version_app=r["reviewCreatedVersion"],
        respuesta_marca=r["replyContent"],
        fecha_respuesta=r["repliedAt"],
        run_id=run_id,
        version_scraper="0.1.0",
    )
    for r in resenas
]
ruta = guardar_registros(registros, run_id=run_id)
print(f"{len(registros)} reseñas guardadas en {ruta}")
```

Si un registro no cumple el contrato, `RegistroMencion(...)` lanza `pydantic.ValidationError` con el campo y el motivo. Cada scraper decide si descarta ese registro (y lo registra en el log) o detiene la corrida.

## Variables de entorno que usa

| Variable | Para qué | Valor por defecto |
| --- | --- | --- |
| `HASH_SALT` | Sal del hash de autores. Obligatoria; se rechaza el valor de ejemplo | — |
| `RAW_BACKEND` | `minio` o `local` | `minio` |
| `LOCAL_RAW_DIR` | Carpeta raíz en modo local | `data` |
| `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Conexión a MinIO | `localhost:9000` |
| `MINIO_BUCKET` | Bucket de la capa raw (se crea si no existe) | `radar-rappi` |
| `MINIO_SECURE` | `true` si MinIO usa HTTPS | `false` |

Mientras el entorno Docker (P1.1) no esté listo, los scrapers pueden trabajar con `RAW_BACKEND=local`: los archivos quedan en `data/raw/...`, que Git ignora.

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q tests/test_common.py
```

## Estado

Terminado en la Semana 1: contrato v1.1.0, hash con sal, escritura local y en MinIO, 33 pruebas.
Pendiente: probar la escritura contra el MinIO real cuando esté el `docker-compose` de P1.1.
