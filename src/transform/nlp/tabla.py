"""Tabla `sentimiento` de la capa clean: sentimiento y tema por registro (P2.4).

El nombre sale del contrato de la capa clean (docs/contrato_clean.md): `clean.sentimiento`.
Igual que `menciones` (P2.3), la tabla se define sin esquema y el esquema real se asigna al
conectarse (`schema_translate_map`), porque cambia por entorno: clean, clean_staging, clean_prod.
La tabla `menciones` aquí es solo de lectura y con las columnas que necesita este paquete;
la define y la llena P2.3 (src/transform/clean/tabla.py).

Qué se analiza (contrato de la capa clean): solo registros en español (`idioma_detectado = 'es'`),
que no sean bots (`es_bot = false`) y con texto.
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

tabla_sentimiento = Table(
    "sentimiento",
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
    Column("idioma_detectado", String),
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
    """Crea el esquema (solo en Postgres) y la tabla `sentimiento` si no existen."""
    if conexion.dialect.name == "postgresql" and esquema:
        if not _ESQUEMA_VALIDO.match(esquema):
            raise ValueError(f"nombre de esquema no válido: {esquema!r}")
        conexion.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"'))
    con_esquema(conexion, esquema)
    metadata.create_all(conexion, tables=[tabla_sentimiento])


def _elegibles():
    """Registros que se analizan: con texto, en español y que no son bots."""
    return and_(
        menciones.c.texto_limpio.is_not(None),
        func.length(func.trim(menciones.c.texto_limpio)) > 0,
        menciones.c.idioma_detectado == "es",
        menciones.c.es_bot.is_(False),
    )


def _union():
    return menciones.outerjoin(
        tabla_sentimiento, tabla_sentimiento.c.id_registro == menciones.c.id_registro
    )


def leer_pendientes(conexion, version_modelo: str, limite: int) -> list[dict[str, Any]]:
    """Registros elegibles (con texto, en español, sin bots) que aún no tienen resultado vigente.

    Pendiente = no tiene fila en `sentimiento`, o se analizó con otra versión del modelo,
    o el texto cambió desde entonces (reseña editada, P2.3 conserva la versión más reciente).
    """
    consulta = (
        select(menciones.c.id_registro, menciones.c.texto_limpio, menciones.c.hash_texto)
        .select_from(_union())
        .where(
            _elegibles(),
            or_(
                tabla_sentimiento.c.id_registro.is_(None),
                tabla_sentimiento.c.version_modelo != version_modelo,
                tabla_sentimiento.c.hash_texto.is_distinct_from(menciones.c.hash_texto),
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
        delete(tabla_sentimiento).where(
            tabla_sentimiento.c.id_registro.in_([f["id_registro"] for f in filas])
        )
    )
    conexion.execute(insert(tabla_sentimiento), filas)
    return len(filas)


def cobertura(conexion, version_modelo: str) -> dict[str, int]:
    """Cuántos registros elegibles hay y cuántos tienen resultado vigente."""
    total = conexion.execute(
        select(func.count()).select_from(menciones).where(_elegibles())
    ).scalar_one()
    vigentes = conexion.execute(
        select(func.count())
        .select_from(_union())
        .where(
            _elegibles(),
            tabla_sentimiento.c.id_registro.is_not(None),
            tabla_sentimiento.c.version_modelo == version_modelo,
            tabla_sentimiento.c.hash_texto.is_not_distinct_from(menciones.c.hash_texto),
        )
    ).scalar_one()
    return {"total": total, "con_resultado": vigentes, "pendientes": total - vigentes}


def ahora_utc() -> datetime:
    return datetime.now(UTC)
