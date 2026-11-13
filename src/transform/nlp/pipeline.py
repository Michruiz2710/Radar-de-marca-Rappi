"""Sentimiento y tema para los registros limpios (P2.4).

Lee `<esquema clean>.menciones`, analiza solo los registros pendientes y escribe
`<esquema clean>.sentimiento`. Es idempotente: volver a correrlo no repite trabajo, y si
cambia el modelo o el texto de un registro, solo ese registro se vuelve a analizar.

Se analizan solo los registros en español (`idioma_detectado = 'es'`) que no son bots
(`es_bot = false`), como pide el contrato de la capa clean (docs/contrato_clean.md).

Uso desde el orquestador (P2.1):

    from src.transform.nlp.pipeline import correr
    resumen = correr()

Uso desde la terminal:  python -m src.transform.nlp.pipeline
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from src.transform.nlp import config, tabla
from src.transform.nlp.sentimiento import AnalizadorSentimiento
from src.transform.nlp.temas import clasificar_tema

log = logging.getLogger(__name__)

TAMANO_LECTURA = 500  # registros que se leen por vuelta (el modelo los parte en lotes más chicos)


def _motor_por_defecto():
    from src.common.db import crear_motor  # lo define P2.3

    return crear_motor()


def _esquema_por_defecto() -> str:
    from src.common.db import esquema_clean

    return esquema_clean()


def correr(
    motor: Any | None = None,
    analizador: Any | None = None,
    esquema: str | None = None,
    tamano_lectura: int = TAMANO_LECTURA,
) -> dict[str, Any]:
    """Analiza todos los registros pendientes y devuelve un resumen."""
    motor = motor or _motor_por_defecto()
    if esquema is None and motor.dialect.name == "postgresql":
        esquema = _esquema_por_defecto()
    analizador = analizador or AnalizadorSentimiento()
    version = analizador.version

    with motor.begin() as conexion:
        tabla.crear_tabla(conexion, esquema)

    procesados = 0
    por_sentimiento: Counter[str] = Counter()
    por_tema: Counter[str] = Counter()
    vistos: set[str] = set()

    while True:
        with motor.begin() as conexion:
            tabla.con_esquema(conexion, esquema)
            pendientes = tabla.leer_pendientes(conexion, version, tamano_lectura)
            pendientes = [p for p in pendientes if p["id_registro"] not in vistos]
            if not pendientes:
                break
            resultados = analizador.analizar([p["texto_limpio"] for p in pendientes])
            ahora = tabla.ahora_utc()
            filas = []
            for p, r in zip(pendientes, resultados, strict=True):
                tema = clasificar_tema(p["texto_limpio"])
                filas.append(
                    {
                        "id_registro": p["id_registro"],
                        "hash_texto": p["hash_texto"],
                        "sentimiento": r.sentimiento,
                        "prob_sentimiento": r.probabilidad,
                        "prob_positivo": r.prob_positivo,
                        "prob_neutro": r.prob_neutro,
                        "prob_negativo": r.prob_negativo,
                        "tema": tema.tema,
                        "temas_detectados": ",".join(tema.temas_detectados) or None,
                        "version_modelo": version,
                        "version_nlp": config.VERSION_NLP,
                        "procesado_en": ahora,
                    }
                )
                por_sentimiento[r.sentimiento] += 1
                por_tema[tema.tema] += 1
            tabla.guardar(conexion, filas)
            vistos.update(f["id_registro"] for f in filas)
            procesados += len(filas)
            log.info("NLP: %s registros procesados", procesados)

    with motor.begin() as conexion:
        tabla.con_esquema(conexion, esquema)
        cobertura = tabla.cobertura(conexion, version)

    return {
        "procesados": procesados,
        "por_sentimiento": dict(por_sentimiento),
        "por_tema": dict(por_tema),
        "version_modelo": version,
        "version_nlp": config.VERSION_NLP,
        **cobertura,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    resumen = correr()
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if resumen["pendientes"]:
        raise SystemExit(
            f"Quedaron {resumen['pendientes']} registros sin resultado (criterio de P2.4 no cumplido)."
        )


if __name__ == "__main__":
    main()
