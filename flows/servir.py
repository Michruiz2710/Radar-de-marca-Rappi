"""Registra los despliegues en el servidor de Prefect y los deja corriendo.

    python -m flows.servir

Crea un despliegue por fuente con su intervalo y uno manual con todas las fuentes.
El proceso debe seguir encendido: si se detiene, las corridas programadas no se ejecutan.
"""

from __future__ import annotations

from datetime import timedelta

from prefect import serve

from flows.entornos import Entorno, entorno_actual
from flows.pipeline import pipeline


def crear_despliegues(entorno: Entorno):
    despliegues = [
        pipeline.to_deployment(
            name=f"{fuente}-{entorno.nombre}",
            interval=timedelta(hours=horas),
            parameters={"fuentes": [fuente]},
            tags=[entorno.nombre, fuente],
        )
        for fuente, horas in entorno.intervalos_horas.items()
    ]
    despliegues.append(pipeline.to_deployment(name=f"todas-{entorno.nombre}", tags=[entorno.nombre, "manual"]))
    return despliegues


def main() -> None:
    serve(*crear_despliegues(entorno_actual()))


if __name__ == "__main__":
    main()
