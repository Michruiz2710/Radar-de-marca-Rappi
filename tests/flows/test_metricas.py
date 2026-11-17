from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from flows import metricas
from src.observability import metricas as obs


def test_cuenta_fallas_seguidas_y_reinicia_con_exito():
    assert metricas.registrar_resultado("pipeline:news", exito=False) == 1
    assert metricas.registrar_resultado("pipeline:news", exito=False) == 2
    assert metricas.registrar_resultado("pipeline:google_play", exito=False) == 1
    assert metricas.registrar_resultado("pipeline:news", exito=True) == 0


def test_los_ganchos_registran_la_duracion():
    flujo = SimpleNamespace(name="pipeline")
    corrida = SimpleNamespace(parameters={"fuentes": ["news"]}, start_time=datetime.now(UTC) - timedelta(seconds=20))
    metricas.al_terminar_bien(flujo, corrida, None)
    datos = obs._leer()["flujos"]["pipeline:news"]
    assert datos["conteo"] == 1 and 19 <= datos["suma"] <= 60


def test_un_error_en_las_metricas_no_rompe_el_flujo(monkeypatch):
    def rota(*a, **k):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(obs, "registrar_corrida", rota)
    assert metricas.registrar_resultado("pipeline", exito=True) == -1


def test_nombre_del_flujo_por_fuente():
    flujo = SimpleNamespace(name="pipeline")
    assert metricas._nombre_flujo(flujo, SimpleNamespace(parameters={"fuentes": ["news"]})) == "pipeline:news"
    assert metricas._nombre_flujo(flujo, SimpleNamespace(parameters={})) == "pipeline"
