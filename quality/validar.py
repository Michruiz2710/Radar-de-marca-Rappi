"""Comando de validación que corre el CI en cada Pull Request.
    Comprueba que:
    Los datos de prueba correctos pasan 
    Los datos de prueba incorrectos fallan.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from quality.checkpoints import validar_tabla
from quality.reglas import fuentes_permitidas
from quality.suites import preparar_tabla, suite_raw
from src.common.storage import leer_registros, listar_rutas

datos_prueba = Path(__file__).parent / "datos_prueba"


def _criticas(ruta: str, fuente: str) -> list[dict]:
    resumen = validar_tabla(preparar_tabla(leer_registros(ruta)), suite_raw(fuente))
    return resumen["criticas"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validaciones de calidad de la capa raw")
    parser.add_argument("--raw", action="store_true", help="validar los archivos reales de la capa raw")
    args = parser.parse_args(argv)
    problemas = 0

    for ruta in sorted((datos_prueba / "correctos").glob("*.jsonl")):
        criticas = _criticas(str(ruta), ruta.stem)
        print(f"{'Ok   ' if not criticas else 'Error'} correcto   {ruta.name}: {len(criticas)} críticas")
        problemas += bool(criticas)

    for ruta in sorted((datos_prueba / "incorrectos").glob("*.jsonl")):
        criticas = _criticas(str(ruta), ruta.stem.split("__")[0])
        print(f"{'Ok   ' if criticas else 'Error'} incorrecto {ruta.name}: {len(criticas)} críticas")
        problemas += not criticas

    if args.raw:
        load_dotenv() 
        for fuente in fuentes_permitidas:
            for ruta in listar_rutas(fuente):
                criticas = _criticas(ruta, fuente)
                print(f"{'Ok   ' if not criticas else 'Error'} raw        {ruta}: {len(criticas)} críticas")
                problemas += bool(criticas)

    print(f"\n{'Validaciones Ok' if not problemas else f'{problemas} archivo(s) con problemas'}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())