"""Las reglas que miran ventanas largas deben esperar a tener historia (P3.2).

Sin esa guarda, un entorno recién levantado da falsas alarmas: con pocos minutos de datos,
`increase(...[6h])` vale 0 aunque todo funcione.
"""

from pathlib import Path

import yaml

REGLAS = Path(__file__).resolve().parents[2] / "infra" / "grafana" / "provisioning" / "alerting" / "reglas.yml"


def _expresion(uid: str) -> str:
    documento = yaml.safe_load(REGLAS.read_text(encoding="utf-8"))
    regla = next(r for g in documento["groups"] for r in g["rules"] if r["uid"] == uid)
    return next(d["model"]["expr"] for d in regla["data"] if d["refId"] == "A")


def test_a2_espera_6_horas_de_historia():
    expresion = _expresion("a2-google-play")
    assert "[6h]" in expresion
    # La misma ventana de la consulta, como desplazamiento de la guarda
    assert 'count(registros_extraidos_total{fuente="google_play"} offset 6h) > 0' in expresion
    assert "and on()" in expresion


def test_a6_espera_7_dias_de_historia():
    expresion = _expresion("a6-menciones")
    assert "[7d]" in expresion
    assert "offset 7d" in expresion
    assert "and on()" in expresion
