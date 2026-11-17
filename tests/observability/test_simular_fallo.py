"""El script de simulación de la demo (P3.2) debe tener sintaxis válida y rechazar usos erróneos."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "simular_fallo.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="requiere bash")


def _correr(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, str(SCRIPT), *args], check=False, capture_output=True, text=True, timeout=30)


def test_la_sintaxis_es_valida():
    assert subprocess.run([BASH, "-n", str(SCRIPT)], check=False, capture_output=True).returncode == 0


def test_los_finales_de_linea_son_unix():
    # Con CRLF, bash falla en Linux y en el CI
    assert b"\r\n" not in SCRIPT.read_bytes()


def test_la_ayuda_lista_los_cuatro_modos():
    resultado = _correr("--help")
    assert resultado.returncode == 0
    for modo in ("inyectar", "real", "minio", "restaurar"):
        assert modo in resultado.stdout


def test_sin_argumentos_muestra_el_uso_y_falla():
    assert _correr().returncode == 1


def test_rechaza_una_alerta_que_no_se_puede_inyectar():
    resultado = _correr("inyectar", "A9")
    assert resultado.returncode == 1
    assert "A1, A4 o A7" in resultado.stderr
