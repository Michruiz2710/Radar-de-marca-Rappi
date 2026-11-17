"""Datos pequeños para probar dbt en el CI (P3.4). No son datos reales.

Uso, con las variables POSTGRES_* y PG_SCHEMA_* del entorno:
    PYTHONPATH=. python dbt/datos_ci.py             # crea las tablas de clean y carga los datos
    PYTHONPATH=. python dbt/datos_ci.py --verificar # después de dbt build: revisa resultados conocidos

Las tablas se crean con el mismo código de P2.3 y P2.4, así que si alguien cambia una
columna de clean que dbt usa, el CI se pone en rojo. Los casos cubren lo que los modelos
tratan aparte: un bot, una mención en inglés, una reseña editada después de la respuesta
de Rappi y un sentimiento viejo (texto que cambió después del análisis).
"""

from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from src.common.db import crear_motor, esquema_analytics, esquema_clean
from src.transform.clean import tabla as menciones
from src.transform.nlp import tabla as sentimiento

BASE = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def _mencion(n: int, fuente: str, texto: str, dias: int, **extra) -> dict:
    fecha = BASE + timedelta(days=dias)
    fila = {
        "id_registro": f"{fuente}:ci-{n}",
        "fuente": fuente,
        "id_original": f"ci-{n}",
        "texto_limpio": texto,
        "hash_texto": _hash(texto),
        "idioma_consulta": "es",
        "idioma_detectado": "es",
        "pais": "co",
        "fecha_publicacion": fecha,
        "fecha_extraccion": fecha + timedelta(hours=1),
        "autor_hash": None if fuente == "news" else _hash(f"autor-{n}"),
        "calificacion": None,
        "likes": None,
        "version_app": None,
        "respuesta_marca": None,
        "fecha_respuesta": None,
        "editada_tras_respuesta": None,
        "fecha_edicion": None,
        "id_contenedor": "video-1" if fuente == "youtube" else None,
        "url": None,
        "medio": "Medio de prueba" if fuente == "news" else None,
        "es_bot": False,
        "motivo_bot": None,
        "run_id": "ci",
        "version_scraper": "ci",
        "version_contrato": "1.3.0",
        "version_limpieza": "ci",
        "procesado_en": fecha,
    }
    fila.update(extra)
    return fila


def filas_menciones() -> list[dict]:
    respuesta = BASE + timedelta(hours=5)
    return [
        _mencion(1, "google_play", "El pedido llegó tarde y frío", 0, calificacion=1,
                 version_app="8.42.20261030-90052", respuesta_marca="Lo sentimos",
                 fecha_respuesta=respuesta, editada_tras_respuesta=False),
        _mencion(2, "google_play", "Excelente servicio de Rappi", 0, calificacion=5, version_app="8.42.20261028-90050"),
        # Editada después de la respuesta: Google Play perdió la fecha original
        _mencion(3, "google_play", "Me cobraron dos veces, ya lo arreglaron", 1, calificacion=2,
                 version_app="8.41.20261021-90044", respuesta_marca="Revisamos tu caso",
                 fecha_respuesta=BASE, editada_tras_respuesta=True, fecha_edicion=BASE + timedelta(days=1)),
        _mencion(4, "youtube", "Rappi siempre se demora", 0),
        _mencion(5, "youtube", "Buen video", 1),
        _mencion(6, "youtube", "Gana dinero fácil aquí", 1, es_bot=True, motivo_bot="promocional"),
        _mencion(7, "youtube", "Great delivery app", 2, idioma_detectado="en"),
        # El texto cambió después del análisis: su sentimiento ya no está vigente
        _mencion(8, "youtube", "Texto editado después del análisis", 2),
        _mencion(9, "news", "Rappi anuncia nueva función de pagos", 0),
    ]


def filas_sentimiento(filas: list[dict]) -> list[dict]:
    etiquetas = {1: "negativo", 2: "positivo", 3: "negativo", 4: "negativo", 5: "positivo", 8: "neutro", 9: "neutro"}
    resultado = []
    for fila in filas:
        n = int(fila["id_original"].split("-")[1])
        if n not in etiquetas:
            continue
        hash_texto = _hash("texto anterior") if n == 8 else fila["hash_texto"]
        resultado.append({
            "id_registro": fila["id_registro"], "hash_texto": hash_texto, "sentimiento": etiquetas[n],
            "prob_sentimiento": 0.9, "prob_positivo": 0.05, "prob_neutro": 0.05, "prob_negativo": 0.9,
            "tema": "entregas" if n in (1, 4) else "otro", "temas_detectados": None,
            "version_modelo": "ci", "version_nlp": "ci", "procesado_en": BASE,
        })
    return resultado


def cargar() -> None:
    motor = crear_motor()
    esquema = esquema_clean()
    filas = filas_menciones()
    with motor.begin() as conexion:
        menciones.crear_tabla(conexion, esquema)
        sentimiento.crear_tabla(conexion, esquema)
        menciones.cargar(conexion, esquema, filas)
        sentimiento.guardar(sentimiento.con_esquema(conexion, esquema), filas_sentimiento(filas))
    print(f"Cargadas {len(filas)} menciones de prueba en {esquema}")


# Resultados que deben salir con estos datos
ESPERADOS = {
    "select count(*) from {a}.fct_menciones": 8,  # 9 menos el bot
    "select count(*) from {a}.fct_menciones where analizada": 6,  # sin la de inglés ni la del texto cambiado
    "select respondidas from {a}.agg_respuesta_marca_semanal": 2,
    "select respondidas_con_tiempo from {a}.agg_respuesta_marca_semanal": 1,
    "select respondidas_editadas from {a}.agg_respuesta_marca_semanal": 1,
    "select horas_mediana_respuesta from {a}.agg_respuesta_marca_semanal": 5,
    "select count(*) from {a}.agg_calificacion_version": 2,
    "select bots from {a}.resumen_fuentes where fuente = 'youtube'": 1,
}


def verificar() -> None:
    errores = []
    with crear_motor().connect() as conexion:
        for consulta, esperado in ESPERADOS.items():
            obtenido = conexion.execute(text(consulta.format(a=esquema_analytics()))).scalar_one()
            if float(obtenido) != esperado:
                errores.append(f"{consulta}: se esperaba {esperado} y salió {obtenido}")
    if errores:
        sys.exit("Resultados distintos a los esperados:\n" + "\n".join(errores))
    print(f"Los {len(ESPERADOS)} resultados esperados coinciden")


if __name__ == "__main__":
    verificar() if "--verificar" in sys.argv else cargar()
