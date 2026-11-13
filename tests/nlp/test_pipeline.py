"""Pruebas del pipeline con SQLite en memoria y un analizador falso (sin torch ni Postgres)."""

import pytest
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


def _fila(n, texto, hash_texto, idioma="es", es_bot=False):
    return {
        "id_registro": f"google_play:{n}",
        "texto_limpio": texto,
        "hash_texto": hash_texto,
        "idioma_detectado": idioma,
        "calificacion": 1,
        "es_bot": es_bot,
    }


@pytest.fixture
def motor():
    motor = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with motor.begin() as c:
        tabla._lectura.create_all(c)
        c.execute(
            insert(tabla.menciones),
            [
                _fila(1, "El pedido llegó tarde", "h1"),
                _fila(2, "Me cobraron doble", "h2"),
                _fila(3, "   ", "h3"),
                _fila(4, "O pedido chegou atrasado", "h4", idioma="pt"),
                _fila(5, "Gana dinero ya con este link", "h5", es_bot=True),
            ],
        )
    return motor


def _resultados(motor):
    with motor.connect() as c:
        return {f.id_registro: f for f in c.execute(select(tabla.tabla_sentimiento))}


def test_cada_registro_elegible_recibe_sentimiento_y_tema(motor):
    resumen = correr(motor=motor, analizador=Falso())
    filas = _resultados(motor)
    assert set(filas) == {"google_play:1", "google_play:2"}
    assert filas["google_play:1"].tema == "entregas"
    assert filas["google_play:2"].tema == "cobros_y_pagos"
    assert filas["google_play:1"].version_modelo == "falso@1"
    assert resumen["procesados"] == 2 and resumen["pendientes"] == 0 and resumen["total"] == 2


def test_no_analiza_bots_ni_otros_idiomas_ni_texto_vacio(motor):
    falso = Falso()
    correr(motor=motor, analizador=falso)
    assert "O pedido chegou atrasado" not in falso.textos_recibidos  # portugués
    assert "Gana dinero ya con este link" not in falso.textos_recibidos  # es_bot
    assert not any(t.strip() == "" for t in falso.textos_recibidos)  # vacío


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
