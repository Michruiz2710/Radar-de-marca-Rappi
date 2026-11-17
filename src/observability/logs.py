"""Logs estructurados en JSON para todo el proyecto (P3.1).

Cada línea es un objeto JSON con timestamp, nivel, fuente, run_id, logger y mensaje.
La fuente y el run_id salen del contexto de la corrida (``contexto``) o de los
argumentos ``extra`` del log. Uso:

    from src.observability.logs import configurar_logs, contexto

    configurar_logs()
    with contexto(run_id="20261116T...", fuente="news"):
        log.info("Inicio de corrida")
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

_contexto: ContextVar[dict] = ContextVar("contexto_logs", default={})
_CAMPOS_ESTANDAR = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        actual = _contexto.get()
        datos = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "fuente": getattr(record, "fuente", None) or actual.get("fuente"),
            "run_id": getattr(record, "run_id", None) or actual.get("run_id"),
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        # Campos que el código pasa con extra={"extra_datos": {...}} (estilo del scraper de noticias)
        datos.update(getattr(record, "extra_datos", None) or {})
        # Cualquier otro campo pasado con extra={...}
        for clave, valor in vars(record).items():
            if clave not in _CAMPOS_ESTANDAR and clave not in datos and clave not in {"fuente", "run_id", "extra_datos"}:
                datos[clave] = valor
        if record.exc_info:
            datos["error"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def _es_de_pytest(manejador: logging.Handler) -> bool:
    return type(manejador).__module__.startswith("_pytest")


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Deja un solo manejador en el logger raíz que escribe JSON en stdout. Se puede llamar varias veces."""
    raiz = logging.getLogger()
    raiz.handlers[:] = [h for h in raiz.handlers if _es_de_pytest(h) or getattr(h, "_radar_json", False)]
    if not any(getattr(h, "_radar_json", False) for h in raiz.handlers):
        manejador = logging.StreamHandler(sys.stdout)
        manejador.setFormatter(FormatoJson())
        manejador._radar_json = True
        raiz.addHandler(manejador)
    raiz.setLevel(nivel)
    # httpx registra cada consulta a la API de Prefect: solo interesan sus advertencias
    for ruidoso in ("httpx", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


@contextmanager
def contexto(**valores):
    """Agrega run_id, fuente u otros campos a todos los logs dentro del bloque."""
    token = _contexto.set({**_contexto.get(), **{k: v for k, v in valores.items() if v is not None}})
    try:
        yield
    finally:
        _contexto.reset(token)


def fijar_contexto(**valores) -> None:
    """Como ``contexto`` pero sin bloque: queda fijo hasta que termina el proceso o el hilo."""
    _contexto.set({**_contexto.get(), **{k: v for k, v in valores.items() if v is not None}})
