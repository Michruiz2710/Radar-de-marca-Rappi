"""Etapa de modelos analíticos (P3.4): corre `dbt build` al final del pipeline.

Va después del sentimiento, así las tablas de analytics quedan al día en cada corrida
con datos nuevos. Si una prueba de dbt falla, la etapa falla y el pipeline lo reporta
como cualquier otra etapa (alertas de P3.1).

dbt se importa al correr la etapa y no al cargar el módulo: así las pruebas y el CI
de Python no necesitan dbt instalado. En la imagen del orquestador sí está
(dbt/requirements-dbt.txt en flows/Dockerfile).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)

# Las tres fuentes corren con intervalos distintos y pueden coincidir. Dos `dbt build`
# a la vez sobre las mismas tablas chocan, así que se corren de a uno con un candado de archivo.
CANDADO = Path(os.getenv("DBT_CANDADO", "/tmp/radar-dbt.lock"))


class ModelosError(RuntimeError):
    """dbt terminó con errores o con pruebas fallidas."""


def proyecto_dbt() -> Path:
    """Carpeta del proyecto dbt. En la imagen es /app/dbt; se puede cambiar con DBT_PROJECT_DIR."""
    return Path(os.getenv("DBT_PROJECT_DIR", Path(__file__).resolve().parent.parent / "dbt"))


@contextmanager
def _de_a_uno():
    try:
        import fcntl
    except ImportError:  # Windows: no hay fcntl; ahí se corre a mano y no hay corridas simultáneas
        yield
        return
    CANDADO.parent.mkdir(parents=True, exist_ok=True)
    with CANDADO.open("w") as archivo:
        fcntl.flock(archivo, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(archivo, fcntl.LOCK_UN)


def resumir(resultados) -> dict[str, int]:
    """Cuenta los nodos de dbt por estado (success, pass, fail, error, skipped...)."""
    conteo: dict[str, int] = {}
    for resultado in resultados or []:
        estado = str(getattr(resultado.status, "value", resultado.status))
        conteo[estado] = conteo.get(estado, 0) + 1
    return conteo


def construir(rutas: dict[str, str | None], runner=None) -> dict:
    """Corre `dbt build` si la corrida trajo datos nuevos. Devuelve el conteo por estado.

    `runner` existe para las pruebas; por defecto es `dbt.cli.main.dbtRunner()`.
    """
    if not any(rutas.values()):
        log.info("Modelos: sin datos nuevos en esta corrida, no se reconstruyen")
        return {"sin_cambios": 1}

    if runner is None:
        from dbt.cli.main import dbtRunner

        runner = dbtRunner()

    proyecto = str(proyecto_dbt())
    with _de_a_uno():
        respuesta = runner.invoke(["build", "--project-dir", proyecto, "--profiles-dir", proyecto])

    resultados = getattr(respuesta.result, "results", None)
    resumen = resumir(resultados)
    log.info("Modelos: dbt build terminó con %s", resumen)

    if not respuesta.success:
        fallidos = [
            getattr(r.node, "name", "?")
            for r in resultados or []
            if str(getattr(r.status, "value", r.status)) in {"error", "fail"}
        ]
        detalle = f"falló en: {', '.join(fallidos)}" if fallidos else f"error: {respuesta.exception}"
        raise ModelosError(f"dbt build {detalle}")
    return resumen
