""" Constantes de quality/reglas.py  deben coincidir con el contrato
en código """

from quality import reglas
from src.common.schema import RegistroMencion

def test_obligatorios_son_campos_del_contrato():
    assert set(reglas.obligatorios) <= set(reglas.campos_contrato)

def test_los_requeridos_del_modelo_estan_en_obligatorios():
    requeridos = {nombre for nombre, campo in
                  RegistroMencion.model_fields.items() if campo.is_required()}
    assert requeridos <= set(reglas.obligatorios)

def test_columnas_por_fuente_existen_en_el_contrato():
    for columna in reglas.solo_google_play + reglas.solo_news + reglas.columnas_fecha:
        assert columna in reglas.campos_contrato

def test_fuentes_permitidas():
    assert sorted(reglas.fuentes_permitidas) == ["google_play", "news", "youtube"]