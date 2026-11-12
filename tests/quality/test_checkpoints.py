""" Validación cruda: función que llama pipeline luego de la ingesta """

import json

import pytest

from quality.checkpoints import ValidacionCriticaError, validar_cruda
from tests.quality.test_suites import _registro_correcto

def _guardar(tmp_path, registros, nombre="run.jsonl") -> str:
    """Escribe un archivo JSON Lines como la capa raw y devuelve su ruta"""
    ruta = tmp_path/nombre
    ruta.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
    return str(ruta)

def test_archivo_correcto_pasa(tmp_path):
    ruta = _guardar(tmp_path, [_registro_correcto(), _registro_correcto(id_original = "gp-2")])
    resumenes = validar_cruda({"google_play": ruta})
    assert resumenes[0]["criticas"] == []
    assert resumenes[0]["filas"] == 2

def test_fuente_sin_archivo_nuevo_se_salta():
    assert validar_cruda({"google_play":None, "youtube":None}) == []

def test_regla_critica_detiene_el_flujo(tmp_path):
    malo = _registro_correcto()
    malo["userName"] = "Ana Pérez"
    ruta = _guardar(tmp_path, [malo])
    with pytest.raises(ValidacionCriticaError):
        validar_cruda({"google_play": ruta})

def test_advertencia_no_detiene_el_flujo(tmp_path):
    antiguo = _registro_correcto()
    antiguo["version_contrato"] = "1.1.0"
    ruta = _guardar(tmp_path, [antiguo])
    resumenes = validar_cruda({"google_play": ruta})
    assert resumenes[0]["criticas"] == []
    assert len(resumenes[0]["advertencias"]) == 1