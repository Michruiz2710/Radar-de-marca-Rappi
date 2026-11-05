"""Scraper de comentarios de YouTube sobre Rappi (P1.4).

Flujo de una corrida:
  1. Busca videos con YT_QUERY (100 unidades de cuota por búsqueda) y se queda
     solo con los que nombran la marca (YT_BRAND_TERMS) en el título, la
     descripción o el canal. El resto se descarta sin gastar cuota.
  2. Baja los comentarios de cada video, del más nuevo al más viejo
     (1 unidad por página de 100 comentarios).
  3. Convierte cada comentario en un RegistroMencion (contrato P1.2).
     Si no cumple el contrato, se descarta y se cuenta en el log.
  4. Guarda la corrida con guardar_registros() en la capa raw:
     raw/fuente=youtube/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl

Es incremental: guarda una marca de agua (la fecha del comentario más nuevo)
y la siguiente corrida solo baja comentarios posteriores.

Uso, desde la raíz del repo:
    python -m src.ingestion.youtube.scraper          # usa RAW_BACKEND del .env
    python -m src.ingestion.youtube.scraper --full   # ignora la marca de agua
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from datetime import UTC, datetime

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import ValidationError

from src.common.privacy import hash_autor
from src.common.schema import Fuente, RegistroMencion
from src.common.storage import guardar_registros, nuevo_run_id
from src.ingestion.youtube import estado

VERSION_SCRAPER = "0.1.0"

# Costo en unidades de cada llamada (la cuota diaria por defecto es 10.000)
COSTO_BUSQUEDA = 100
COSTO_COMENTARIOS = 1

log = logging.getLogger("scraper_youtube")


class CuotaAgotada(Exception):
    """Se llegó al presupuesto de cuota que fijamos para una corrida."""


def _fecha(valor: str) -> datetime:
    """'2026-11-03T15:00:00Z' -> datetime en UTC."""
    return datetime.fromisoformat(valor).astimezone(UTC)


class ScraperYouTube:
    def __init__(self, api_key: str, presupuesto: int = 8000, region: str = "CO",
                 idioma: str = "es", terminos_marca: tuple[str, ...] = ("rappi",), youtube=None):
        self.youtube = youtube or build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        self.presupuesto = presupuesto
        self.cuota_usada = 0
        self.region = region
        self.idioma = idioma
        # \b exige que el término empiece una palabra: sirve "RappiTurbo" o "#rappi", no "trappist"
        self.patron_marca = re.compile(
            r"\b(?:" + "|".join(re.escape(t) for t in terminos_marca) + ")", re.IGNORECASE
        )

    def es_de_la_marca(self, video: dict) -> bool:
        """True si el título, la descripción o el canal del video nombran la marca."""
        snippet = video.get("snippet", {})
        texto = " ".join(snippet.get(campo, "") for campo in ("title", "description", "channelTitle"))
        return bool(self.patron_marca.search(texto))

    def _gastar(self, unidades: int) -> None:
        if self.cuota_usada + unidades > self.presupuesto:
            raise CuotaAgotada(f"presupuesto de cuota agotado ({self.cuota_usada}/{self.presupuesto})")
        self.cuota_usada += unidades

    def _ejecutar(self, peticion, intentos: int = 3):
        """Ejecuta la llamada y reintenta con espera creciente si YouTube falla (5xx)."""
        for intento in range(intentos):
            try:
                return peticion.execute()
            except HttpError as error:
                if error.resp.status >= 500 and intento < intentos - 1:
                    espera = 2 ** intento
                    log.warning("YouTube respondió %s, reintento en %ss", error.resp.status, espera)
                    time.sleep(espera)
                    continue
                raise

    # ---------- 1. buscar videos ----------
    def buscar_videos(self, consulta: str, paginas: int) -> list[str]:
        ids, descartados, token = [], 0, None
        for _ in range(paginas):
            self._gastar(COSTO_BUSQUEDA)
            respuesta = self._ejecutar(self.youtube.search().list(
                q=consulta, part="snippet", type="video", maxResults=50, order="relevance",
                relevanceLanguage=self.idioma, regionCode=self.region, pageToken=token,
            ))
            for item in respuesta.get("items", []):
                if self.es_de_la_marca(item):
                    ids.append(item["id"]["videoId"])
                else:
                    descartados += 1
                    log.debug("video descartado, no nombra la marca: %s", item["id"]["videoId"])
            token = respuesta.get("nextPageToken")
            if not token:
                break
        log.info("búsqueda '%s': %d videos nombran la marca, %d descartados", consulta, len(ids), descartados)
        return ids

    # ---------- 2. bajar comentarios ----------
    def bajar_comentarios(self, video_id: str, maximo: int, desde: datetime | None = None) -> list[dict]:
        """Comentarios de primer nivel, del más nuevo al más viejo.
        Se detiene al llegar a `desde` (marca de agua) o a `maximo`."""
        hilos, token = [], None
        while len(hilos) < maximo:
            self._gastar(COSTO_COMENTARIOS)
            peticion = self.youtube.commentThreads().list(
                part="snippet", videoId=video_id, maxResults=100,
                order="time", textFormat="plainText", pageToken=token,
            )
            try:
                respuesta = self._ejecutar(peticion)
            except HttpError as error:
                if error.resp.status in (403, 404):  # comentarios desactivados o video borrado
                    log.info("video %s sin comentarios disponibles (%s)", video_id, error.resp.status)
                    return hilos
                raise
            for hilo in respuesta.get("items", []):
                publicado = _fecha(hilo["snippet"]["topLevelComment"]["snippet"]["publishedAt"])
                if desde and publicado <= desde:
                    return hilos
                hilos.append(hilo)
            token = respuesta.get("nextPageToken")
            if not token:
                break
        return hilos[:maximo]

    # ---------- 3. convertir al contrato ----------
    def a_registro(self, hilo: dict, run_id: str, extraccion: datetime) -> RegistroMencion:
        comentario = hilo["snippet"]["topLevelComment"]
        s = comentario["snippet"]
        video_id = s.get("videoId") or hilo["snippet"].get("videoId")
        return RegistroMencion(
            fuente=Fuente.YOUTUBE,
            id_original=comentario["id"],
            texto=s.get("textOriginal") or s.get("textDisplay") or "",
            fecha_publicacion=s["publishedAt"],
            idioma=self.idioma,
            pais=self.region,
            fecha_extraccion=extraccion,
            run_id=run_id,
            version_scraper=VERSION_SCRAPER,
            autor_hash=hash_autor(s.get("authorDisplayName")),  # nunca el nombre
            likes=int(s.get("likeCount", 0)),
            id_contenedor=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}&lc={comentario['id']}",
        )

    # ---------- todo junto ----------
    def correr(self, consultas: list[str], max_busquedas: int, max_comentarios: int,
               run_id: str, desde: datetime | None = None) -> list[RegistroMencion]:
        extraccion = datetime.now(UTC)
        registros: dict[str, RegistroMencion] = {}
        vistos, rechazados = set(), 0
        paginas = max(1, max_busquedas // max(1, len(consultas)))
        try:
            for consulta in consultas:
                for video_id in self.buscar_videos(consulta, paginas):
                    if video_id in vistos:
                        continue
                    vistos.add(video_id)
                    for hilo in self.bajar_comentarios(video_id, max_comentarios, desde):
                        try:
                            registro = self.a_registro(hilo, run_id, extraccion)
                        except ValidationError as error:
                            rechazados += 1
                            log.debug("comentario rechazado por el contrato: %s", error)
                            continue
                        registros.setdefault(registro.id_registro, registro)  # sin duplicados
        except CuotaAgotada as error:
            log.warning("%s; se guarda lo que se alcanzó a bajar", error)
        log.info("videos=%d comentarios=%d rechazados=%d cuota_usada=%d",
                 len(vistos), len(registros), rechazados, self.cuota_usada)
        return list(registros.values())


def main(argv: list[str] | None = None, youtube=None) -> str | None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Scraper de comentarios de YouTube sobre Rappi")
    parser.add_argument("--full", action="store_true", help="ignorar la marca de agua")
    args = parser.parse_args(argv)

    consultas = [c.strip() for c in os.getenv("YT_QUERY", "Rappi").split(",") if c.strip()]
    marca = None if args.full else estado.leer_marca()
    log.info("marca de agua: %s", marca.isoformat() if marca else "ninguna (primera corrida)")

    scraper = ScraperYouTube(
        os.getenv("YOUTUBE_API_KEY", ""),
        presupuesto=int(os.getenv("YT_QUOTA_BUDGET", "8000")),
        region=os.getenv("YT_REGION", "CO"),
        idioma=os.getenv("YT_LANG", "es"),
        terminos_marca=tuple(t.strip() for t in os.getenv("YT_BRAND_TERMS", "rappi").split(",") if t.strip()),
        youtube=youtube,
    )
    run_id = nuevo_run_id()
    registros = scraper.correr(
        consultas,
        max_busquedas=int(os.getenv("YT_MAX_SEARCHES_PER_DAY", "3")),
        max_comentarios=int(os.getenv("YT_MAX_COMMENTS_PER_VIDEO", "500")),
        run_id=run_id,
        desde=marca,
    )
    if not registros:
        log.info("no hay comentarios nuevos")
        return None

    ruta = guardar_registros(registros, run_id=run_id)
    estado.guardar_marca(max(r.fecha_publicacion for r in registros), run_id, len(registros))
    log.info("%d comentarios guardados en %s", len(registros), ruta)
    return ruta


if __name__ == "__main__":
    main()
