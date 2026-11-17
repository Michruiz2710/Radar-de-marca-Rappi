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

from prefect import flow, get_run_logger, runtime, task

from flows import fuentes as mod_fuentes
from flows.entornos import FUENTES, entorno_actual, esperas
from flows.metricas import al_fallar, al_terminar_bien
from src.observability import metricas as obs
from src.observability.logs import configurar_logs, contexto

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
    Etapa("modelos", "flows.modelos:construir", "P3.4"),
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


def contar_extraidos(fuente: str, ruta: str | None) -> int:
    """Cuenta los registros guardados en la corrida para registros_extraidos_total (P3.1)."""
    cantidad = 0
    if ruta:
        try:
            from src.common.storage import leer_registros

            cantidad = len(leer_registros(ruta))
        except Exception as error:  # noqa: BLE001 - contar no debe tumbar la ingesta
            get_run_logger().warning("No se pudieron contar los registros de %s: %s", ruta, error)
    # Se cuenta aunque sea 0: así la alerta A2 ve que Google Play no trajo nada
    obs.contar_registros(fuente, cantidad)
    return cantidad


@task(name="extraer", **_opciones_tarea)
def extraer(fuente: str) -> str | None:
    with contexto(fuente=fuente):
        ruta = mod_fuentes.correr_fuente(fuente)
        contar_extraidos(fuente, ruta)
        return ruta


def contar_validaciones(resumenes) -> None:
    """Suma a validaciones_fallidas_total lo que devolvió o adjuntó una validación de P2.2."""
    if isinstance(resumenes, dict):
        resumenes = [resumenes]
    for resumen in resumenes or []:
        suite = resumen.get("suite", "desconocida")
        for severidad, clave in (("critica", "criticas"), ("advertencia", "advertencias")):
            if resumen.get(clave):
                obs.contar_validacion(suite, severidad, len(resumen[clave]))


@task(name="etapa", **_opciones_tarea)
def correr_etapa(etapa: Etapa, rutas: dict[str, str | None]) -> str:
    logger = get_run_logger()
    funcion = resolver(etapa.destino)
    if funcion is None:
        logger.warning("Etapa %s pendiente: %s aún no existe (%s)", etapa.nombre, etapa.destino, etapa.paquete)
        return PENDIENTE
    try:
        resultado = funcion(rutas)
    except Exception as error:
        # ValidacionCriticaError trae sus resúmenes: se cuentan antes de detener el flujo
        contar_validaciones(getattr(error, "resumenes", None))
        raise
    if etapa.nombre.startswith("validacion"):
        contar_validaciones(resultado)
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
    configurar_logs()
    # Todos los logs de esta corrida llevan su run_id (el id de la corrida en Prefect)
    with contexto(run_id=str(runtime.flow_run.id)):
        return _correr_pipeline(list(fuentes or FUENTES))


def _correr_pipeline(pedidas: list[str]) -> dict:
    logger = get_run_logger()
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
