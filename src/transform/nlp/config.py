"""Configuración del módulo de sentimiento y temas (P2.4).

Lo que cambia por entorno se lee de variables de entorno (ver .env.example y el servicio
`nlp` de infra/docker-compose.yml). Lo que forma parte de la lógica vive aquí como constante.
"""

from __future__ import annotations

import os
from importlib import metadata

# Modelo de sentimiento en español (RoBERTuito). pysentimiento lo descarga con este nombre.
MODELO = "pysentimiento/robertuito-sentiment-analysis"

# Versión del código de este módulo. Súbela si cambia el diccionario de temas o la lógica.
VERSION_NLP = "0.1.0"

TAMANO_LOTE_POR_DEFECTO = 32


def tamano_lote() -> int:
    """Textos por lote que se envían al modelo (NLP_BATCH_SIZE)."""
    try:
        valor = int(os.getenv("NLP_BATCH_SIZE", str(TAMANO_LOTE_POR_DEFECTO)))
    except ValueError:
        return TAMANO_LOTE_POR_DEFECTO
    return valor if valor > 0 else TAMANO_LOTE_POR_DEFECTO


def version_modelo() -> str:
    """Texto que se guarda junto a cada resultado: modelo, revisión y versión de la librería.

    La revisión (hash del commit en Hugging Face) la fija el Dockerfile al construir la imagen
    y llega por NLP_MODEL_REVISION, así lo guardado coincide con el modelo que realmente corrió.
    """
    revision = os.getenv("NLP_MODEL_REVISION", "").strip() or "sin-revision"
    try:
        libreria = metadata.version("pysentimiento")
    except metadata.PackageNotFoundError:
        libreria = "no-instalada"
    return f"{MODELO}@{revision}|pysentimiento=={libreria}"
