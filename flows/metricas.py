"""Ganchos de éxito y fallo de los flujos.

Publican en el Pushgateway de Prometheus:
- ultima_corrida_exitosa_timestamp{flujo}  (alerta A3)
- ultima_corrida_fallida_timestamp{flujo}
- fallas_consecutivas{flujo}                (alerta A1: 2 o más)

Si PUSHGATEWAY_URL está vacía o el Pushgateway no responde, solo se deja un aviso
en el log: un problema de métricas nunca debe tumbar el pipeline. El Pushgateway lo
agrega P3.1.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("flows.metricas")
JOB = "radar_flujos"


def _archivo_estado() -> Path:
    return Path(os.getenv("LOCAL_RAW_DIR", "data")) / "estado" / "flujos.json"


def _leer_fallas() -> dict[str, int]:
    archivo = _archivo_estado()
    try:
        return json.loads(archivo.read_text("utf-8")) if archivo.exists() else {}
    except (OSError, ValueError):
        log.warning("No se pudo leer %s; el conteo de fallas empieza en 0", archivo)
        return {}


def _guardar_fallas(fallas: dict[str, int]) -> None:
    archivo = _archivo_estado()
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps(fallas), "utf-8")
        temporal.replace(archivo)
    except OSError as error:
        log.warning("No se pudo guardar el conteo de fallas: %s", error)


def publicar(flujo: str, valores: dict[str, float]) -> bool:
    """Publica gauges con la etiqueta flujo. Devuelve False si no se pudo."""
    url = os.getenv("PUSHGATEWAY_URL", "").strip()
    if not url:
        log.info("PUSHGATEWAY_URL vacía; métricas de %s sin publicar: %s", flujo, valores)
        return False
    try:
        from prometheus_client import CollectorRegistry, Gauge, pushadd_to_gateway

        registro = CollectorRegistry()
        for nombre, valor in valores.items():
            Gauge(nombre, nombre.replace("_", " "), registry=registro).set(valor)
        # pushadd solo reemplaza estas métricas; no borra las demás del grupo
        pushadd_to_gateway(url, job=JOB, grouping_key={"flujo": flujo}, registry=registro, timeout=5)
        return True
    except Exception as error:  # noqa: BLE001 - las métricas no deben romper el flujo
        log.warning("No se pudieron publicar las métricas de %s: %s", flujo, error)
        return False


def registrar_resultado(flujo: str, exito: bool) -> int:
    """Actualiza el conteo de fallas seguidas, publica y devuelve ese conteo."""
    fallas = _leer_fallas()
    fallas[flujo] = 0 if exito else fallas.get(flujo, 0) + 1
    _guardar_fallas(fallas)
    nombre = "ultima_corrida_exitosa_timestamp" if exito else "ultima_corrida_fallida_timestamp"
    publicar(flujo, {nombre: time.time(), "fallas_consecutivas": fallas[flujo]})
    return fallas[flujo]


def _nombre_flujo(flow, flow_run) -> str:
    # Si el pipeline corre para una sola fuente, la métrica se separa por fuente
    fuentes = (getattr(flow_run, "parameters", None) or {}).get("fuentes")
    if isinstance(fuentes, list | tuple) and len(fuentes) == 1:
        return f"{flow.name}:{fuentes[0]}"
    return flow.name


def al_fallar(flow, flow_run, state) -> None:
    """Gancho on_failure de Prefect."""
    flujo = _nombre_flujo(flow, flow_run)
    seguidas = registrar_resultado(flujo, exito=False)
    log.error("Flujo %s falló (%d seguidas): %s", flujo, seguidas, getattr(state, "message", ""))


def al_terminar_bien(flow, flow_run, state) -> None:
    """Gancho on_completion de Prefect."""
    registrar_resultado(_nombre_flujo(flow, flow_run), exito=True)
