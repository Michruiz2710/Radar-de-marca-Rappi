"""Crea la hoja para etiquetar 200 reseñas reales de Google Play (paquete P1.5).

Toma las reseñas del CSV que Katalina viene guardando desde la Fase 0, o las
descarga directamente si no se indica un CSV, y selecciona 40 por cada estrella.

    python data/etiquetas/preparar_muestra.py --desde-csv resenas_katalina.csv
    python data/etiquetas/preparar_muestra.py
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections import defaultdict
from pathlib import Path

from etiquetas_comun import COLUMNAS, ETIQUETADORES, SENTIMIENTOS, TEMAS, enmascarar
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

APP_ID = "com.grability.rappi"
CARPETA = Path(__file__).parent
SEMILLA = 2026
POR_ESTRELLA = 40
MIN_PALABRAS = 4

# Los nombres posibles de cada columna en el CSV de origen.
ALIAS = {
    "id_original": ["id_original", "reviewId"],
    "texto": ["texto", "content"],
    "calificacion": ["calificacion", "score"],
    "fecha_publicacion": ["fecha_publicacion", "at"],
}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")  # Excel no los admite


def normalizar(fila: dict) -> dict | None:
    salida = {}
    for campo, nombres in ALIAS.items():
        nombre = next((n for n in nombres if n in fila), None)
        if nombre is None:
            raise SystemExit(f"Al CSV le falta la columna '{campo}' (acepto: {', '.join(nombres)})")
        salida[campo] = str(fila[nombre] or "").strip()
    try:
        salida["calificacion"] = int(float(salida["calificacion"]))
    except ValueError:
        return None
    texto = " ".join(_CONTROL.sub(" ", salida["texto"]).split())
    if len(texto.split()) < MIN_PALABRAS or salida["calificacion"] not in range(1, 6):
        return None
    if not salida["id_original"] or not salida["fecha_publicacion"]:
        return None
    return {
        "id_registro": f"google_play:{salida['id_original']}",
        "texto": enmascarar(texto),
        "calificacion": salida["calificacion"],
        "fecha_publicacion": salida["fecha_publicacion"],
    }


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def descargar(cantidad: int = 2000) -> list[dict]:
    from google_play_scraper import Sort, reviews

    resenas, _ = reviews(APP_ID, lang="es", country="co", sort=Sort.NEWEST, count=cantidad)
    if not resenas:
        raise SystemExit("Google Play no devolvió reseñas. Revisa la conexión o usa --desde-csv.")
    return [{"reviewId": r["reviewId"], "content": r["content"], "score": r["score"], "at": r["at"].isoformat()} for r in resenas]


def seleccionar(filas: list[dict], por_estrella: int = POR_ESTRELLA, semilla: int = SEMILLA) -> list[dict]:
    """Selecciona por estrella; si una se queda corta, completa con las más disponibles."""
    grupos: dict[int, list[dict]] = defaultdict(list)
    vistos: set[str] = set()
    for fila in filas:
        registro = normalizar(fila)
        if registro and registro["id_registro"] not in vistos and registro["texto"].lower() not in vistos:
            vistos.update({registro["id_registro"], registro["texto"].lower()})
            grupos[registro["calificacion"]].append(registro)

    azar = random.Random(semilla)
    for grupo in grupos.values():
        grupo.sort(key=lambda r: r["id_registro"])
        azar.shuffle(grupo)

    meta = por_estrella * 5
    muestra: list[dict] = []
    for estrella in range(1, 6):
        muestra += grupos[estrella][:por_estrella]
        grupos[estrella] = grupos[estrella][por_estrella:]
    sobrantes = sorted((r for g in grupos.values() for r in g), key=lambda r: r["id_registro"])
    azar.shuffle(sobrantes)
    muestra += sobrantes[: meta - len(muestra)]
    if len(muestra) < meta:
        raise SystemExit(f"Solo hay {len(muestra)} reseñas útiles; se necesitan {meta}.")
    azar.shuffle(muestra)
    return muestra


def escribir_hoja(muestra: list[dict], destino: Path) -> None:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "etiquetas"
    hoja.append(COLUMNAS)
    for registro in muestra:
        hoja.append([registro.get(c, "") for c in COLUMNAS])

    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="333333")
    for columna, ancho in zip("ABCDEFG", (14, 80, 11, 20, 13, 17, 15), strict=True):
        hoja.column_dimensions[columna].width = ancho
    for fila in hoja.iter_rows(min_row=2, min_col=2, max_col=2):
        fila[0].alignment = Alignment(wrap_text=True, vertical="top")
        fila[0].data_type = "s"  # una reseña que empiece por "=" no debe ser fórmula
    hoja.freeze_panes = "A2"

    ultima = len(muestra) + 1
    for columna, opciones in (("E", SENTIMIENTOS), ("F", TEMAS), ("G", ETIQUETADORES)):
        lista = DataValidation(type="list", formula1=f'"{",".join(opciones)}"', allow_blank=True, showErrorMessage=True)
        lista.error = "Elige un valor de la lista"
        hoja.add_data_validation(lista)
        lista.add(f"{columna}2:{columna}{ultima}")
    libro.save(destino)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde-csv", type=Path, help="CSV de reseñas ya recolectadas")
    parser.add_argument("--salida", type=Path, default=CARPETA / "muestra_200_para_etiquetar.xlsx")
    args = parser.parse_args()

    filas = leer_csv(args.desde_csv) if args.desde_csv else descargar()
    muestra = seleccionar(filas)
    escribir_hoja(muestra, args.salida)
    conteo = {e: sum(r["calificacion"] == e for r in muestra) for e in range(1, 6)}
    print(f"Hoja creada: {args.salida} | filas: {len(muestra)} | por estrella: {conteo}")


if __name__ == "__main__":
    main()
