"""
Scraper de Google Play para reseñas nuevas de Rappi en Colombia
"""

#Importación de librerías
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv
from google_play_scraper import Sort, reviews
from pydantic import ValidationError

from src.common.privacy import hash_autor
from src.common.schema import Fuente, RegistroMencion
from src.common.storage import guardar_registros, nuevo_run_id
from src.ingestion.google_play.marca_agua import MarcaAgua, guardar_marca, leer_marca

VERSION_SCRAPER = "0.1.0"
TAMANO_PAGINA = 100 # Reseñas por petición a Google Play

log = logging.getLogger(__name__)


@dataclass
class Config:
    app_id: str
    pais: str
    idioma: str
    max_resenas: int
    pausa_segundos: float = 2.0
    max_reintentos: int = 3

def cargar_config() -> Config:
    # Lee las variables GP_* del .env
    return Config(
        app_id=os.getenv("GP_APP_ID", "com.grability.rappi"),
        pais=os.getenv("GP_COUNTRY", "co"),
        idioma=os.getenv("GP_LANG", "es"),
        max_resenas=int(os.getenv("GP_MAX_REVIEWS_PER_RUN", "500")),
    )

def a_utc(fecha: datetime | None) -> datetime | None:
    #Se entregan fechas sin zona horaria
    return None if fecha is None else fecha.astimezone(timezone.utc)

def pedir_pagina(config:Config, token=None) -> tuple[list[dict], object]:
    # Pide una página de reseñas, con reintentos y espera de manera creciente.
    for intento in range(config.max_reintentos):
       resenas, siguiente_token = reviews(
            config.app_id,
            lang=config.idioma,
            country=config.pais,
            sort=Sort.NEWEST,
            count=TAMANO_PAGINA,
            continuation_token=token,
        )
       if resenas:
           return resenas, siguiente_token
       espera = 2**(intento+1) 
       log.warning("Página vacía (intento %d de %d). Reintento en %d s", intento + 1, config.max_reintentos, espera)
       time.sleep(espera)

    log.error("Google Play no devolvió reseñas tras %d intentos", config.max_reintentos)
    return[], None

def extraer_nuevas(
        config: Config,
        marca: MarcaAgua | None,
        pedir: Callable = pedir_pagina,
) -> list[dict]:
    nuevas: list[dict] = []
    vistas: set[str] = set()
    token = None
    while len(nuevas) < config.max_resenas:
        pagina, token = pedir(config, token)
        for resena in pagina:
            if marca is not None and (resena["reviewId"] == marca.id_original or a_utc(resena["at"]) < marca.fecha_publicacion):
                return nuevas[: config.max_resenas]
            if resena["reviewId"] in vistas:
                continue
            nuevas.append(resena)
            vistas.add(resena["reviewId"])        
        if not pagina or token is None:
            break
        time.sleep(config.pausa_segundos)
    return nuevas[: config.max_resenas]           

def a_registro(resena: dict, run_id:str, config: Config) -> RegistroMencion | None:
    # Convierte una reseña cruda en RegistroMencion. Si no cumple queda vacío
    try:
        return RegistroMencion(
            fuente=Fuente.GOOGLE_PLAY,
            id_original=resena["reviewId"],
            texto=resena["content"],
            fecha_publicacion=a_utc(resena["at"]),
            autor_hash=hash_autor(resena["userName"]),  # nunca guardar userName
            calificacion=resena["score"],
            likes=resena["thumbsUpCount"],
            version_app=resena["reviewCreatedVersion"],
            respuesta_marca=resena["replyContent"],
            fecha_respuesta=a_utc(resena["repliedAt"]),
            idioma=config.idioma,
            pais=config.pais,
            run_id=run_id,
            version_scraper=VERSION_SCRAPER,
        )
    except ValidationError as error:
        log.warning("Reseña %s descartada: %s", resena.get("reviewId"), error)
        return None

def correr() -> str | None:
    # Cada ejecución retorna la ruta la ubicación las reseñas.
    load_dotenv()
    config = cargar_config()
    run_id = nuevo_run_id()
    marca = leer_marca()

    resenas_crudas = extraer_nuevas(config, marca)
    registros = [r for r in (a_registro(x, run_id, config) for x in resenas_crudas) if r]
    ruta = guardar_registros(registros, run_id=run_id)
    if ruta:
        mas_nueva = resenas_crudas[0]
        guardar_marca(MarcaAgua(
            id_original=mas_nueva["reviewId"],
            fecha_publicacion=a_utc(mas_nueva["at"]),
        ))
 
    log.info("Corrida %s: %d reseñas guardadas en %s", run_id, len(registros), ruta)
    return ruta

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    correr()


