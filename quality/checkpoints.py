""" Checkpoints de calidad que llaman el pipeline de Prefect
    flows/pipeline.py llama a `validar_cruda(rutas)` después de la ingesta, con
    rutas = {fuente: ruta del archivo nuevo o None}. Si falla una regla CRÍTICA,
    la función lanza ValidacionCriticaError y el pipeline se detiene antes de la
    limpieza. Las advertencias solo quedan en el log.
"""

import logging 
import great_expectations as gx
import pandas as pd

from quality.reglas import critica
from quality.suites import preparar_tabla, suite_raw
from src.common.storage import leer_registros

log = logging.getLogger("quality.checkpoints")

class ValidacionCriticaError(Exception):
    """Falla al menos una regla critica si dato incumple contrato"""

def validar_tabla(tabla: pd.DataFrame, suite:gx.ExpectationSuite) -> dict:
    """ Corre suite sobre tabla y devuelve resumen con reglas que fallaron"""
    contexto = gx.get_context(mode = "ephemeral")
    lote = (
        contexto.data_sources.add_pandas("datos").add_dataframe_asset(suite.name).add_batch_definition_whole_dataframe("todo")
    )
    resultado = lote.get_batch(batch_parameters = {"dataframe": tabla}).validate(suite)

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
    """ Etapa de validación cruda del pipeline para cada archivo de cada fuente"""
    resumenes = []
    for fuente, ruta in rutas.items():
        if not ruta:
            log.info("Validación de raw %s: no hay archivo nuevo", fuente)
            continue
        resumen = validar_tabla(preparar_tabla(leer_registros(ruta)),
                                suite_raw(fuente))
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