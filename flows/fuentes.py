"""Una tarea por fuente que corre su scraper y devuelve la ruta guardada (o None)."""

from __future__ import annotations

import os
from collections.abc import Callable

from dotenv import load_dotenv


class FuenteOmitida(Exception):
    """La fuente no puede correr por configuración, por ejemplo sin API key."""


def correr_google_play() -> str | None:
    from src.ingestion.google_play import scraper

    return scraper.correr()


def correr_youtube() -> str | None:
    if not os.getenv("YOUTUBE_API_KEY", "").strip():
        raise FuenteOmitida("YOUTUBE_API_KEY vacía; YouTube no corre")
    from src.ingestion.youtube import scraper

    return scraper.main([])


def correr_noticias() -> str | None:
    from src.common.storage import nuevo_run_id
    from src.ingestion.news import scraper
    from src.ingestion.news.estado import crear_almacen_estado

    # Se usa correr() y no main(), porque main() atrapa los errores y el flujo no se enteraría
    scraper.configurar_logs()
    run_id = os.getenv("RUN_ID") or nuevo_run_id()
    resumen = scraper.correr(scraper.construir_url(), crear_almacen_estado(), run_id)
    return resumen["ruta"]


SCRAPERS: dict[str, Callable[[], str | None]] = {
    "google_play": correr_google_play,
    "youtube": correr_youtube,
    "news": correr_noticias,
}


def correr_fuente(fuente: str) -> str | None:
    load_dotenv()
    if fuente not in SCRAPERS:
        raise ValueError(f"Fuente desconocida: '{fuente}'")
    return SCRAPERS[fuente]()
