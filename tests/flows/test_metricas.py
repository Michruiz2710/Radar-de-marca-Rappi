from types import SimpleNamespace
from unittest.mock import patch

from flows import metricas


def test_cuenta_fallas_seguidas_y_reinicia_con_exito():
    assert metricas.registrar_resultado("pipeline:news", exito=False) == 1
    assert metricas.registrar_resultado("pipeline:news", exito=False) == 2
    assert metricas.registrar_resultado("pipeline:google_play", exito=False) == 1
    assert metricas.registrar_resultado("pipeline:news", exito=True) == 0


def test_sin_pushgateway_no_falla():
    assert metricas.publicar("pipeline", {"fallas_consecutivas": 1}) is False


def test_pushgateway_caido_no_falla(monkeypatch):
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://localhost:9")
    assert metricas.publicar("pipeline", {"fallas_consecutivas": 1}) is False


def test_publica_en_el_grupo_del_flujo(monkeypatch):
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway:9091")
    with patch("prometheus_client.pushadd_to_gateway") as enviar:
        metricas.registrar_resultado("pipeline:news", exito=False)
    _, kwargs = enviar.call_args
    assert enviar.call_args.args[0] == "http://pushgateway:9091"
    assert kwargs["job"] == "radar_flujos" and kwargs["grouping_key"] == {"flujo": "pipeline:news"}
    nombres = {m.name for m in kwargs["registry"].collect()}
    assert nombres == {"ultima_corrida_fallida_timestamp", "fallas_consecutivas"}


def test_estado_danado_empieza_en_cero(tmp_path):
    archivo = metricas._archivo_estado()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("{roto", "utf-8")
    assert metricas.registrar_resultado("pipeline", exito=False) == 1


def test_nombre_del_flujo_por_fuente():
    flujo = SimpleNamespace(name="pipeline")
    assert metricas._nombre_flujo(flujo, SimpleNamespace(parameters={"fuentes": ["news"]})) == "pipeline:news"
    assert metricas._nombre_flujo(flujo, SimpleNamespace(parameters={})) == "pipeline"
