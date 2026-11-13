"""Descarga el modelo de sentimiento FIJADO en una revisión y lo deja en la caché de la imagen.

Se ejecuta una sola vez, al construir la imagen (ver Dockerfile). Después el contenedor corre
sin red (HF_HUB_OFFLINE=1) y siempre usa exactamente esta revisión.
"""

import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODELO = "pysentimiento/robertuito-sentiment-analysis"

# El repositorio trae los pesos en tres formatos de 416 MB cada uno (safetensors, pytorch_model.bin
# y tf_model.h5). PyTorch usa solo uno, así que bajamos únicamente lo necesario para cargar el modelo.
ARCHIVOS = [
    "config.json",
    "model.safetensors",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
]


def main() -> None:
    revision = os.environ.get("NLP_MODEL_REVISION", "").strip()
    if not revision:
        sys.exit("Falta NLP_MODEL_REVISION (hash del commit del modelo). Ver src/transform/nlp/README.md")
    ruta = Path(snapshot_download(MODELO, revision=revision, allow_patterns=ARCHIVOS))
    # pysentimiento pide el modelo por nombre (rama "main"). Apuntamos "main" a la revisión
    # fijada para que, sin red, cargue exactamente esa versión.
    refs = ruta.parent.parent / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "main").write_text(ruta.name)
    print(f"Modelo {MODELO} fijado en {ruta.name}")


if __name__ == "__main__":
    main()
