""" Suite clean y validar_limpia, con una base SQLite en memoria (no necesita Postgres) """

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from quality.checkpoints import ValidacionCriticaError, validar_limpia
from src.transform.clean.tabla import menciones, metadata

HASH = "3f5a" + "0" * 60
RUTAS = {"google_play": "data/raw/run.jsonl"} 


def _fila(**cambios) -> dict:
    fila = {
        "id_registro": "google_play:gp-1",
        "fuente": "google_play",
        "id_original": "gp-1",
        "texto_limpio": "El pedido llegó tarde",
        "hash_texto": HASH,
        "idioma_consulta": "es",
        "idioma_detectado": "es",
        "pais": "co",
        "fecha_publicacion": datetime(2026, 11, 2, 13, tzinfo=timezone.utc),
        "fecha_extraccion": datetime(2026, 11, 2, 15, tzinfo=timezone.utc),
        "autor_hash": HASH,
        "calificacion": 2,
        "es_bot": False,
        "run_id": "20261102T150000Z-prueba",
        "version_limpieza": "1.0.0",
        "procesado_en": datetime(2026, 11, 2, 16, tzinfo=timezone.utc),
    }
    fila.update(cambios)
    return fila


def _motor_con(filas: list[dict]):
    motor = create_engine("sqlite://")
    metadata.create_all(motor)
    with motor.begin() as conexion:
        conexion.execute(menciones.insert(), filas)
    return motor


def test_tabla_correcta_pasa():
    motor = _motor_con([_fila(), _fila(id_registro="google_play:gp-2", id_original="gp-2", calificacion=5)])
    resumen = validar_limpia(RUTAS, motor=motor)
    assert resumen["criticas"] == []


def test_sin_archivos_nuevos_no_valida():
    assert validar_limpia({"google_play": None}) is None


@pytest.mark.parametrize(
    "defecto",
    [
        {"calificacion": 9},
        {"texto_limpio": ""},
        {"autor_hash": "juan123"},
        {"fuente": "reddit"},
        {"fecha_publicacion": datetime(2030, 1, 1, tzinfo=timezone.utc)},
    ],
    ids=["calificacion", "texto_vacio", "autor_hash", "fuente", "fecha_futura"],
)
def test_tabla_con_defecto_detiene_el_flujo(defecto):
    motor = _motor_con([_fila(**defecto)])
    with pytest.raises(ValidacionCriticaError):
        validar_limpia(RUTAS, motor=motor)