"""Ganchos de fin de corrida del flujo pipeline (P2.1 y P3.1).

Al terminar cada corrida, bien o mal, calculan la duración y las métricas de la capa
clean (bots y sentimiento negativo de 24 h) y publican todo en el Pushgateway con
``src.observability.metricas``. Un problema de métricas nunca detiene el pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.observability import consultas
from src.observability import metricas as obs

log = logging.getLogger("flows.metricas")


def _nombre_flujo(flow, flow_run) -> str:
    # Si el pipeline corre para una sola fuente, la métrica se separa por fuente
    fuentes = (getattr(flow_run, "parameters", None) or {}).get("fuentes")
    if isinstance(fuentes, list | tuple) and len(fuentes) == 1:
        return f"{flow.name}:{fuentes[0]}"
    return flow.name


def _duracion(flow_run) -> float | None:
    inicio = getattr(flow_run, "start_time", None)
    if inicio is None:
        return None
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - inicio).total_seconds())


def registrar_resultado(flujo: str, exito: bool, duracion: float | None = None) -> int:
    """Cierra la corrida y devuelve cuántas fallas seguidas lleva el flujo."""
    try:
        estado = obs.registrar_corrida(flujo, exito, duracion, gauges=consultas.calcular())
        return estado["flujos"][flujo]["fallas"]
    except Exception as error:  # noqa: BLE001 - las métricas no deben romper el flujo
        log.warning("No se pudieron registrar las métricas de %s: %s", flujo, error)
        return -1


def al_fallar(flow, flow_run, state) -> None:
    """Gancho on_failure de Prefect."""
    flujo = _nombre_flujo(flow, flow_run)
    seguidas = registrar_resultado(flujo, exito=False, duracion=_duracion(flow_run))
    log.error("Flujo %s falló (%d seguidas): %s", flujo, seguidas, getattr(state, "message", ""))


def al_terminar_bien(flow, flow_run, state) -> None:
    """Gancho on_completion de Prefect."""
    registrar_resultado(_nombre_flujo(flow, flow_run), exito=True, duracion=_duracion(flow_run))
