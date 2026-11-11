"""Limpieza y filtrado de bots (P2.3): de la capa raw (MinIO) a la tabla clean.menciones (Postgres).

El orquestador (P2.1) llama a `limpiar(rutas)` después de la validación cruda,
con los archivos que se guardaron en esa corrida:

    limpiar({"google_play": "s3://radar-rappi/raw/...jsonl", "youtube": None, "news": "s3://..."})

Para cargar todo lo que ya existe en la capa raw (carga histórica):

    python -m src.transform.clean.limpieza            # todas las fuentes
    python -m src.transform.clean.limpieza --fuente youtube

Pasos, en orden:
1. Leer los archivos de la capa raw.
2. Descartar filas sin los campos mínimos (id, texto, fecha) y registrarlas en el log.
3. Quitar duplicados por id_registro: queda la versión más reciente.
4. Normalizar el texto y enmascarar datos personales (correos, teléfonos, números largos).
5. Detectar el idioma real de cada texto.
6. Marcar bots (sin borrarlos).
7. Cargar en clean.menciones sin duplicar (insertar o actualizar).
"""

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import Engine

from src.common.db import crear_motor, esquema_clean
from src.common.storage import leer_registros, listar_rutas
from src.transform.clean import tabla
from src.transform.clean.bots import marcar_bots
from src.transform.clean.texto import (
    clave_comparacion,
    contar_urls,
    detectar_idioma,
    esta_vacio,
    limpiar_texto,
)

# Subirla cuando cambie una regla: así la carga actualiza las filas ya limpiadas.
VERSION_LIMPIEZA = "1.2.0"

log = logging.getLogger("limpieza")


def _fecha(valor) -> datetime | None:
    """Convierte una fecha ISO 8601 ('2026-11-07T18:56:50Z') en datetime UTC."""
    if valor in (None, ""):
        return None
    fecha = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    return fecha.replace(tzinfo=timezone.utc) if fecha.tzinfo is None else fecha.astimezone(timezone.utc)


def _preparar(cruda: dict) -> dict:
    """Pasa una fila de la capa raw al formato de clean.menciones (sin bots ni idioma aún).

    Lanza ValueError si faltan los campos mínimos.
    """
    fuente = cruda.get("fuente")
    id_original = cruda.get("id_original")
    texto = cruda.get("texto")
    fecha_publicacion = _fecha(cruda.get("fecha_publicacion"))
    if not fuente or not id_original or not texto or fecha_publicacion is None:
        raise ValueError("faltan fuente, id_original, texto o fecha_publicacion")

    fecha_respuesta = _fecha(cruda.get("fecha_respuesta"))
    # Se recalculan aquí porque los archivos anteriores al contrato v1.2.0 no los traen
    editada = None if fecha_respuesta is None else fecha_publicacion > fecha_respuesta
    texto_limpio = limpiar_texto(texto)
    # Un texto con solo espacios o caracteres invisibles queda vacío al limpiarlo:
    # rompería la regla "texto no vacío" (P2.2) y el modelo de sentimiento (P2.4)
    if esta_vacio(texto_limpio):
        raise ValueError("el texto queda vacío después de limpiarlo")
    respuesta = limpiar_texto(cruda.get("respuesta_marca")) or None

    return {
        "id_registro": cruda.get("id_registro") or f"{fuente}:{id_original}",
        "fuente": fuente,
        "id_original": str(id_original),
        "texto_limpio": texto_limpio,
        "hash_texto": hashlib.sha256(texto_limpio.encode("utf-8")).hexdigest(),
        "idioma_consulta": (cruda.get("idioma") or "es").lower(),
        "pais": (cruda.get("pais") or "co").lower(),
        "fecha_publicacion": fecha_publicacion,
        "fecha_extraccion": _fecha(cruda.get("fecha_extraccion")) or fecha_publicacion,
        "autor_hash": cruda.get("autor_hash"),
        "calificacion": cruda.get("calificacion"),
        "likes": cruda.get("likes"),
        "version_app": cruda.get("version_app"),
        "respuesta_marca": respuesta,
        "fecha_respuesta": fecha_respuesta,
        "editada_tras_respuesta": editada,
        "fecha_edicion": fecha_publicacion if editada else None,
        "id_contenedor": cruda.get("id_contenedor"),
        "url": cruda.get("url"),
        "medio": cruda.get("medio"),
        "run_id": cruda.get("run_id") or "desconocido",
        "version_scraper": cruda.get("version_scraper"),
        "version_contrato": cruda.get("version_contrato"),
        # Solo para las reglas de bots; no se guardan
        "_n_urls": contar_urls(texto),
        "_texto_original": texto,
    }


def _mas_reciente(a: dict, b: dict) -> dict:
    """De dos versiones del mismo registro, la más reciente (reseña editada o extracción posterior)."""
    return max(a, b, key=lambda f: (f["fecha_publicacion"], f["fecha_extraccion"]))


