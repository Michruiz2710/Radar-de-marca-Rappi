"""Checkpoints de calidad que llama el pipeline de Prefect (P2.2).

    flows/pipeline.py llama a `validar_cruda(rutas)` después de la ingesta, con
    rutas = {fuente de ruta del archivo nuevo o None}. Si falla una regla CRÍTICA,
    la función lanza ValidacionCriticaError y el pipeline se detiene antes de la
    limpieza. Las ADVERTENCIAS solo quedan en el log.
"""

import logging
import os
from functools import lru_cache
from itertools import count

import great_expectations as gx
import pandas as pd
from great_expectations.data_context import AbstractDataContext
from sqlalchemy import Engine, select

from quality.reglas import critica
from quality.suites import preparar_tabla, preparar_tabla_clean, suite_clean, suite_raw
from src.common.db import crear_motor, esquema_clean
from src.common.storage import leer_registros
from src.transform.clean.tabla import con_esquema, menciones

log = logging.getLogger("quality.checkpoints")


class ValidacionCriticaError(Exception):
    """Falló al menos una regla crítica por lo que el dato rompe el contrato."""


def directorio_data_docs() -> str:
    """Carpeta donde se guardan los Data Docs (reporte HTML)"""
    return os.path.abspath(os.getenv("DATA_DOCS_DIR", "data/data_docs"))


@lru_cache(maxsize=1)
def _contexto() -> AbstractDataContext:
    """Un solo contexto de GX por proceso. Índice de Data Docs muestra todas
    las validaciones de la corrida"""
    contexto = gx.get_context(mode="ephemeral")
    contexto.add_data_docs_site(
        site_name="radar",
        site_config={
            "class_name": "SiteBuilder",
            "store_backend": {"class_name": "TupleFilesystemStoreBackend", "base_directory": directorio_data_docs()},
            "site_index_builder": {"class_name": "DefaultSiteIndexBuilder"},
        },
    )
    contexto.data_sources.add_pandas("datos")
    return contexto


_numero_validacion = count(1)


def validar_tabla(tabla: pd.DataFrame, suite: gx.ExpectationSuite) -> dict:
    """Corre la suite como un Checkpoint de GX, actualiza los Data Docs y resume las fallas."""
    contexto = _contexto()
    nombre = f"{suite.name}_{next(_numero_validacion)}"  # cada validación con nombre único
    lote = contexto.data_sources.get("datos").add_dataframe_asset(nombre).add_batch_definition_whole_dataframe("todo")
    suite = contexto.suites.add_or_update(suite)
    validacion = contexto.validation_definitions.add(gx.ValidationDefinition(name=nombre, data=lote, suite=suite))
    checkpoint = contexto.checkpoints.add(
        gx.Checkpoint(
            name=f"checkpoint_{nombre}",
            validation_definitions=[validacion],
            actions=[gx.checkpoint.UpdateDataDocsAction(name="data_docs")],
        )
    )
    resultado_checkpoint = checkpoint.run(batch_parameters={"dataframe": tabla})
    resultado = next(iter(resultado_checkpoint.run_results.values()))

    fallidas = [
        {
            "regla": r.expectation_config.type,
            "columna": r.expectation_config.kwargs.get("column"),
            "severidad": r.expectation_config.severity.value,
            "filas_malas": r.result.get("unexpected_count"),
        }
        for r in resultado.results
        if not r.success
    ]
    return {
        "suite": suite.name,
        "filas": len(tabla),
        "criticas": [f for f in fallidas if f["severidad"] == critica],
        "advertencias": [f for f in fallidas if f["severidad"] != critica],
    }


def validar_cruda(rutas: dict[str, str | None]) -> list[dict]:
    """ Valida el archivo nuevo de cada fuente."""
    resumenes = []
    for fuente, ruta in rutas.items():
        if not ruta:
            log.info("Validación raw de %s: no hay archivo nuevo", fuente)
            continue
        resumen = validar_tabla(preparar_tabla(leer_registros(ruta)), suite_raw(fuente))
        resumen["ruta"] = ruta
        for falla in resumen["advertencias"]:
            log.warning("Advertencia en %s: %s", ruta, falla)
        for falla in resumen["criticas"]:
            log.error("Regla crítica fallida en %s: %s", ruta, falla)
        resumenes.append(resumen)

    con_criticas = [r["ruta"] for r in resumenes if r["criticas"]]
    if con_criticas:
        raise ValidacionCriticaError(f"Validación raw fallida en: {con_criticas}")
    return resumenes


def leer_clean(motor: Engine | None = None, esquema: str | None = None) -> pd.DataFrame:
    """ Lee la tabla `menciones` de la capa clean del entorno actual."""
    motor = motor or crear_motor()
    with motor.connect() as conexion:
        conexion = con_esquema(conexion, esquema or esquema_clean())
        return pd.read_sql(select(menciones), conexion)


def validar_limpia(rutas: dict[str, str | None], motor: Engine | None = None, esquema: str | None = None) -> dict | None:
    """ Valida la tabla clean después de la limpieza."""
    if not any(rutas.values()):
        log.info("Validación clean: no hubo archivos nuevos, la tabla no cambió")
        return None
    resumen = validar_tabla(preparar_tabla_clean(leer_clean(motor, esquema)), suite_clean())
    for falla in resumen["advertencias"]:
        log.warning("Advertencia en clean: %s", falla)
    for falla in resumen["criticas"]:
        log.error("Regla crítica fallida en clean: %s", falla)
    if resumen["criticas"]:
        raise ValidacionCriticaError(f"Validación clean fallida: {resumen['criticas']}")
    return resumen