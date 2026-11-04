"""Pruebas del módulo común (P1.2): privacidad, contrato de datos y almacenamiento."""

import json
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.common.privacy import SalNoConfiguradaError, hash_autor
from src.common.schema import Fuente, RegistroMencion
from src.common.storage import construir_ruta, guardar_registros, nuevo_run_id

SAL = "sal-solo-para-pruebas"
AHORA = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)


def resena(**cambios) -> RegistroMencion:
    """Reseña válida de Google Play; cada prueba cambia lo que necesita."""
    datos = dict(
        fuente="google_play",
        id_original="gp-123",
        texto="El pedido llegó tarde",
        fecha_publicacion=AHORA - timedelta(hours=2),
        fecha_extraccion=AHORA,
        autor_hash=hash_autor("Ana", sal=SAL),
        calificacion=2,
        run_id="run-test",
        version_scraper="0.1.0",
    )
    datos.update(cambios)
    return RegistroMencion(**datos)


# ---------- privacy.py ----------

def test_hash_tiene_64_caracteres_hexadecimales():
    h = hash_autor("Ana María", sal=SAL)
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_mismo_autor_mismo_hash_aunque_cambien_espacios_y_mayusculas():
    assert hash_autor("Ana María", sal=SAL) == hash_autor("  ANA   maría ", sal=SAL)


def test_autores_distintos_dan_hashes_distintos():
    assert hash_autor("Ana", sal=SAL) != hash_autor("Juan", sal=SAL)


def test_la_sal_cambia_el_hash():
    assert hash_autor("Ana", sal=SAL) != hash_autor("Ana", sal="otra-sal")


def test_el_hash_no_contiene_el_nombre():
    assert "ana" not in hash_autor("Ana", sal=SAL)


def test_sin_autor_devuelve_none():
    assert hash_autor(None, sal=SAL) is None
    assert hash_autor("   ", sal=SAL) is None


def test_sin_sal_configurada_falla(monkeypatch):
    monkeypatch.delenv("HASH_SALT", raising=False)
    with pytest.raises(SalNoConfiguradaError):
        hash_autor("Ana")


def test_sal_de_ejemplo_es_rechazada(monkeypatch):
    monkeypatch.setenv("HASH_SALT", "cambiar_por_cadena_aleatoria")
    with pytest.raises(SalNoConfiguradaError):
        hash_autor("Ana")


def test_lee_la_sal_del_entorno(monkeypatch):
    monkeypatch.setenv("HASH_SALT", SAL)
    assert hash_autor("Ana") == hash_autor("Ana", sal=SAL)


# ---------- schema.py ----------

def test_resena_valida_y_id_registro():
    r = resena()
    assert r.id_registro == "google_play:gp-123"
    assert r.idioma == "es" and r.pais == "co"


def test_fecha_sin_zona_horaria_se_asume_utc():
    r = resena(fecha_publicacion=datetime(2026, 11, 1, 10, 0))
    assert r.fecha_publicacion.tzinfo == timezone.utc


def test_fecha_de_colombia_se_convierte_a_utc():
    bogota = timezone(timedelta(hours=-5))
    r = resena(fecha_publicacion=datetime(2026, 11, 1, 10, 0, tzinfo=bogota))
    assert r.fecha_publicacion.hour == 15


@pytest.mark.parametrize("calificacion", [0, 6])
def test_calificacion_fuera_de_rango(calificacion):
    with pytest.raises(ValidationError):
        resena(calificacion=calificacion)


def test_texto_vacio_falla():
    with pytest.raises(ValidationError):
        resena(texto="   ")


def test_fecha_futura_falla():
    with pytest.raises(ValidationError):
        resena(fecha_publicacion=datetime.now(timezone.utc) + timedelta(days=1))


def test_fuente_desconocida_falla():
    with pytest.raises(ValidationError):
        resena(fuente="news")


def test_campo_fuera_del_contrato_falla():
    # Protege contra guardar datos personales por accidente.
    with pytest.raises(ValidationError):
        resena(userName="Ana")


def test_autor_hash_mal_formado_falla():
    with pytest.raises(ValidationError):
        resena(autor_hash="Ana")


