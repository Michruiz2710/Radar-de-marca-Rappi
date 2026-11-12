"""Conexión compartida a Postgres (capas clean y analytics).

La usan la limpieza (P2.3), las validaciones (P2.2) y el sentimiento (P2.4),
para que todos se conecten igual y lean los mismos nombres de esquema.

Variables de entorno (las mismas del .env y del docker-compose):

- POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- PG_SCHEMA_CLEAN: esquema de la capa clean. Cambia por entorno
  (dev: clean, staging: clean_staging, prod: clean_prod; ver config/<entorno>.env)
- PG_SCHEMA_ANALYTICS: esquema de la capa analytics.
- DATABASE_URL (opcional): si existe, se usa tal cual. Útil para pruebas.

Ejemplo:

    from src.common.db import crear_motor, esquema_clean

    motor = crear_motor()
    with motor.connect() as conexion:
        ...
"""

import os

from sqlalchemy import URL, Engine, create_engine


def esquema_clean() -> str:
    """Nombre del esquema de la capa clean en el entorno actual."""
    return os.getenv("PG_SCHEMA_CLEAN", "clean")


def esquema_analytics() -> str:
    """Nombre del esquema de la capa analytics en el entorno actual."""
    return os.getenv("PG_SCHEMA_ANALYTICS", "analytics")


def url_postgres() -> URL | str:
    """URL de conexión armada con las variables POSTGRES_* (o DATABASE_URL)."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "radar"),
    )


def crear_motor(url: URL | str | None = None) -> Engine:
    """Crea el motor de SQLAlchemy. `pool_pre_ping` evita conexiones caídas."""
    return create_engine(url or url_postgres(), pool_pre_ping=True)
