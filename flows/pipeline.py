"""Flujo principal: ingesta → validación cruda → limpieza → validación limpia → sentimiento.

Cada fuente tiene su propio flujo (ingesta_<fuente>) y el pipeline los llama. Las
etapas posteriores son de otros paquetes y se conectan por nombre: si el módulo
todavía no existe, la etapa queda como "pendiente" y el pipeline sigue. Si la etapa
existe y lanza un error, el pipeline se detiene (así se detienen las validaciones
críticas de P2.2).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass

from prefect import flow, get_run_logger, task

from flows import fuentes as mod_fuentes
from flows.entornos import FUENTES, entorno_actual, esperas
from flows.metricas import al_fallar, al_terminar_bien

PENDIENTE = "pendiente"


@dataclass(frozen=True)
class Etapa:
    nombre: str
    destino: str  # "modulo:funcion"; la función recibe el dict {fuente: ruta}
    paquete: str


# Nombres propuestos: se confirman con cada autor. Cambiarlos solo requiere tocar esta lista.
ETAPAS = (
    Etapa("validacion_cruda", "quality.checkpoints:validar_cruda", "P2.2"),
    Etapa("limpieza", "src.transform.clean.limpieza:limpiar", "P2.3"),
    Etapa("validacion_limpia", "quality.checkpoints:validar_limpia", "P2.2"),
    Etapa("sentimiento", "src.transform.nlp.sentimiento:analizar", "P2.4"),
)


def resolver(destino: str) -> Callable | None:
    """Devuelve la función de la etapa, o None si el módulo o la función no existen aún."""
    nombre_modulo, nombre_funcion = destino.split(":")
    try:
        modulo = importlib.import_module(nombre_modulo)
    except ModuleNotFoundError as error:
        # Solo cuenta como pendiente si falta el propio módulo, no una dependencia suya
        if error.name and nombre_modulo.startswith(error.name):
            return None
        raise
    return getattr(modulo, nombre_funcion, None)


_entorno = entorno_actual()
_opciones_tarea = {
    "retries": _entorno.reintentos,
    "retry_delay_seconds": esperas(_entorno),
    "timeout_seconds": _entorno.timeout_tarea_segundos,
}


@task(name="extraer", **_opciones_tarea)
def extraer(fuente: str) -> str | None:
    return mod_fuentes.correr_fuente(fuente)


@task(name="etapa", **_opciones_tarea)
def correr_etapa(etapa: Etapa, rutas: dict[str, str | None]) -> str:
    logger = get_run_logger()
    funcion = resolver(etapa.destino)
    if funcion is None:
        logger.warning("Etapa %s pendiente: %s aún no existe (%s)", etapa.nombre, etapa.destino, etapa.paquete)
        return PENDIENTE
    funcion(rutas)
    return "ok"


def _flujo_de_ingesta(fuente: str):
    @flow(name=f"ingesta_{fuente}", log_prints=True)
    def ingesta() -> str | None:
        logger = get_run_logger()
        try:
            ruta = extraer.with_options(name=f"extraer_{fuente}")(fuente)
        except mod_fuentes.FuenteOmitida as error:
            logger.warning("%s", error)
            return None
        logger.info("Fuente %s: %s", fuente, ruta or "sin registros nuevos")
        return ruta

    return ingesta


INGESTAS = {fuente: _flujo_de_ingesta(fuente) for fuente in FUENTES}


@flow(name="pipeline", log_prints=True, on_failure=[al_fallar], on_completion=[al_terminar_bien])
def pipeline(fuentes: list[str] | None = None) -> dict:
    """Corre la ingesta de las fuentes pedidas (todas si no se indica) y luego las etapas."""
    logger = get_run_logger()
    pedidas = list(fuentes or FUENTES)
    desconocidas = [f for f in pedidas if f not in INGESTAS]
    if desconocidas:
        raise ValueError(f"Fuentes desconocidas: {desconocidas}")

    rutas = {fuente: INGESTAS[fuente]() for fuente in pedidas}
    etapas = {}
    for etapa in ETAPAS:
        etapas[etapa.nombre] = correr_etapa.with_options(name=etapa.nombre)(etapa, rutas)

    resumen = {"entorno": _entorno.nombre, "rutas": rutas, "etapas": etapas}
    logger.info("Resumen: %s", resumen)
    return resumen
