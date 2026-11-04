"""Almacenamiento de la capa raw.

Los scrapers llaman a una sola función, `guardar_registros`, y no necesitan
saber dónde terminan los datos. La ruta siempre es:

    raw/fuente=<fuente>/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl

Hay dos destinos posibles, según la variable de entorno RAW_BACKEND:

- "minio" (por defecto): el bucket MINIO_BUCKET en MinIO.
- "local": la carpeta LOCAL_RAW_DIR (por defecto data/). Sirve para avanzar
  mientras el entorno Docker (P1.1) no está listo, y para pruebas.

Ejemplo:

    from src.common.storage import guardar_registros, nuevo_run_id

    run_id = nuevo_run_id()
    ruta = guardar_registros(registros, run_id=run_id)
"""

import io
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from src.common.schema import Fuente, RegistroMencion

PREFIJO_RAW = "raw"


def nuevo_run_id() -> str:
    """ID de corrida legible y único: 20261104T153000Z-1a2b3c4d."""
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{marca}-{uuid.uuid4().hex[:8]}"


def construir_ruta(fuente: Fuente | str, fecha: date, run_id: str) -> str:
    """Ruta del archivo dentro del bucket o de la carpeta local."""
    fuente = Fuente(fuente)  # falla si la fuente no es válida
    if not run_id or "/" in run_id:
        raise ValueError("run_id no puede estar vacío ni contener '/'")
    return f"{PREFIJO_RAW}/fuente={fuente.value}/fecha={fecha.isoformat()}/run_{run_id}.jsonl"


def a_jsonl(registros: list[RegistroMencion]) -> bytes:
    """Convierte la lista de registros en JSON Lines (un JSON por línea)."""
    return "".join(r.a_json() + "\n" for r in registros).encode("utf-8")


def _cliente_minio():
    """Crea el cliente de MinIO con las variables del .env."""
    from minio import Minio  # se importa aquí para no exigirlo en modo local

    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def guardar_registros(
    registros: list[RegistroMencion],
    run_id: str,
    backend: str | None = None,
    cliente=None,
) -> str | None:
    """Guarda una corrida de UNA fuente en la capa raw y devuelve la ruta.

    - Todos los registros deben ser de la misma fuente.
    - Si la lista está vacía no escribe nada y devuelve None.
    - La fecha de la partición es la fecha de extracción (UTC).
    """
    if not registros:
        return None

    fuentes = {r.fuente for r in registros}
    if len(fuentes) != 1:
        raise ValueError(f"una corrida debe tener una sola fuente, llegaron: {fuentes}")

    ids = [r.id_registro for r in registros]
    if len(ids) != len(set(ids)):
        raise ValueError("hay id_registro duplicados dentro de la misma corrida")

    ruta = construir_ruta(fuentes.pop(), registros[0].fecha_extraccion.date(), run_id)
    contenido = a_jsonl(registros)
    backend = (backend or os.getenv("RAW_BACKEND", "minio")).lower()

    if backend == "local":
        destino = Path(os.getenv("LOCAL_RAW_DIR", "data")) / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return str(destino)

    if backend == "minio":
        cliente = cliente or _cliente_minio()
        bucket = os.getenv("MINIO_BUCKET", "radar-rappi")
        if not cliente.bucket_exists(bucket):
            cliente.make_bucket(bucket)
        cliente.put_object(
            bucket,
            ruta,
            io.BytesIO(contenido),
            length=len(contenido),
            content_type="application/x-ndjson",
        )
        return f"s3://{bucket}/{ruta}"

    raise ValueError(f"RAW_BACKEND desconocido: '{backend}' (usa 'minio' o 'local')")
