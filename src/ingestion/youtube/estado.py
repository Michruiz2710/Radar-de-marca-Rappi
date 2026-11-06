"""Marca de agua del scraper de YouTube (para la descarga incremental).

Se guarda en el mismo destino que la capa raw (RAW_BACKEND), pero fuera de
raw/ para no mezclarla con los datos: estado/youtube.json
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path

RUTA = "estado/youtube.json"


def _backend() -> str:
    return os.getenv("RAW_BACKEND", "minio").lower()


def _cliente_minio():
    from minio import Minio

    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def leer_marca() -> datetime | None:
    """Fecha del comentario más nuevo de la corrida anterior, o None."""
    if _backend() == "local":
        archivo = Path(os.getenv("LOCAL_RAW_DIR", "data")) / RUTA
        if not archivo.exists():
            return None
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    else:
        from minio.error import S3Error

        try:
            respuesta = _cliente_minio().get_object(os.getenv("MINIO_BUCKET", "radar-rappi"), RUTA)
        except S3Error:
            return None  # primera corrida
        try:
            datos = json.loads(respuesta.read())
        finally:
            respuesta.close()
            respuesta.release_conn()
    return datetime.fromisoformat(datos["marca_de_agua"])


def guardar_marca(marca: datetime, run_id: str, registros: int) -> None:
    contenido = json.dumps(
        {"marca_de_agua": marca.isoformat(), "ultimo_run_id": run_id, "registros": registros},
        ensure_ascii=False,
    ).encode("utf-8")
    if _backend() == "local":
        archivo = Path(os.getenv("LOCAL_RAW_DIR", "data")) / RUTA
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)
        return
    _cliente_minio().put_object(
        os.getenv("MINIO_BUCKET", "radar-rappi"), RUTA, io.BytesIO(contenido),
        length=len(contenido), content_type="application/json",
    )
