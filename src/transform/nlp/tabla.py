"""Tabla `menciones_nlp` de la capa clean: sentimiento y tema por registro (P2.4).

Igual que `menciones` (P2.3), la tabla se define sin esquema y el esquema real se asigna al
conectarse (`schema_translate_map`), porque cambia por entorno: clean, clean_staging, clean_prod.
La tabla `menciones` aquí es solo de lectura y con las columnas que necesita este paquete;
la define y la llena P2.3.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    delete,
    func,
    insert,
    or_,
    select,
    text,
)

metadata = MetaData()

menciones_nlp = Table(
    "menciones_nlp",
    metadata,
    Column("id_registro", String, primary_key=True),
    Column("hash_texto", String),  # hash del texto que se analizó: si cambia, se vuelve a analizar
    Column("sentimiento", String, nullable=False),
    Column("prob_sentimiento", Float, nullable=False),
    Column("prob_positivo", Float, nullable=False),
    Column("prob_neutro", Float, nullable=False),
    Column("prob_negativo", Float, nullable=False),
    Column("tema", String, nullable=False),
    Column("temas_detectados", Text),  # todos los temas con coincidencia, separados por coma
    Column("version_modelo", String, nullable=False),
    Column("version_nlp", String, nullable=False),
    Column("procesado_en", DateTime(timezone=True), nullable=False),
)

# Solo lectura. No se crea desde aquí (otro MetaData): la tabla real la crea P2.3.
_lectura = MetaData()
menciones = Table(
    "menciones",
    _lectura,
    Column("id_registro", String, primary_key=True),
    Column("texto_limpio", Text),
    Column("hash_texto", String),
    Column("calificacion", Integer),
    Column("es_bot", Boolean),
)

_ESQUEMA_VALIDO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def con_esquema(conexion, esquema: str | None):
    """Hace que las tablas apunten al esquema del entorno. SQLite (pruebas) no tiene esquemas."""
    if conexion.dialect.name == "sqlite" or not esquema:
        return conexion
    if not _ESQUEMA_VALIDO.match(esquema):
        raise ValueError(f"nombre de esquema no válido: {esquema!r}")
    return conexion.execution_options(schema_translate_map={None: esquema})


def crear_tabla(conexion, esquema: str | None) -> None:
    """Crea el esquema (solo en Postgres) y la tabla `menciones_nlp` si no existen."""
    if conexion.dialect.name == "postgresql" and esquema:
        if not _ESQUEMA_VALIDO.match(esquema):
            raise ValueError(f"nombre de esquema no válido: {esquema!r}")
        conexion.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"'))
    con_esquema(conexion, esquema)
    metadata.create_all(conexion, tables=[menciones_nlp])


def _con_texto():
    return and_(
        menciones.c.texto_limpio.is_not(None),
        func.length(func.trim(menciones.c.texto_limpio)) > 0,
    )


def _union():
    return menciones.outerjoin(
        menciones_nlp, menciones_nlp.c.id_registro == menciones.c.id_registro
    )


def leer_pendientes(conexion, version_modelo: str, limite: int) -> list[dict[str, Any]]:
    """Registros limpios con texto que aún no tienen resultado vigente.

    Pendiente = no tiene fila en menciones_nlp, o se analizó con otra versión del modelo,
    o el texto cambió desde entonces (reseña editada, P2.3 conserva la versión más reciente).
    """
    consulta = (
        select(menciones.c.id_registro, menciones.c.texto_limpio, menciones.c.hash_texto)
        .select_from(_union())
        .where(
            _con_texto(),
            or_(
                menciones_nlp.c.id_registro.is_(None),
                menciones_nlp.c.version_modelo != version_modelo,
                menciones_nlp.c.hash_texto.is_distinct_from(menciones.c.hash_texto),
            ),
        )
        .order_by(menciones.c.id_registro)
        .limit(limite)
    )
    return [dict(f._mapping) for f in conexion.execute(consulta)]


def guardar(conexion, filas: list[dict[str, Any]]) -> int:
    """Reemplaza el resultado de cada registro (borra el anterior e inserta el nuevo)."""
    if not filas:
        return 0
    conexion.execute(
        delete(menciones_nlp).where(
            menciones_nlp.c.id_registro.in_([f["id_registro"] for f in filas])
        )
    )
    conexion.execute(insert(menciones_nlp), filas)
    return len(filas)


def cobertura(conexion, version_modelo: str) -> dict[str, int]:
    """Cuántos registros limpios con texto hay y cuántos tienen resultado vigente."""
    total = conexion.execute(
        select(func.count()).select_from(menciones).where(_con_texto())
    ).scalar_one()
    vigentes = conexion.execute(
        select(func.count())
        .select_from(_union())
        .where(
            _con_texto(),
            menciones_nlp.c.id_registro.is_not(None),
            menciones_nlp.c.version_modelo == version_modelo,
            menciones_nlp.c.hash_texto.is_not_distinct_from(menciones.c.hash_texto),
        )
    ).scalar_one()
    return {"total": total, "con_resultado": vigentes, "pendientes": total - vigentes}


def ahora_utc() -> datetime:
    return datetime.now(UTC)
