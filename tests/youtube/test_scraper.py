"""Pruebas del scraper de YouTube (P1.4). No usan internet: la API se simula."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.common.schema import Fuente
from src.ingestion.youtube import scraper as yt
from src.ingestion.youtube.scraper import CuotaAgotada, ScraperYouTube

SAL = "sal-solo-para-pruebas"


@pytest.fixture(autouse=True)
def entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("HASH_SALT", SAL)
    monkeypatch.setenv("RAW_BACKEND", "local")
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    monkeypatch.setattr(yt, "load_dotenv", lambda: None)  # no leer el .env real
    return tmp_path


def hilo(cid, publicado, texto="Rappi llegó tarde", video="vid1", autor="@ana"):
    return {
        "snippet": {
            "videoId": video,
            "totalReplyCount": 0,
            "topLevelComment": {
                "id": cid,
                "snippet": {
                    "videoId": video, "textOriginal": texto, "authorDisplayName": autor,
                    "publishedAt": publicado, "likeCount": 3,
                },
            },
        }
    }


class Peticion:
    def __init__(self, respuesta):
        self.respuesta = respuesta

    def execute(self):
        return self.respuesta


class YouTubeFalso:
    """Imita youtube.search().list(...) y youtube.commentThreads().list(...)."""

    def __init__(self, paginas_comentarios, videos=("vid1",), snippets=None):
        self.paginas = list(paginas_comentarios)
        self.videos = videos
        self.snippets = snippets or {}
        self.pedidos = []  # videos a los que se les pidieron comentarios

    def search(self):
        videos, snippets = self.videos, self.snippets

        class Busqueda:
            def list(self, **kw):
                return Peticion({"items": [
                    {"id": {"videoId": v}, "snippet": snippets.get(v, {"title": f"Opiniones de Rappi {v}"})}
                    for v in videos
                ]})
        return Busqueda()

    def commentThreads(self):
        paginas, pedidos = self.paginas, self.pedidos

        class Comentarios:
            def list(self, **kw):
                pedidos.append(kw["videoId"])
                return Peticion(paginas.pop(0) if paginas else {"items": []})
        return Comentarios()


def test_comentario_cumple_el_contrato():
    s = ScraperYouTube("x", youtube=YouTubeFalso([]))
    r = s.a_registro(hilo("c1", "2026-11-01T10:00:00Z"), "run-test", datetime(2026, 11, 4, tzinfo=UTC))
    assert r.fuente == Fuente.YOUTUBE
    assert r.id_registro == "youtube:c1"
    assert r.id_contenedor == "vid1"
    assert r.pais == "co" and r.idioma == "es"
    assert len(r.autor_hash) == 64 and "ana" not in r.autor_hash
    assert r.calificacion is None


def test_texto_vacio_se_descarta():
    paginas = [{"items": [hilo("c1", "2026-11-01T10:00:00Z", texto="   "), hilo("c2", "2026-11-01T09:00:00Z")]}]
    s = ScraperYouTube("x", youtube=YouTubeFalso(paginas))
    registros = s.correr(["Rappi"], max_busquedas=1, max_comentarios=100, run_id="run-test")
    assert [r.id_original for r in registros] == ["c2"]


def test_paginacion_y_marca_de_agua():
    paginas = [
        {"items": [hilo("c3", "2026-11-03T00:00:00Z"), hilo("c2", "2026-11-02T00:00:00Z")], "nextPageToken": "p2"},
        {"items": [hilo("c1", "2026-10-01T00:00:00Z")]},
    ]
    s = ScraperYouTube("x", youtube=YouTubeFalso(paginas))
    hilos = s.bajar_comentarios("vid1", maximo=100, desde=datetime(2026, 10, 15, tzinfo=UTC))
    assert [h["snippet"]["topLevelComment"]["id"] for h in hilos] == ["c3", "c2"]
    assert s.cuota_usada == 2


def test_no_repite_videos_ni_comentarios():
    paginas = [{"items": [hilo("c1", "2026-11-01T00:00:00Z"), hilo("c1", "2026-11-01T00:00:00Z")]}]
    s = ScraperYouTube("x", youtube=YouTubeFalso(paginas))
    registros = s.correr(["Rappi", "Rappi opiniones"], max_busquedas=2, max_comentarios=100, run_id="r")
    assert len(registros) == 1
    assert s.cuota_usada == 100 + 1 + 100  # 2 búsquedas + 1 página de comentarios


def test_solo_baja_comentarios_de_videos_que_nombran_la_marca():
    snippets = {
        "v1": {"title": "Probé RappiTurbo en Bogotá"},
        "v2": {"title": "Receta de arepas", "description": "sin patrocinio"},
        "v3": {"title": "Domicilios en 10 minutos", "channelTitle": "Rappi Colombia"},
        "v4": {"title": "Cerveza trappist artesanal"},  # contiene "rappi" pero no es la marca
        "v5": {"title": "Unboxing", "description": "Pedido por #rappi con cupón"},
    }
    falso = YouTubeFalso([], videos=tuple(snippets), snippets=snippets)
    s = ScraperYouTube("x", youtube=falso)
    s.correr(["Rappi"], max_busquedas=1, max_comentarios=100, run_id="r")
    assert falso.pedidos == ["v1", "v3", "v5"]
    assert s.cuota_usada == 100 + 3  # los videos descartados no gastan cuota


def test_presupuesto_de_cuota():
    s = ScraperYouTube("x", presupuesto=50, youtube=YouTubeFalso([]))
    with pytest.raises(CuotaAgotada):
        s._gastar(100)


def test_corrida_completa_en_modo_local_es_incremental(entorno):
    primera = YouTubeFalso([{"items": [hilo("c2", "2026-11-02T00:00:00Z"), hilo("c1", "2026-11-01T00:00:00Z")]}])
    ruta = Path(yt.main([], youtube=primera))
    assert ruta.parts[-4:-2] == ("raw", "fuente=youtube")
    lineas = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]
    assert {linea["id_registro"] for linea in lineas} == {"youtube:c1", "youtube:c2"}
    assert all("authorDisplayName" not in linea for linea in lineas)

    estado = json.loads((entorno / "estado" / "youtube.json").read_text(encoding="utf-8"))
    assert estado["marca_de_agua"].startswith("2026-11-02")

    # Segunda corrida: solo hay un comentario más nuevo que la marca de agua
    segunda = YouTubeFalso([{"items": [hilo("c3", "2026-11-03T00:00:00Z"), hilo("c2", "2026-11-02T00:00:00Z")]}])
    ruta2 = Path(yt.main([], youtube=segunda))
    lineas2 = [json.loads(linea) for linea in ruta2.read_text(encoding="utf-8").splitlines()]
    assert [linea["id_registro"] for linea in lineas2] == ["youtube:c3"]
