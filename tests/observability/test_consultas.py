from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool

from src.observability import consultas
from src.transform.clean import tabla as clean
from src.transform.nlp import tabla as nlp

AHORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def motor():
    motor = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with motor.begin() as c:
        clean.crear_tabla(c, None)
        nlp.crear_tabla(c, None)
    return motor


def mencion(i, fuente, es_bot=False, horas=1):
    momento = AHORA - timedelta(hours=horas)
    return {
        "id_registro": f"{fuente}:{i}", "fuente": fuente, "id_original": str(i), "texto_limpio": "t",
        "hash_texto": "h", "idioma_consulta": "es", "idioma_detectado": "es", "pais": "co",
        "fecha_publicacion": momento, "fecha_extraccion": momento, "es_bot": es_bot,
        "run_id": "r", "version_limpieza": "1", "procesado_en": momento,
    }


def sentimiento(id_registro, valor):
    return {
        "id_registro": id_registro, "hash_texto": "h", "sentimiento": valor, "prob_sentimiento": 0.9,
        "prob_positivo": 0.0, "prob_neutro": 0.0, "prob_negativo": 0.0, "tema": "app",
        "version_modelo": "m", "version_nlp": "1", "procesado_en": AHORA,
    }


def test_calcula_bots_y_sentimiento_negativo(motor):
    filas = [mencion(1, "google_play"), mencion(2, "google_play"), mencion(3, "google_play", es_bot=True),
             mencion(4, "google_play", horas=30), mencion(5, "news")]
    sentimientos = [sentimiento("google_play:1", "negativo"), sentimiento("google_play:2", "positivo"),
                    sentimiento("google_play:3", "negativo"), sentimiento("google_play:4", "negativo"),
                    sentimiento("news:5", "neutro")]
    with motor.begin() as c:
        c = clean.con_esquema(c, None)
        c.execute(insert(clean.menciones), filas)
        c.execute(insert(nlp.tabla_sentimiento), sentimientos)
    resultado = consultas.calcular(motor, ahora=AHORA)
    # Bots: 1 de 3 en las últimas 24 h (la de hace 30 h no entra)
    assert resultado["registros_bot_ratio"]["google_play"] == pytest.approx(1 / 3)
    # Negativo: el bot y la de hace 30 h no cuentan, queda 1 de 2
    assert resultado["sentimiento_negativo_24h_ratio"] == {"google_play": 0.5, "news": 0.0}


def test_sin_base_de_datos_devuelve_vacio():
    assert consultas.calcular(create_engine("sqlite:////ruta/que/no/existe/x.db")) == {}
