import json
import logging

from src.observability import logs


def formatear(**extra):
    registro = logging.makeLogRecord({"name": "prueba", "levelname": "INFO", "msg": "hola %s", "args": ("mundo",), **extra})
    return json.loads(logs.FormatoJson().format(registro))


def test_campos_obligatorios():
    datos = formatear()
    assert {"timestamp", "nivel", "fuente", "run_id", "logger", "mensaje"} <= set(datos)
    assert datos["mensaje"] == "hola mundo" and datos["nivel"] == "INFO" and datos["timestamp"].endswith("+00:00")


def test_toma_fuente_y_run_id_del_contexto():
    with logs.contexto(run_id="r1", fuente="news"):
        datos = formatear()
    assert datos["run_id"] == "r1" and datos["fuente"] == "news"
    assert formatear()["run_id"] is None


def test_el_extra_del_log_gana_y_se_agregan_campos():
    with logs.contexto(run_id="flujo", fuente="news"):
        datos = formatear(run_id="scraper", extra_datos={"intento": 2}, ruta="s3://x")
    assert datos["run_id"] == "scraper" and datos["intento"] == 2 and datos["ruta"] == "s3://x"


def test_incluye_el_error():
    try:
        raise ValueError("falló")
    except ValueError:
        import sys

        registro = logging.makeLogRecord({"msg": "x", "levelname": "ERROR", "exc_info": sys.exc_info()})
    assert "ValueError: falló" in json.loads(logs.FormatoJson().format(registro))["error"]


def test_configurar_es_idempotente_y_no_quita_a_pytest():
    raiz = logging.getLogger()
    antes = [h for h in raiz.handlers if logs._es_de_pytest(h)]
    logs.configurar_logs()
    logs.configurar_logs()
    propios = [h for h in raiz.handlers if getattr(h, "_radar_json", False)]
    assert len(propios) == 1 and all(h in raiz.handlers for h in antes)
    raiz.removeHandler(propios[0])
