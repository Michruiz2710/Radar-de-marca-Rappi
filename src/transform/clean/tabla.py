"""Tabla `menciones` de la capa clean y su carga sin duplicados.

La tabla se define sin esquema y el esquema real se asigna al conectarse
(`schema_translate_map`), porque cambia por entorno: clean, clean_staging, clean_prod.
Así el mismo código funciona en Postgres y, en las pruebas, en SQLite.
"""

from datetime import timezone

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    bindparam,
    or_,
    select,
    text,
)
from sqlalchemy.dialects import postgresql, sqlite

metadata = MetaData()

menciones = Table(
    "menciones",
    metadata,
    # --- Identidad ---
    Column("id_registro", String, primary_key=True),
    Column("fuente", String, nullable=False),
    Column("id_original", String, nullable=False),
    # --- Texto (solo la versión limpia: el original con posibles datos personales se queda en raw) ---
    Column("texto_limpio", Text, nullable=False),
    Column("hash_texto", String(64), nullable=False),
    Column("idioma_consulta", String(8), nullable=False),
    Column("idioma_detectado", String(8), nullable=False),
    Column("pais", String(8), nullable=False),
    # --- Fechas (UTC) ---
    Column("fecha_publicacion", DateTime(timezone=True), nullable=False),
    Column("fecha_extraccion", DateTime(timezone=True), nullable=False),
    # --- Campos del contrato ---
    Column("autor_hash", String(64)),
    Column("calificacion", Integer),
    Column("likes", Integer),
    Column("version_app", String),
    Column("respuesta_marca", Text),
    Column("fecha_respuesta", DateTime(timezone=True)),
    Column("editada_tras_respuesta", Boolean),
    Column("fecha_edicion", DateTime(timezone=True)),
    Column("id_contenedor", String),
    Column("url", Text),
    Column("medio", String),
    # --- Bots ---
    Column("es_bot", Boolean, nullable=False),
    Column("motivo_bot", String),
    # --- Trazabilidad y linaje ---
    Column("run_id", String, nullable=False),
    Column("version_scraper", String),
    Column("version_contrato", String),
    Column("version_limpieza", String, nullable=False),
    Column("procesado_en", DateTime(timezone=True), nullable=False),
)

COLUMNAS = [c.name for c in menciones.columns]
_LOTE = 1000


def con_esquema(conexion: Connection, esquema: str | None) -> Connection:
    """Hace que la tabla `menciones` apunte al esquema del entorno.

    SQLite (solo se usa en las pruebas) no tiene esquemas: ahí la tabla va sin esquema.
    """
    if conexion.dialect.name == "sqlite":
        esquema = None
    return conexion.execution_options(schema_translate_map={None: esquema})


def crear_tabla(conexion: Connection, esquema: str | None) -> None:
    """Crea el esquema (solo en Postgres) y la tabla si no existen."""
    if conexion.dialect.name == "postgresql" and esquema:
        conexion.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"'))
    metadata.create_all(con_esquema(conexion, esquema))


def _debe_actualizar(nueva: dict, actual) -> bool:
    """Misma regla que el upsert: gana la versión más reciente del registro."""
    return (
        nueva["fecha_publicacion"] > _con_zona(actual.fecha_publicacion)
        or (
            nueva["fecha_publicacion"] == _con_zona(actual.fecha_publicacion)
            and nueva["fecha_extraccion"] > _con_zona(actual.fecha_extraccion)
        )
        or nueva["version_limpieza"] != actual.version_limpieza
    )


def _con_zona(fecha):
    """SQLite devuelve fechas sin zona horaria; en este proyecto todas son UTC."""
    return fecha if fecha is None or fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def cargar(conexion: Connection, esquema: str | None, filas: list[dict]) -> dict[str, int]:
    """Inserta o actualiza las filas en `menciones`, una por `id_registro`.

    Si el registro ya existe, solo se reemplaza cuando la versión nueva es más
    reciente (reseña editada) o cuando cambió la versión de la limpieza.
    Volver a cargar el mismo archivo no cambia nada (es idempotente).
    """
    conexion = con_esquema(conexion, esquema)
    resumen = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0}
    dialecto = postgresql if conexion.dialect.name == "postgresql" else sqlite

    for inicio in range(0, len(filas), _LOTE):
        lote = filas[inicio : inicio + _LOTE]

        # Conteo para el resumen: qué ya existía y qué va a cambiar
        consulta = select(
            menciones.c.id_registro,
            menciones.c.fecha_publicacion,
            menciones.c.fecha_extraccion,
            menciones.c.version_limpieza,
        ).where(menciones.c.id_registro.in_(bindparam("ids", expanding=True)))
        existentes = {f.id_registro: f for f in conexion.execute(consulta, {"ids": [f["id_registro"] for f in lote]})}
        for fila in lote:
            actual = existentes.get(fila["id_registro"])
            if actual is None:
                resumen["nuevos"] += 1
            elif _debe_actualizar(fila, actual):
                resumen["actualizados"] += 1
            else:
                resumen["sin_cambios"] += 1

        insercion = dialecto.insert(menciones)
        nueva = insercion.excluded
        insercion = insercion.on_conflict_do_update(
            index_elements=["id_registro"],
            set_={c: nueva[c] for c in COLUMNAS if c != "id_registro"},
            where=or_(
                nueva.fecha_publicacion > menciones.c.fecha_publicacion,
                and_(
                    nueva.fecha_publicacion == menciones.c.fecha_publicacion,
                    nueva.fecha_extraccion > menciones.c.fecha_extraccion,
                ),
                nueva.version_limpieza != menciones.c.version_limpieza,
            ),
        )
        conexion.execute(insercion, lote)

    return resumen
