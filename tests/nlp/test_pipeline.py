"""Pruebas del pipeline con SQLite en memoria y un analizador falso (sin torch ni Postgres)."""

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, insert, select
from sqlalchemy.pool import StaticPool

from src.transform.nlp import tabla
from src.transform.nlp.pipeline import correr
from src.transform.nlp.sentimiento import ResultadoSentimiento


class Falso:
    def __init__(self, version="falso@1"):
        self.version = version
        self.textos_recibidos = []

    def analizar(self, textos):
        self.textos_recibidos.extend(textos)
        return [ResultadoSentimiento("negativo", 0.8, 0.1, 0.1, 0.8) for _ in textos]


@pytest.fixture
def motor():
    motor = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with motor.begin() as c:
        tabla._lectura.create_all(c)
        c.execute(
            insert(tabla.menciones),
            [
                {"id_registro": "google_play:1", "texto_limpio": "El pedido llegó tarde", "hash_texto": "h1",
                 "calificacion": 1, "es_bot": False},
                {"id_registro": "google_play:2", "texto_limpio": "Me cobraron doble", "hash_texto": "h2",
                 "calificacion": 2, "es_bot": True},
                {"id_registro": "google_play:3", "texto_limpio": "   ", "hash_texto": "h3",
                 "calificacion": 3, "es_bot": False},
            ],
        )
    return motor


def _resultados(motor):
    with motor.connect() as c:
        return {f.id_registro: f for f in c.execute(select(tabla.menciones_nlp))}


def test_cada_registro_con_texto_recibe_sentimiento_y_tema(motor):
    resumen = correr(motor=motor, analizador=Falso())
    filas = _resultados(motor)
    assert set(filas) == {"google_play:1", "google_play:2"}  # el texto vacío no se analiza
    assert filas["google_play:1"].tema == "entregas"
    assert filas["google_play:2"].tema == "cobros_y_pagos"  # los bots también se analizan
    assert filas["google_play:1"].version_modelo == "falso@1"
    assert resumen["procesados"] == 2 and resumen["pendientes"] == 0 and resumen["total"] == 2


def test_volver_a_correr_no_repite_trabajo(motor):
    correr(motor=motor, analizador=Falso())
    segundo = Falso()
    resumen = correr(motor=motor, analizador=segundo)
    assert resumen["procesados"] == 0 and segundo.textos_recibidos == []


def test_cambio_de_modelo_reanaliza_todo(motor):
    correr(motor=motor, analizador=Falso("falso@1"))
    resumen = correr(motor=motor, analizador=Falso("falso@2"))
    assert resumen["procesados"] == 2
    assert {f.version_modelo for f in _resultados(motor).values()} == {"falso@2"}


def test_texto_editado_se_reanaliza_solo_ese_registro(motor):
    correr(motor=motor, analizador=Falso())
    with motor.begin() as c:
        c.execute(
            tabla.menciones.update()
            .where(tabla.menciones.c.id_registro == "google_play:1")
            .values(texto_limpio="Excelente servicio", hash_texto="h1b")
        )
    falso = Falso()
    resumen = correr(motor=motor, analizador=falso)
    assert resumen["procesados"] == 1 and falso.textos_recibidos == ["Excelente servicio"]
    assert _resultados(motor)["google_play:1"].hash_texto == "h1b"


def test_lotes_de_lectura_pequenos_procesan_todo(motor):
    resumen = correr(motor=motor, analizador=Falso(), tamano_lectura=1)
    assert resumen["procesados"] == 2
