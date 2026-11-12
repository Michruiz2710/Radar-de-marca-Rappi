"""La limpieza se conecta al orquestador (P2.1) por nombre: si alguien lo cambia, esta prueba avisa."""

from flows import pipeline
from src.transform.clean import limpieza


def test_el_orquestador_encuentra_la_funcion_limpiar():
    (etapa,) = [e for e in pipeline.ETAPAS if e.nombre == "limpieza"]
    assert pipeline.resolver(etapa.destino) is limpieza.limpiar
