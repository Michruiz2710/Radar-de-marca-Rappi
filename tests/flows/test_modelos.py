"""Etapa de modelos (P3.4). No necesitan dbt ni Postgres: usan un runner falso."""

from types import SimpleNamespace

import pytest

from flows import modelos


def _nodo(nombre, estado):
    return SimpleNamespace(node=SimpleNamespace(name=nombre), status=estado)


class RunnerFalso:
    def __init__(self, exito=True, resultados=(), excepcion=None):
        self.respuesta = SimpleNamespace(
            success=exito, result=SimpleNamespace(results=list(resultados)), exception=excepcion
        )
        self.argumentos = None

    def invoke(self, argumentos):
        self.argumentos = argumentos
        return self.respuesta


@pytest.fixture(autouse=True)
def candado_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(modelos, "CANDADO", tmp_path / "dbt.lock")


def test_sin_datos_nuevos_no_corre_dbt():
    runner = RunnerFalso()
    assert modelos.construir({"news": None, "youtube": None}, runner=runner) == {"sin_cambios": 1}
    assert runner.argumentos is None


def test_corre_build_con_el_proyecto_del_repo():
    runner = RunnerFalso(resultados=[_nodo("fct_menciones", "success"), _nodo("unique_x", "pass")])
    resumen = modelos.construir({"news": "raw/fuente=news/x.jsonl"}, runner=runner)
    assert resumen == {"success": 1, "pass": 1}
    assert runner.argumentos[0] == "build"
    proyecto = runner.argumentos[runner.argumentos.index("--project-dir") + 1]
    assert proyecto.endswith("dbt")


def test_prueba_fallida_detiene_la_etapa():
    runner = RunnerFalso(exito=False, resultados=[_nodo("fct_menciones", "success"), _nodo("fct_sin_bots", "fail")])
    with pytest.raises(modelos.ModelosError, match="fct_sin_bots"):
        modelos.construir({"news": "ruta"}, runner=runner)


def test_error_sin_resultados_muestra_la_excepcion():
    runner = RunnerFalso(exito=False, excepcion="no se pudo conectar a Postgres")
    with pytest.raises(modelos.ModelosError, match="Postgres"):
        modelos.construir({"news": "ruta"}, runner=runner)


def test_la_etapa_esta_en_el_pipeline_despues_del_sentimiento():
    from flows.pipeline import ETAPAS

    nombres = [e.nombre for e in ETAPAS]
    # conftest aísla las etapas pero conserva nombre y orden
    assert nombres[-1] == "modelos"
    assert nombres.index("modelos") > nombres.index("sentimiento")
