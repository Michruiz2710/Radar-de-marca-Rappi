"""Cada regla de alerta debe apuntar a un runbook que exista (P3.2)."""

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = RAIZ / "infra" / "grafana" / "provisioning" / "alerting" / "reglas.yml"


def _reglas() -> list[dict]:
    documento = yaml.safe_load(REGLAS.read_text(encoding="utf-8"))
    return [regla for grupo in documento["groups"] for regla in grupo["rules"]]


def test_hay_siete_reglas_de_a1_a_a7():
    assert sorted(r["labels"]["alerta"] for r in _reglas()) == [f"A{i}" for i in range(1, 8)]


def test_cada_regla_apunta_a_un_runbook_que_existe():
    for regla in _reglas():
        runbook = RAIZ / regla["annotations"]["runbook"]
        assert runbook.is_file(), f"{regla['title']}: falta {runbook}"
        assert runbook.name.startswith(regla["labels"]["alerta"] + "_")


def test_el_indice_de_runbooks_los_enlaza_todos():
    indice = (RAIZ / "docs" / "runbooks" / "README.md").read_text(encoding="utf-8")
    enlazados = set(re.findall(r"\]\((A\d_[^)]+\.md)\)", indice))
    existentes = {p.name for p in (RAIZ / "docs" / "runbooks").glob("A[0-9]_*.md")}
    assert enlazados == existentes


def test_los_runbooks_enlazados_entre_si_existen():
    carpeta = RAIZ / "docs" / "runbooks"
    for archivo in carpeta.glob("*.md"):
        for destino in re.findall(r"\]\(([^)#:]+\.md)\)", archivo.read_text(encoding="utf-8")):
            assert (carpeta / destino).is_file(), f"{archivo.name} enlaza a {destino}, que no existe"


def test_las_reglas_son_p0_o_p1_con_su_correspondiente_prioridad():
    esperadas = {"A1": "P0", "A2": "P0", "A3": "P0", "A4": "P0", "A5": "P1", "A6": "P1", "A7": "P1"}
    assert {r["labels"]["alerta"]: r["labels"]["severidad"] for r in _reglas()} == esperadas
