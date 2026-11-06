""" Pruebas del scraper de Google Play con respuestas simuladas."""
 
from dataclasses import replace
from datetime import datetime, timedelta
 
from src.ingestion.google_play.marca_agua import MarcaAgua
from src.ingestion.google_play.scraper import Config, a_registro, a_utc, extraer_nuevas
 
CONFIG = Config(app_id="com.grability.rappi", pais="co", idioma="es",
                max_resenas=500, pausa_segundos=0)
AHORA = datetime(2026, 11, 4, 20, 0)
 
def resena_cruda(n: int) -> dict:
    # Una reseña como la devuelve google-play-scraper; n=0 es la más nueva.
    return {
        "reviewId": f"gp-{n}",
        "userName": f"Usuario {n}",
        "content": f"Reseña número {n}",
        "score": 4,
        "thumbsUpCount": 0,
        "reviewCreatedVersion": "8.0.0",
        "at": AHORA - timedelta(minutes=n),
        "replyContent": None,
        "repliedAt": None,
    }
 
 
def pagina_falsa(resenas: list[dict]):
    # Devuelve una función que entrega `resenas` en una sola página y luego para.
    def pedir(config, token=None):
        return (resenas, None) if token is None else ([], None)
    return pedir
 
 
def ids(resenas: list[dict]) -> list[str]:
    # Solo los reviewId, para que los assert sean fáciles de leer.
    return [r["reviewId"] for r in resenas]
 
 
def test_primera_corrida_trae_todo():
    nuevas = extraer_nuevas(CONFIG, marca=None, pedir=pagina_falsa([resena_cruda(n) for n in range(5)]))
    assert len(nuevas) == 5
 
 
def test_se_detiene_en_la_marca_de_agua():
    resenas = [resena_cruda(n) for n in range(5)]
    marca = MarcaAgua(id_original="gp-3", fecha_publicacion=a_utc(resenas[3]["at"]))
 
    nuevas = extraer_nuevas(CONFIG, marca=marca, pedir=pagina_falsa(resenas))
 
    assert ids(nuevas) == ["gp-0", "gp-1", "gp-2"]
 
 
def test_respeta_el_tope_por_corrida():
    config_chica = replace(CONFIG, max_resenas=2)  # copia de CONFIG con otro tope
    resenas = [resena_cruda(n) for n in range(5)]
 
    nuevas = extraer_nuevas(config_chica, marca=None, pedir=pagina_falsa(resenas))
 
    assert ids(nuevas) == ["gp-0", "gp-1"]
 
 
def test_quita_duplicados_de_la_misma_corrida():
    # La reseña 0 llega dos veces en la misma página.
    resenas = [resena_cruda(0), resena_cruda(0), resena_cruda(1)]
 
    nuevas = extraer_nuevas(CONFIG, marca=None, pedir=pagina_falsa(resenas))
 
    assert ids(nuevas) == ["gp-0", "gp-1"]
 
 
def test_a_registro_no_guarda_el_nombre(monkeypatch):
    # monkeypatch pone una sal solo durante esta prueba; tu .env no se toca.
    monkeypatch.setenv("HASH_SALT", "sal-solo-para-pruebas")
 
    registro = a_registro(resena_cruda(0), run_id="run-prueba", config=CONFIG)
 
    assert registro is not None
    assert len(registro.autor_hash) == 64
    assert "Usuario 0" not in registro.a_json()
 