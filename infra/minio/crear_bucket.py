"""Crea el bucket de la capa raw en MinIO y termina.

Lo ejecuta el servicio `minio-init` del docker-compose. Reintenta durante
un minuto por si MinIO todavía está arrancando, y no falla si el bucket ya existe.
"""

import os
import sys
import time

from minio import Minio

endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
bucket = os.getenv("MINIO_BUCKET", "radar-rappi")
cliente = Minio(
    endpoint,
    access_key=os.environ["MINIO_ROOT_USER"],
    secret_key=os.environ["MINIO_ROOT_PASSWORD"],
    secure=False,
)

INTENTOS = 30
for intento in range(1, INTENTOS + 1):
    try:
        if cliente.bucket_exists(bucket):
            print(f"Bucket '{bucket}' ya existe")
        else:
            cliente.make_bucket(bucket)
            print(f"Bucket '{bucket}' creado")
        sys.exit(0)
    except Exception as error:  # MinIO aún no responde
        print(f"Intento {intento}/{INTENTOS}: {error}")
        time.sleep(2)

print("No se pudo crear el bucket", file=sys.stderr)
sys.exit(1)
