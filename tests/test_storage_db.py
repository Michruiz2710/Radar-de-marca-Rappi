"""Pruebas de la lectura de la capa raw (storage) y de la conexión compartida (db)."""

import io
import json

import pytest

from src.common import db
from src.common.storage import _separar_ruta_s3, leer_registros, listar_rutas


def test_leer_registros_local(tmp_path):
    ruta = tmp_path / "run.jsonl"
    ruta.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert leer_registros(str(ruta)) == [{"a": 1}, {"a": 2}]


class RespuestaFalsa(io.BytesIO):
    def release_conn(self):
        pass


class MinioFalso:
    def __init__(self, objetos):
        self.objetos = objetos

    def get_object(self, bucket, objeto):
        return RespuestaFalsa(self.objetos[(bucket, objeto)])

    def list_objects(self, bucket, prefix, recursive):
        class Objeto:
            def __init__(self, nombre):
                self.object_name = nombre

        return [Objeto(o) for (b, o) in self.objetos if b == bucket and o.startswith(prefix)]


def test_leer_registros_de_minio():
    cliente = MinioFalso({("radar-rappi", "raw/fuente=news/fecha=2026-11-07/run_x.jsonl"): json.dumps({"a": 1}).encode()})
    assert leer_registros("s3://radar-rappi/raw/fuente=news/fecha=2026-11-07/run_x.jsonl", cliente=cliente) == [{"a": 1}]


def test_listar_rutas_de_minio_por_fuente(monkeypatch):
    monkeypatch.setenv("MINIO_BUCKET", "radar-rappi")
    cliente = MinioFalso(
        {
            ("radar-rappi", "raw/fuente=news/fecha=2026-11-07/run_b.jsonl"): b"",
            ("radar-rappi", "raw/fuente=news/fecha=2026-11-06/run_a.jsonl"): b"",
            ("radar-rappi", "raw/fuente=youtube/fecha=2026-11-07/run_c.jsonl"): b"",
            ("radar-rappi", "state/news/marca.json"): b"",
        }
    )
    assert listar_rutas("news", backend="minio", cliente=cliente) == [
        "s3://radar-rappi/raw/fuente=news/fecha=2026-11-06/run_a.jsonl",
        "s3://radar-rappi/raw/fuente=news/fecha=2026-11-07/run_b.jsonl",
    ]
    assert len(listar_rutas(backend="minio", cliente=cliente)) == 3


def test_listar_rutas_local(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    carpeta = tmp_path / "raw/fuente=youtube/fecha=2026-11-07"
    carpeta.mkdir(parents=True)
    (carpeta / "run_1.jsonl").write_text("{}")
    assert listar_rutas("youtube", backend="local") == [str(carpeta / "run_1.jsonl")]


def test_ruta_s3_invalida():
    with pytest.raises(ValueError):
        _separar_ruta_s3("s3://solo-bucket")


def test_url_postgres_desde_variables(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for clave, valor in {"POSTGRES_USER": "radar", "POSTGRES_PASSWORD": "secreta", "POSTGRES_HOST": "postgres", "POSTGRES_DB": "radar"}.items():
        monkeypatch.setenv(clave, valor)
    url = db.url_postgres()
    assert (url.drivername, url.host, url.database, url.username) == ("postgresql+psycopg", "postgres", "radar", "radar")
    assert "secreta" not in str(url)  # la contraseña no se imprime en logs


def test_database_url_tiene_prioridad(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    assert db.url_postgres() == "sqlite://"


def test_esquemas_por_entorno(monkeypatch):
    monkeypatch.delenv("PG_SCHEMA_CLEAN", raising=False)
    assert db.esquema_clean() == "clean"
    monkeypatch.setenv("PG_SCHEMA_CLEAN", "clean_staging")
    assert db.esquema_clean() == "clean_staging"
