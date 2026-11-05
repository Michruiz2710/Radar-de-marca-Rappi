"""Revisa las etiquetas y genera muestra_200.csv, el archivo que va en el PR (P1.5).

    python data/etiquetas/validar_muestra.py muestra_200_para_etiquetar.xlsx
    python data/etiquetas/validar_muestra.py muestra_200.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from etiquetas_comun import COLUMNAS, SENTIMIENTOS, TEMAS, tiene_dato_personal

FILAS_ESPERADAS = 200


def _celda(valor) -> str:
    """Google Sheets exporta los enteros como 3.0; aqui vuelven a ser 3."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def leer(ruta: Path) -> list[dict]:
    if ruta.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        hoja = load_workbook(ruta, read_only=True, data_only=True).worksheets[0]
        filas = list(hoja.iter_rows(values_only=True))
        encabezado = [str(c) if c is not None else "" for c in filas[0]]
        datos = [f for f in filas[1:] if any(c not in (None, "") for c in f)]
        return [{k: _celda(v) for k, v in zip(encabezado, f, strict=False)} for f in datos]
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def validar(filas: list[dict]) -> list[str]:
    errores: list[str] = []
    if len(filas) != FILAS_ESPERADAS:
        errores.append(f"Hay {len(filas)} filas; deben ser {FILAS_ESPERADAS}")
    if filas and set(filas[0]) != set(COLUMNAS):
        return errores + [f"Columnas incorrectas: se esperan {COLUMNAS}"]

    repetidos = [i for i, n in Counter(f["id_registro"] for f in filas).items() if n > 1]
    if repetidos:
        errores.append(f"id_registro repetidos: {repetidos[:5]}")

    for numero, fila in enumerate(filas, start=2):
        vacios = [c for c in COLUMNAS if not str(fila.get(c) or "").strip()]
        if vacios:
            errores.append(f"Fila {numero}: campos vacíos {vacios}")
        if not str(fila["id_registro"]).startswith("google_play:"):
            errores.append(f"Fila {numero}: id_registro debe empezar por google_play:")
        if fila["calificacion"] and fila["calificacion"] not in {"1", "2", "3", "4", "5"}:
            errores.append(f"Fila {numero}: calificacion inválida '{fila['calificacion']}'")
        if fila["sentimiento"] and fila["sentimiento"] not in SENTIMIENTOS:
            errores.append(f"Fila {numero}: sentimiento inválido '{fila['sentimiento']}'")
        if fila["tema"] and fila["tema"] not in TEMAS:
            errores.append(f"Fila {numero}: tema inválido '{fila['tema']}'")
        if tiene_dato_personal(fila["texto"]):
            errores.append(f"Fila {numero}: el texto parece tener un correo o teléfono")
    return errores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", type=Path)
    parser.add_argument("--salida", type=Path, default=Path(__file__).parent / "muestra_200.csv")
    args = parser.parse_args()

    filas = leer(args.entrada)
    errores = validar(filas)
    if errores:
        print(f"NO PASA: {len(errores)} problemas")
        for error in errores[:30]:
            print(f"  - {error}")
        return 1

    if args.entrada.resolve() != args.salida.resolve():
        with args.salida.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
            escritor.writeheader()
            escritor.writerows(filas)
    print(f"PASA: {len(filas)} filas sin campos vacíos -> {args.salida}")
    print("Sentimiento:", dict(Counter(f["sentimiento"] for f in filas)))
    print("Tema:", dict(Counter(f["tema"] for f in filas)))
    print("Sentimiento vs. estrellas revisar:", sum(
        (f["sentimiento"] == "positivo" and f["calificacion"] in {"1", "2"})
        or (f["sentimiento"] == "negativo" and f["calificacion"] in {"4", "5"})
        for f in filas
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
