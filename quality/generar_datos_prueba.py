""" Genera los datos de prueba para la capa raw: correctos e 
    incorrectos.
    Se corre una sola vez y los archivos de almacenan en git.
"""

import json

from pathlib import Path

from src.common.schema import RegistroMencion

carpeta = Path(__file__).parent / "datos_prueba"
hash_ejemplo = "3f5a"+"0"*60
fechas = {"fecha_publicacion": "2026-11-02T13:00:00Z", "fecha_extraccion": "2026-11-02T15:00:00Z"}
corrida = {"run_id": "20261102T150000Z-prueba", "version_scraper": "0.1.0"}

def google_play(n:int, **cambios) -> dict:
    datos = {
        "fuente": "google_play",
        "id_original": f"gp-{n}",
        "texto": "El pedido llegó tarde y frío",
        "autor_hash": hash_ejemplo,
        "calificacion": 2,
        "likes": 3,
        "version_app": "9.1.0",
        **fechas,
        **corrida,
    }
    return RegistroMencion(**{**datos, **cambios}).model_dump(mode="json")

def youtube(n:int, **cambios) -> dict:
    datos = {
        "fuente": "youtube",
        "id_original": f"yt-{n}",
        "texto": "Rappi me salvó la cena 🙌",
        "autor_hash": hash_ejemplo,
        "likes": 10,
        "id_contenedor": "video-1",
        "url": "https://www.youtube.com/watch?v=video-1",
        **fechas,
        **corrida, 
    }
    return RegistroMencion(**{**datos, **cambios}).model_dump(mode="json")

def news(n:int, **cambios) -> dict:
    datos = {
        "fuente": "news",
        "id_original": f"news-{n}",
        "texto": "Rappi anuncia nuevas zonas de cobertura en Bogotá",
        "medio": "El Tiempo",
        "url": "https://news.google.com/articles/ejemplo",
        **fechas,
        **corrida,
    }
    return RegistroMencion(**{**datos, **cambios}).model_dump(mode="json")

def _con(registro: dict, **cambios) -> dict:
    """ Copia un buen registro y le aplica alguna modificación que lo afecte"""
    return {**registro, **cambios}

def _sin(registro:dict, columna:str) -> dict:
    return {k: v for k, v in registro.items() if k != columna}

correctos = {
    "google_play": [google_play(1), google_play(2, calificacion = 5, texto = "Excelente servicio")],
    "youtube": [youtube(1), youtube(2, likes = 0)],
    "news": [news(1), news(2, likes = 0)],
}

incorrectos = {
    "google_play__calificacion_fuera_de_rango": [_con(google_play(1), calificacion=9)],
    "google_play__dato_personal_userName": [_con(google_play(1), userName="Ana Pérez")],
    "google_play__id_registro_repetido": [google_play(1), google_play(1)],
    "google_play__fecha_futura": [_con(google_play(1), fecha_publicacion="2030-01-01T00:00:00Z")],
    "youtube__calificacion_prohibida": [_con(youtube(1), calificacion=4)],
    "youtube__autor_hash_invalido": [_con(youtube(1), autor_hash="juan123")],
    "youtube__texto_vacio": [_con(youtube(1), texto="")],
    "news__sin_columna_texto": [_sin(news(1), "texto")],
    "news__fuente_equivocada": [_con(news(1), fuente="youtube")],
    "news__fecha_ilegible": [_con(news(1), fecha_publicacion="ayer")],    
}

def _escribir(ruta:Path, registros: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = [json.dumps(r, ensure_ascii = False) for r in registros]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

def main() -> None:
    for fuente, registros in correctos.items():
        _escribir(carpeta / "correctos" / f"{fuente}.jsonl", registros)
    for nombre, registros in incorrectos.items():
        _escribir(carpeta / "incorrectos" / f"{nombre}.jsonl", registros)
    print(f"{len(correctos)} archivos correctos y {len(incorrectos)} incorrectos en {carpeta}")

if __name__ == "__main__":
    main()