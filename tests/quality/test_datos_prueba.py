""" Criterio de aceptación de validaciones donde archivos buenos pasan
    pero incorrectos detienen flujo
"""

from pathlib import Path

import pytest

from quality.checkpoints import ValidacionCriticaError, validar_cruda

datos = Path(__file__).parents[2] / "quality" / "datos_prueba"
correctos = sorted((datos/"correctos").glob("*.jsonl"))
incorrectos = sorted((datos/"incorrectos").glob("*.jsonl"))

def test_hay_datos_de_prueba_de_las_tres_fuentes():
    assert {r.stem for r in correctos} == {"google_play", "youtube", "news"}
    assert {r.stem.split("__")[0] for r in incorrectos} == {"google_play", "youtube", "news"}

@pytest.mark.parametrize("ruta", correctos, ids=lambda r:r.stem)
def test_archivo_correcto_pasa(ruta):
    resumenes = validar_cruda({ruta.stem: str(ruta)})
    assert resumenes[0]["criticas"] == []
    assert resumenes[0]["advertencias"] == []

@pytest.mark.parametrize("ruta", incorrectos, ids=lambda r: r.stem)
def test_archivo_incorrecto_detiene_el_flujo(ruta):
    fuente = ruta.stem.split("__")[0]
    with pytest.raises(ValidacionCriticaError):
        validar_cruda({fuente: str(ruta)})