def test_calificacion_solo_en_google_play():
    with pytest.raises(ValidationError):
        resena(fuente="youtube", calificacion=5)


def test_subreddit_solo_en_reddit():
    with pytest.raises(ValidationError):
        resena(subreddit="Colombia")


def test_respuesta_antes_de_la_resena_falla():
    with pytest.raises(ValidationError):
        resena(fecha_respuesta=AHORA - timedelta(days=1))


def test_comentario_youtube_valido():
    r = RegistroMencion(
        fuente=Fuente.YOUTUBE, id_original="yt-9", texto="Rappi nunca responde",
        fecha_publicacion=AHORA, fecha_extraccion=AHORA, autor_hash=hash_autor("x", sal=SAL),
        likes=3, id_contenedor="video-1", url="https://youtube.com/watch?v=video-1",
        run_id="r", version_scraper="0.1.0",
    )
    assert r.id_registro == "youtube:yt-9"


def test_comentario_reddit_valido():
    r = RegistroMencion(
        fuente=Fuente.REDDIT, id_original="t1_abc", texto="Rappi me cobró dos veces",
        fecha_publicacion=AHORA, fecha_extraccion=AHORA, autor_hash=hash_autor("u1", sal=SAL),
        likes=12, id_contenedor="t3_post1", subreddit="r/Colombia",
        url="https://www.reddit.com/r/Colombia/comments/post1/", run_id="r", version_scraper="0.1.0",
    )
    assert r.id_registro == "reddit:t1_abc"
    assert r.subreddit == "colombia"


def test_calificacion_no_aplica_a_reddit():
    with pytest.raises(ValidationError):
        resena(fuente="reddit", calificacion=4)


# ---------- storage.py ----------

def test_ruta_de_particiones():
    ruta = construir_ruta("youtube", date(2026, 11, 4), "abc")
    assert ruta == "raw/fuente=youtube/fecha=2026-11-04/run_abc.jsonl"


def test_ruta_con_fuente_invalida_falla():
    with pytest.raises(ValueError):
        construir_ruta("twitter", date(2026, 11, 4), "abc")


def test_run_id_es_unico():
    assert nuevo_run_id() != nuevo_run_id()


def test_guardar_en_local_escribe_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    registros = [resena(id_original="a"), resena(id_original="b")]
    ruta = guardar_registros(registros, run_id="r1", backend="local")

    assert Path(ruta).as_posix().endswith("raw/fuente=google_play/fecha=2026-11-02/run_r1.jsonl")
    lineas = open(ruta, encoding="utf-8").read().splitlines()
    assert len(lineas) == 2
    primero = json.loads(lineas[0])
    assert primero["id_registro"] == "google_play:a"
    assert primero["fecha_publicacion"].endswith("Z")


def test_lista_vacia_no_escribe(tmp_path):
    assert guardar_registros([], run_id="r1", backend="local") is None


def test_mezclar_fuentes_falla():
    yt = resena(fuente="youtube", calificacion=None, id_original="y")
    with pytest.raises(ValueError):
        guardar_registros([resena(), yt], run_id="r1", backend="local")


def test_duplicados_en_la_corrida_fallan():
    with pytest.raises(ValueError):
        guardar_registros([resena(), resena()], run_id="r1", backend="local")


class MinioFalso:
    """Imita al cliente de MinIO para probar sin servidor."""

    def __init__(self):
        self.buckets, self.objetos = set(), {}

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def put_object(self, bucket, ruta, datos, length, content_type):
        self.objetos[(bucket, ruta)] = datos.read()


def test_guardar_en_minio(monkeypatch):
    monkeypatch.setenv("MINIO_BUCKET", "radar-rappi")
    cliente = MinioFalso()
    ruta = guardar_registros([resena()], run_id="r1", backend="minio", cliente=cliente)

    assert ruta == "s3://radar-rappi/raw/fuente=google_play/fecha=2026-11-02/run_r1.jsonl"
    assert "radar-rappi" in cliente.buckets
    (contenido,) = cliente.objetos.values()
    assert json.loads(contenido)["calificacion"] == 2


def test_backend_desconocido_falla():
    with pytest.raises(ValueError):
        guardar_registros([resena()], run_id="r1", backend="s4")
