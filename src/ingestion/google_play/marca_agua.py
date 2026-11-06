""" Marca de agua: permite recordar cuál fue la reseña más nueva de la corrida anterior"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class MarcaAgua:
    id_original:str
    fecha_publicacion:datetime

def ruta_marca() -> Path:
    # Ruta del archivo de la marca de agua
    return Path(os.getenv("LOCAL_RAW_DIR", "data")) / "estado" / "google_play_marca_agua.json"

def leer_marca(ruta: Path | None = None) -> MarcaAgua | None:
    # Devuelve la marca guardada
    ruta = ruta or ruta_marca()
    if not ruta.exists():
        return None
    
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    
    return MarcaAgua(
        id_original=datos["id_original"],
        fecha_publicacion=datetime.fromisoformat(datos["fecha_publicacion"]),
    )
    
def guardar_marca(marca: MarcaAgua, ruta: Path | None = None) -> None:
    # Escribe la marca y se llama después de guardar las reseñas con éxito
    ruta = ruta or ruta_marca()
    ruta.parent.mkdir(parents = True, exist_ok = True)
    datos = {
        "id_original": marca.id_original,
        "fecha_publicacion": marca.fecha_publicacion.isoformat(),
    }
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")