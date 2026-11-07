"""Parámetros por entorno: dev, staging y prod.

El entorno se elige con APP_ENV. Aquí no van secretos: las claves siguen en .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

FUENTES = ("google_play", "youtube", "news")


@dataclass(frozen=True)
class Entorno:
    nombre: str
    # Cada cuántas horas corre el pipeline de cada fuente
    intervalos_horas: dict[str, float] = field(
        default_factory=lambda: {"google_play": 3, "youtube": 6, "news": 2}
    )
    # Reintentos por tarea, con espera creciente: base, 2*base, 4*base segundos
    reintentos: int = 3
    espera_base_segundos: float = 60
    # Tiempo máximo de una tarea antes de cancelarla
    timeout_tarea_segundos: float = 30 * 60


ENTORNOS = {
    # En dev las esperas son cortas para probar rápido en el computador
    "dev": Entorno(nombre="dev", espera_base_segundos=10),
    "staging": Entorno(nombre="staging", espera_base_segundos=30),
    "prod": Entorno(nombre="prod", espera_base_segundos=60),
}


def entorno_actual() -> Entorno:
    nombre = os.getenv("APP_ENV", "dev").strip().lower()
    if nombre not in ENTORNOS:
        raise ValueError(f"APP_ENV desconocido: '{nombre}' (usa {', '.join(ENTORNOS)})")
    return ENTORNOS[nombre]


def esperas(entorno: Entorno) -> list[float]:
    """Esperas entre reintentos: 2 s, 4 s, 8 s con base 2."""
    return [entorno.espera_base_segundos * 2**i for i in range(entorno.reintentos)]
