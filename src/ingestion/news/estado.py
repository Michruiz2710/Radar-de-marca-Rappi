"""Guarda qué enlaces ya se vieron, en el mismo destino que la capa raw.

Usa las variables de src/common/storage.py: RAW_BACKEND, LOCAL_RAW_DIR y MINIO_*.
"""

from __future__ import annotations

import io
import os
from pathlib import Path


class EstadoLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)

    def leer(self, ruta: str) -> bytes | None:
        archivo = self.raiz / ruta
        return archivo.read_bytes() if archivo.exists() else None

    def escribir(self, ruta: str, contenido: bytes) -> None:
        archivo = self.raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)


class EstadoMinio:
    def __init__(self, cliente, bucket: str):
        self.cliente = cliente
        self.bucket = bucket

    def leer(self, ruta: str) -> bytes | None:
        from minio.error import S3Error

        try:
            respuesta = self.cliente.get_object(self.bucket, ruta)
        except S3Error as error:
            # En la primera corrida todavía no existen ni el archivo ni el bucket.
            if error.code in {"NoSuchKey", "NoSuchBucket"}:
                return None
            raise
        try:
            return respuesta.read()
        finally:
            respuesta.close()
            respuesta.release_conn()

    def escribir(self, ruta: str, contenido: bytes) -> None:
        self.cliente.put_object(self.bucket, ruta, io.BytesIO(contenido), length=len(contenido), content_type="application/json")


def crear_almacen_estado():
    backend = os.getenv("RAW_BACKEND", "minio").lower()
    if backend == "local":
        return EstadoLocal(os.getenv("LOCAL_RAW_DIR", "data"))
    if backend != "minio":
        raise ValueError(f"RAW_BACKEND desconocido: '{backend}' (usa 'minio' o 'local')")

    from minio import Minio

    cliente = Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    return EstadoMinio(cliente, os.getenv("MINIO_BUCKET", "radar-rappi"))
