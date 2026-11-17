import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from src.observability import metricas

OCHO = {
    "registros_extraidos": "counter",
    "errores_http": "counter",
    "duracion_corrida_segundos": "histogram",
    "ultima_corrida_exitosa_timestamp": "gauge",
    "validaciones_fallidas": "counter",
    "registros_bot_ratio": "gauge",
    "cuota_youtube_usada": "gauge",
    "sentimiento_negativo_24h_ratio": "gauge",
}
GAUGES = {"registros_bot_ratio": {"youtube": 0.1}, "sentimiento_negativo_24h_ratio": {"google_play": 0.4}}


def exponer(estado):
    texto = generate_latest(metricas.registro_prometheus(estado)).decode()
    return texto, {f.name: f for f in text_string_to_metric_families(texto)}


def valor(familias, nombre, sufijo="", **etiquetas):
    for muestra in familias[nombre].samples:
        if muestra.name == nombre + sufijo and all(muestra.labels.get(k) == v for k, v in etiquetas.items()):
            return muestra.value
    return None


def corrida_completa(exito=True, duracion=42.0, ahora=None):
    metricas.contar_registros("news", 75)
    metricas.contar_registros("google_play", 0)
    metricas.contar_error_http("news", 429)
    metricas.contar_validacion("raw_google_play", "advertencia", 2)
    metricas.sumar_cuota_youtube(300)
    return metricas.registrar_corrida("pipeline:news", exito, duracion, gauges=GAUGES, ahora=ahora)


def test_publica_las_ocho_metricas_con_su_tipo():
    _, familias = exponer(corrida_completa())
    for nombre, tipo in OCHO.items():
        assert familias[nombre].type == tipo, nombre
    assert valor(familias, "registros_extraidos", "_total", fuente="news") == 75
    assert valor(familias, "registros_extraidos", "_total", fuente="google_play") == 0
    assert valor(familias, "errores_http", "_total", fuente="news", codigo="429") == 1
    assert valor(familias, "validaciones_fallidas", "_total", suite="raw_google_play", severidad="advertencia") == 2
    assert valor(familias, "cuota_youtube_usada") == 300
    assert valor(familias, "registros_bot_ratio", fuente="youtube") == 0.1
    assert valor(familias, "sentimiento_negativo_24h_ratio", fuente="google_play") == 0.4
    assert valor(familias, "duracion_corrida_segundos", "_count", flujo="pipeline:news") == 1
    assert valor(familias, "duracion_corrida_segundos", "_bucket", flujo="pipeline:news", le="60.0") == 1
    assert valor(familias, "duracion_corrida_segundos", "_bucket", flujo="pipeline:news", le="30.0") == 0
    assert valor(familias, "fallas_consecutivas", flujo="pipeline:news") == 0


def test_todas_las_metricas_aparecen_aunque_no_haya_errores():
    _, familias = exponer(metricas.registrar_corrida("pipeline:news", True, 3.0, gauges=GAUGES))
    for nombre in OCHO:
        assert familias[nombre].samples, f"{nombre} no tiene ninguna serie"
    assert valor(familias, "errores_http", "_total", fuente="google_play", codigo="429") == 0
    assert valor(familias, "validaciones_fallidas", "_total", suite="clean_menciones", severidad="critica") == 0


def test_los_contadores_se_acumulan_entre_corridas_y_no_bajan():
    corrida_completa()
    _, familias = exponer(corrida_completa())
    assert valor(familias, "registros_extraidos", "_total", fuente="news") == 150
    assert valor(familias, "errores_http", "_total", fuente="news", codigo="429") == 2
    assert valor(familias, "duracion_corrida_segundos", "_count", flujo="pipeline:news") == 2


def test_lo_pendiente_se_vacia_al_registrar():
    corrida_completa()
    estado = metricas.registrar_corrida("pipeline:news", True)
    assert estado["registros"]["news"] == 75


def test_fallas_seguidas_y_timestamps():
    metricas.registrar_corrida("pipeline:news", False)
    estado = metricas.registrar_corrida("pipeline:news", False)
    assert estado["flujos"]["pipeline:news"]["fallas"] == 2 and estado["flujos"]["pipeline:news"]["exitosa"] is None
    estado = metricas.registrar_corrida("pipeline:news", True)
    assert estado["flujos"]["pipeline:news"]["fallas"] == 0 and estado["flujos"]["pipeline:news"]["exitosa"]


def test_la_cuota_se_reinicia_cada_dia_del_pacifico():
    dia1 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    corrida_completa(ahora=dia1)
    assert corrida_completa(ahora=dia1 + timedelta(hours=1))["cuota_youtube"]["usada"] == 600
    # 08:30 UTC ya es otro día en el Pacífico (00:30 hora del Pacífico)
    assert corrida_completa(ahora=datetime(2026, 11, 17, 8, 30, tzinfo=UTC))["cuota_youtube"]["usada"] == 300


def test_estado_danado_empieza_en_cero():
    archivo = metricas.archivo_estado()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("{roto", "utf-8")
    assert corrida_completa()["registros"]["news"] == 75


def test_dos_corridas_a_la_vez_no_pierden_conteos():
    def una():
        metricas.registrar_corrida("pipeline:google_play", False)

    hilos = [threading.Thread(target=una) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert metricas._leer()["flujos"]["pipeline:google_play"]["fallas"] == 8
    assert not metricas.archivo_estado().with_suffix(".lock").exists()


def test_sin_pushgateway_no_falla():
    assert metricas.publicar(metricas._vacio()) is False


def test_pushgateway_caido_no_falla(monkeypatch):
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://localhost:9")
    assert metricas.publicar(metricas._vacio()) is False


def test_publica_en_el_pushgateway(monkeypatch):
    recibido = {}

    class Falso(BaseHTTPRequestHandler):
        def do_PUT(self):
            recibido["ruta"] = self.path
            recibido["cuerpo"] = self.rfile.read(int(self.headers["Content-Length"])).decode()
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Falso)
    threading.Thread(target=servidor.handle_request, daemon=True).start()
    monkeypatch.setenv("PUSHGATEWAY_URL", f"http://127.0.0.1:{servidor.server_port}")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    corrida_completa()
    servidor.server_close()
    assert recibido["ruta"] == "/metrics/job/radar_pipeline"
    assert 'registros_extraidos_total{fuente="news"} 75.0' in recibido["cuerpo"]
