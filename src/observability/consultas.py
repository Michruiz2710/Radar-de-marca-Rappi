"""Métricas que se calculan con la capa clean: bots y sentimiento negativo (P3.1)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.engine import Engine

log = logging.getLogger("observability.consultas")


def calcular(motor: Engine | None = None, esquema: str | None = None, ahora: datetime | None = None) -> dict:
    """Devuelve {"registros_bot_ratio": {fuente: x}, "sentimiento_negativo_24h_ratio": {fuente: y}}.

    Ventana de 24 horas: los bots por fecha de procesamiento y el sentimiento por fecha
    de publicación (lo que se dijo de Rappi en el último día). Si Postgres no responde o
    las tablas aún no existen, devuelve un diccionario vacío y deja un aviso.
    """
    from src.common.db import crear_motor, esquema_clean
    from src.transform.clean.tabla import con_esquema, menciones
    from src.transform.nlp.tabla import tabla_sentimiento

    desde = (ahora or datetime.now(UTC)) - timedelta(hours=24)
    resultado: dict[str, dict[str, float]] = {}
    try:
        motor = motor or crear_motor()
        with motor.connect() as conexion:
            conexion = con_esquema(conexion, esquema or esquema_clean())
            es_bot = func.avg(case((menciones.c.es_bot, 1.0), else_=0.0))
            filas = conexion.execute(
                select(menciones.c.fuente, es_bot).where(menciones.c.procesado_en >= desde).group_by(menciones.c.fuente)
            ).all()
            resultado["registros_bot_ratio"] = {fuente: float(valor) for fuente, valor in filas}

            s = tabla_sentimiento
            negativo = func.avg(case((s.c.sentimiento == "negativo", 1.0), else_=0.0))
            filas = conexion.execute(
                select(menciones.c.fuente, negativo)
                .join(s, s.c.id_registro == menciones.c.id_registro)
                .where(menciones.c.fecha_publicacion >= desde, menciones.c.es_bot.is_(False))
                .group_by(menciones.c.fuente)
            ).all()
            resultado["sentimiento_negativo_24h_ratio"] = {fuente: float(valor) for fuente, valor in filas}
    except Exception as error:  # noqa: BLE001 - una métrica no debe tumbar el pipeline
        log.warning("No se pudieron calcular las métricas de la capa clean: %s", error)
    return resultado
