"""Scraper de noticias sobre Rappi desde el RSS de Google News (paquete P1.5)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

import feedparser
import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from src.common.schema import Fuente, RegistroMencion
from src.common.storage import guardar_registros, nuevo_run_id
from src.ingestion.news.estado import crear_almacen_estado

VERSION_SCRAPER = "0.1.0"
RUTA_ESTADO = "state/fuente=news/enlaces_vistos.json"
CODIGOS_REINTENTABLES = {429, 500, 502, 503, 504}

log = logging.getLogger("news")


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "timestamp": datetime.now(UTC).isoformat(),
            "nivel": record.levelname,
            "fuente": Fuente.NEWS.value,
            "run_id": getattr(record, "run_id", None),
            "mensaje": record.getMessage(),
        }
        datos.update(getattr(record, "extra_datos", {}))
        return json.dumps(datos, ensure_ascii=False)


def configurar_logs() -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJson())
    log.handlers[:] = [manejador]
    log.setLevel(logging.INFO)
    log.propagate = False


def construir_url() -> str:
    """URL del RSS a partir de NEWS_QUERY, NEWS_HL y NEWS_GL; NEWS_RSS_URL la reemplaza en pruebas."""
    if url := os.getenv("NEWS_RSS_URL"):
        return url
    idioma = os.getenv("NEWS_HL", "es-419")
    pais = os.getenv("NEWS_GL", "CO")
    parametros = {"q": os.getenv("NEWS_QUERY", "Rappi"), "hl": idioma, "gl": pais, "ceid": f"{pais}:{idioma}"}
    return f"https://news.google.com/rss/search?{urlencode(parametros)}"


def descargar_feed(url: str, run_id: str, intentos: int = 4, espera_base: float = 2.0, timeout: int = 20) -> bytes:
    """Descarga el feed con reintentos y espera creciente (2 s, 4 s, 8 s)."""
    ultimo_error: Exception | None = None
    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.get(
                url, timeout=timeout, headers={"User-Agent": f"radar-de-marca-rappi/{VERSION_SCRAPER} (proyecto academico)"}
            )
            if respuesta.status_code == 200:
                return respuesta.content
            ultimo_error = RuntimeError(f"HTTP {respuesta.status_code}")
            if respuesta.status_code not in CODIGOS_REINTENTABLES:
                break
        except requests.RequestException as error:
            ultimo_error = error
        log.warning(
            "Falló la descarga del feed",
            extra={"run_id": run_id, "extra_datos": {"intento": intento, "error": str(ultimo_error)}},
        )
        if intento < intentos:
            time.sleep(espera_base * 2 ** (intento - 1))
    raise RuntimeError(f"No se pudo descargar el feed: {ultimo_error}")


def limpiar_titular(titulo: str, medio: str | None) -> str:
    """Google News termina los títulos en ' - Medio'; eso ya va en el campo medio."""
    titulo = titulo.strip()
    if medio and titulo.endswith(f" - {medio}"):
        return titulo[: -len(f" - {medio}")].strip()
    return titulo


def entrada_a_registro(entrada, run_id: str, ahora: datetime) -> RegistroMencion | None:
    """Convierte una entrada del RSS; devuelve None si no cumple el contrato."""
    enlace = (entrada.get("link") or "").strip()
    fecha = entrada.get("published_parsed")
    if not enlace or not fecha:
        return None
    medio = (entrada.get("source") or {}).get("title") or None
    try:
        return RegistroMencion(
            fuente=Fuente.NEWS,
            id_original=enlace,
            texto=limpiar_titular(entrada.get("title") or "", medio),
            fecha_publicacion=datetime(*fecha[:6], tzinfo=UTC),
            medio=medio,
            url=enlace,
            fecha_extraccion=ahora,
            run_id=run_id,
            version_scraper=VERSION_SCRAPER,
        )
    except ValidationError:
        return None


def extraer_nuevos(contenido: bytes, vistos: dict[str, str], run_id: str, ahora: datetime):
    """Devuelve (nuevos, descartados, total). Deduplica contra el estado y dentro del feed."""
    feed = feedparser.parse(contenido)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"El feed no se pudo interpretar: {feed.bozo_exception}")
    if not getattr(feed, "version", ""):
        raise RuntimeError("La respuesta no es un feed RSS")

    nuevos: list[RegistroMencion] = []
    en_esta_corrida: set[str] = set()
    descartados = 0
    for entrada in feed.entries:
        registro = entrada_a_registro(entrada, run_id, ahora)
        if registro is None:
            descartados += 1
            continue
        if registro.id_original in vistos or registro.id_original in en_esta_corrida:
            continue
        en_esta_corrida.add(registro.id_original)
        nuevos.append(registro)
    return nuevos, descartados, len(feed.entries)


def actualizar_estado(vistos: dict[str, str], nuevos: list[RegistroMencion]) -> dict[str, str]:
    """Agrega los enlaces nuevos. No olvida ninguno: el RSS también devuelve noticias de hace meses."""
    return {**vistos, **{registro.id_original: registro.fecha_publicacion.isoformat() for registro in nuevos}}


def correr(url: str, almacen, run_id: str, dry_run: bool = False, guardar=guardar_registros) -> dict:
    ahora = datetime.now(UTC).replace(microsecond=0)
    log.info("Inicio de corrida", extra={"run_id": run_id, "extra_datos": {"dry_run": dry_run}})
    contenido = descargar_feed(url, run_id)
    crudo = None if dry_run else almacen.leer(RUTA_ESTADO)
    vistos = json.loads(crudo) if crudo else {}
    nuevos, descartados, total = extraer_nuevos(contenido, vistos, run_id, ahora)

    ruta = None
    if nuevos and not dry_run:
        # Primero los datos y luego el estado: si algo falla entre los dos pasos, la
        # siguiente corrida repite noticias (las elimina P2.3) pero nunca pierde ninguna.
        ruta = guardar(nuevos, run_id=run_id)
        estado = actualizar_estado(vistos, nuevos)
        almacen.escribir(RUTA_ESTADO, json.dumps(estado, ensure_ascii=False).encode("utf-8"))

    resumen = {
        "items_en_feed": total,
        "registros_extraidos": len(nuevos),
        "ya_vistos": total - len(nuevos) - descartados,
        "descartados": descartados,
        "ruta": ruta,
    }
    log.info("Fin de corrida", extra={"run_id": run_id, "extra_datos": resumen})
    if dry_run:
        for registro in nuevos[:5]:
            print(f"  {registro.fecha_publicacion:%Y-%m-%d} | {registro.medio} | {registro.texto}")
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="lee el RSS y muestra ejemplos sin guardar nada")
    args = parser.parse_args()

    load_dotenv()
    configurar_logs()
    run_id = os.getenv("RUN_ID") or nuevo_run_id()
    try:
        almacen = None if args.dry_run else crear_almacen_estado()
        correr(construir_url(), almacen, run_id, dry_run=args.dry_run)
    except Exception as error:  # noqa: BLE001 - toda falla debe quedar en el log con run_id
        log.error("Corrida fallida", extra={"run_id": run_id, "extra_datos": {"error": str(error)}})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
