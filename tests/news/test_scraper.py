import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.common.storage import guardar_registros
from src.ingestion.news import scraper
from src.ingestion.news.estado import EstadoLocal

FEED = (Path(__file__).parent / "fixtures" / "feed_simulado.xml").read_bytes()


def respuesta(status=200, content=FEED):
    r = MagicMock()
    r.status_code = status
    r.content = content
    return r


@pytest.fixture
def almacen(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_BACKEND", "local")
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    return EstadoLocal(str(tmp_path))


def correr(almacen, feed=FEED, run_id="r1", **kwargs):
    with patch.object(scraper.requests, "get", return_value=respuesta(content=feed)):
        return scraper.correr("http://x", almacen, run_id, **kwargs)


def leer_jsonl(raiz):
    return [json.loads(linea) for f in Path(raiz, "raw").rglob("*.jsonl") for linea in f.read_text("utf-8").splitlines()]


def test_cumple_contrato_y_limpia_titular(almacen):
    correr(almacen)
    registros = leer_jsonl(almacen.raiz)
    assert len(registros) == 2
    uno = next(r for r in registros if r["url"].endswith("PRUEBA1"))
    assert uno["id_registro"] == "news:https://news.google.com/rss/articles/PRUEBA1"
    assert uno["fuente"] == "news" and uno["idioma"] == "es" and uno["pais"] == "co"
    assert uno["texto"] == "Noticia de prueba uno sobre Rappi"
    assert uno["medio"] == "Medio Ejemplo"
    assert uno["fecha_publicacion"] == "2026-11-02T13:00:00Z"
    dos = next(r for r in registros if r["url"].endswith("PRUEBA2"))
    assert dos["texto"] == "Noticia de prueba dos - con guion interno"


def test_ruta_sigue_el_contrato(almacen):
    ruta = correr(almacen, run_id="abc")["ruta"].replace("\\", "/")
    assert "raw/fuente=news/fecha=" in ruta and ruta.endswith("/run_abc.jsonl")


def test_dos_corridas_no_duplican(almacen):
    assert correr(almacen, run_id="r1")["registros_extraidos"] == 2
    segunda = correr(almacen, run_id="r2")
    assert segunda["registros_extraidos"] == 0 and segunda["ruta"] is None
    assert len(leer_jsonl(almacen.raiz)) == 2


def test_segunda_corrida_solo_trae_lo_nuevo(almacen):
    correr(almacen, run_id="r1")
    nuevo = b"""<item><title>Otra noticia - Medio</title><link>https://news.google.com/rss/articles/PRUEBA9</link>
    <pubDate>Mon, 02 Nov 2026 18:30:00 GMT</pubDate><source url="https://m.test">Medio</source></item></channel>"""
    assert correr(almacen, FEED.replace(b"</channel>", nuevo), run_id="r2")["registros_extraidos"] == 1
    assert len(leer_jsonl(almacen.raiz)) == 3


def test_noticia_con_fecha_futura_se_descarta(almacen):
    futura = b"""<item><title>Futura - Medio</title><link>https://news.google.com/rss/articles/F</link>
    <pubDate>Mon, 02 Nov 2099 18:30:00 GMT</pubDate></item></channel>"""
    resumen = correr(almacen, FEED.replace(b"</channel>", futura))
    assert resumen["registros_extraidos"] == 2 and resumen["descartados"] == 2


def test_dry_run_no_guarda(almacen):
    resumen = correr(None, dry_run=True)
    assert resumen["registros_extraidos"] == 2 and resumen["ruta"] is None
    assert not list(almacen.raiz.rglob("*"))


def test_si_falla_guardar_no_marca_como_vistos(almacen):
    with pytest.raises(OSError):
        correr(almacen, guardar=MagicMock(side_effect=OSError("disco lleno")))
    assert correr(almacen, run_id="r2", guardar=guardar_registros)["registros_extraidos"] == 2


def test_reintenta_y_luego_funciona():
    secuencia = [requests.ConnectionError("caída"), respuesta(503), respuesta()]
    with patch.object(scraper.requests, "get", side_effect=secuencia), patch.object(scraper.time, "sleep") as dormir:
        assert scraper.descargar_feed("http://x", "r1") == FEED
    assert [c.args[0] for c in dormir.call_args_list] == [2.0, 4.0]


def test_error_definitivo_no_reintenta():
    with (
        patch.object(scraper.requests, "get", return_value=respuesta(404)) as get,
        patch.object(scraper.time, "sleep"),
        pytest.raises(RuntimeError, match="HTTP 404"),
    ):
        scraper.descargar_feed("http://x", "r1")
    assert get.call_count == 1


def test_respuesta_que_no_es_feed_falla(almacen):
    with pytest.raises(RuntimeError):
        correr(almacen, feed=b"<html><body>captcha</body></html>")


def test_noticia_antigua_no_se_duplica(almacen):
    antigua = b"""<item><title>Noticia de hace meses - Medio</title><link>https://news.google.com/rss/articles/VIEJA</link>
    <pubDate>Mon, 02 Mar 2026 18:30:00 GMT</pubDate><source url="https://m.test">Medio</source></item></channel>"""
    feed = FEED.replace(b"</channel>", antigua)
    assert correr(almacen, feed, run_id="r1")["registros_extraidos"] == 3
    assert correr(almacen, feed, run_id="r2")["registros_extraidos"] == 0
    assert len(leer_jsonl(almacen.raiz)) == 3


def test_url_usa_variables_del_entorno(monkeypatch):
    monkeypatch.delenv("NEWS_RSS_URL", raising=False)
    monkeypatch.setenv("NEWS_QUERY", "Rappi Colombia")
    monkeypatch.setenv("NEWS_HL", "es-419")
    monkeypatch.setenv("NEWS_GL", "CO")
    url = scraper.construir_url()
    assert "q=Rappi+Colombia" in url and "hl=es-419" in url and "gl=CO" in url and "ceid=CO%3Aes-419" in url


def test_usa_el_id_del_feed_y_no_duplica_si_cambia_el_enlace(almacen):
    feed = b"""<rss version="2.0"><channel><item><title>Noticia - Medio</title><link>%s</link>
    <guid isPermaLink="false">TOKEN1</guid><pubDate>Mon, 02 Nov 2026 18:30:00 GMT</pubDate></item></channel></rss>"""
    correr(almacen, feed % b"https://news.google.com/rss/articles/TOKEN1?oc=5", run_id="r1")
    registro = leer_jsonl(almacen.raiz)[0]
    assert registro["id_original"] == "TOKEN1"
    assert registro["url"] == "https://news.google.com/rss/articles/TOKEN1?oc=5"
    assert correr(almacen, feed % b"https://news.google.com/rss/articles/TOKEN1?oc=6", run_id="r2")["registros_extraidos"] == 0

