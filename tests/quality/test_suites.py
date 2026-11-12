"""suite raw: reglas y archivo que las pasan"""

import great_expectations as gx
import pytest

from quality.reglas import critica
from quality.suites import preparar_tabla, suite_raw
from src.common.schema import Fuente, RegistroMencion

def _registro_correcto(**cambios) -> dict:
    """Registro de google play válido"""
    datos = {
        "fuente": Fuente.GOOGLE_PLAY,
        "id_original": "gp-1",
        "texto": "El pedido llegó tarde",
        "fecha_publicacion": "2026-11-02T13:00:00Z",
        "autor_hash": "a" * 64,
        "calificacion": 2,
        "run_id" : "20261102T150000Z-1a2b3c4d",
        "version_scraper": "0.1.0",
    }
    datos.update(cambios)
    return RegistroMencion(**datos).model_dump(mode="json")

def _validar(registros, fuente="google_play"):
    contexto = gx.get_context(mode="ephemeral")
    lote = (
        contexto.data_sources.add_pandas("prueba").add_dataframe_asset("raw").add_batch_definition_whole_dataframe("todo")
    )
    batch = lote.get_batch(batch_parameters={"dataframe": preparar_tabla(registros)})
    return batch.validate(suite_raw(fuente))

def test_fuente_desconocida():
    with pytest.raises(ValueError):
        suite_raw("reddit")

def test_la_suite_tiene_reglas_criticas_y_advertencias():
    severidades = {regla.severity.value for regla in suite_raw("google_play").expectations}
    assert severidades == {"critical", "warning"}

def test_archivo_correcto_pasa():
    registros = [_registro_correcto(), _registro_correcto(id_original = "gp-2", calificacion = 5)]
    resultado = _validar(registros)
    fallidas = [r.expectation_config.type for r in resultado.results if not r.success]
    assert fallidas == []

def test_calificacion_fuera_de_rango_es_critica():
    registro = _registro_correcto()
    registro["calificacion"] = 9
    resultado = _validar([registro])
    fallidas = [r for r in resultado.results if not r.success]
    assert [r.expectation_config.severity.value for r in fallidas] == [critica]