def transformar(crudas: list[dict]) -> tuple[list[dict], dict]:
    """Pasos 2 a 6: de filas raw a filas listas para clean.menciones.

    Es una función pura (no lee ni escribe), así se prueba sin MinIO ni Postgres.
    Devuelve las filas y un resumen con los conteos.
    """
    resumen = {"leidos": len(crudas), "descartados": 0, "duplicados": 0, "bots": 0, "idiomas": {}}
    procesado_en = datetime.now(timezone.utc)

    unicas: dict[str, dict] = {}
    for cruda in crudas:
        try:
            fila = _preparar(cruda)
        except (ValueError, TypeError) as error:
            resumen["descartados"] += 1
            log.warning("Fila descartada (%s): %s", error, cruda.get("id_registro") or cruda.get("id_original"))
            continue
        anterior = unicas.get(fila["id_registro"])
        if anterior is not None:
            resumen["duplicados"] += 1
            fila = _mas_reciente(anterior, fila)
        unicas[fila["id_registro"]] = fila

    filas = list(unicas.values())
    for fila in filas:
        fila["idioma_detectado"] = detectar_idioma(fila["texto_limpio"], fila["idioma_consulta"])
        resumen["idiomas"][fila["idioma_detectado"]] = resumen["idiomas"].get(fila["idioma_detectado"], 0) + 1

    motivos = marcar_bots(
        [
            {
                "id_registro": f["id_registro"],
                "fuente": f["fuente"],
                "autor_hash": f["autor_hash"],
                "clave": clave_comparacion(f["texto_limpio"]),
                "n_urls": f["_n_urls"],
                "texto_limpio": f["texto_limpio"],
                "texto_original": f["_texto_original"],
                "fecha_publicacion": f["fecha_publicacion"],
                "id_contenedor": f["id_contenedor"],
            }
            for f in filas
        ]
    )
    for fila in filas:
        fila["es_bot"] = fila["id_registro"] in motivos
        fila["motivo_bot"] = ",".join(motivos.get(fila["id_registro"], [])) or None
        fila["version_limpieza"] = VERSION_LIMPIEZA
        fila["procesado_en"] = procesado_en
        del fila["_n_urls"], fila["_texto_original"]
    resumen.update(_porcentaje_bots(filas))
    return filas, resumen


def _porcentaje_bots(filas: list[dict]) -> dict:
    """Bots en total y por fuente, en cantidad y en porcentaje de las filas limpias.

    `pct_bots` alimenta la métrica registros_bot_ratio de la observabilidad (P3.1).
    """
    por_fuente: dict[str, list[int]] = {}
    for fila in filas:
        total, bots = por_fuente.setdefault(fila["fuente"], [0, 0])
        por_fuente[fila["fuente"]] = [total + 1, bots + int(fila["es_bot"])]
    total_bots = sum(bots for _, bots in por_fuente.values())

    def pct(bots: int, total: int) -> float:
        return round(100 * bots / total, 2) if total else 0.0

    return {
        "bots": total_bots,
        "pct_bots": pct(total_bots, len(filas)),
        "bots_por_fuente": {f: bots for f, (_, bots) in sorted(por_fuente.items())},
        "pct_bots_por_fuente": {f: pct(bots, total) for f, (total, bots) in sorted(por_fuente.items())},
    }


def limpiar_rutas(rutas: list[str], motor: Engine | None = None, esquema: str | None = None, cliente=None) -> dict:
    """Pasos 1 a 7 para una lista de archivos de la capa raw. Devuelve el resumen."""
    rutas = [r for r in rutas if r]
    if not rutas:
        log.info("Limpieza: no hay archivos nuevos")
        return {"archivos": 0, "leidos": 0}

    crudas = [fila for ruta in rutas for fila in leer_registros(ruta, cliente=cliente)]
    filas, resumen = transformar(crudas)

    motor = motor or crear_motor()
    esquema = esquema or esquema_clean()
    with motor.begin() as conexion:
        tabla.crear_tabla(conexion, esquema)
        resumen.update(tabla.cargar(conexion, esquema, filas))

    resumen["archivos"] = len(rutas)
    log.info("Limpieza terminada: %s", json.dumps(resumen, ensure_ascii=False))
    return resumen


def limpiar(rutas: dict[str, str | None], motor: Engine | None = None, esquema: str | None = None, cliente=None) -> dict:
    """Etapa del orquestador (P2.1): recibe {fuente: ruta} de la corrida y carga clean.menciones.

    Las fuentes sin datos nuevos llegan con ruta None y se ignoran.
    Si algo falla (MinIO o Postgres caídos), lanza la excepción y el
    orquestador reintenta la etapa.
    """
    return limpiar_rutas(list(rutas.values()), motor=motor, esquema=esquema, cliente=cliente)


def main(argv: list[str] | None = None) -> dict:
    """Carga histórica: limpia todos los archivos de la capa raw (o los de una fuente)."""
    parser = argparse.ArgumentParser(description="Carga la capa raw completa en clean.menciones")
    parser.add_argument("--fuente", choices=["google_play", "youtube", "news"], help="solo esta fuente")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from dotenv import load_dotenv

    load_dotenv()
    rutas = listar_rutas(args.fuente)
    log.info("Archivos encontrados en la capa raw: %d", len(rutas))
    return limpiar_rutas(rutas)


if __name__ == "__main__":
    main()
