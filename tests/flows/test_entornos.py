import pytest

from flows import entornos


def test_intervalos_propuestos():
    for nombre in ("dev", "staging", "prod"):
        assert entornos.ENTORNOS[nombre].intervalos_horas == {"google_play": 3, "youtube": 6, "news": 2}


def test_tres_reintentos_con_espera_creciente():
    assert entornos.esperas(entornos.ENTORNOS["prod"]) == [60, 120, 240]
    assert entornos.esperas(entornos.ENTORNOS["dev"]) == [10, 20, 40]


def test_entorno_desde_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "Staging")
    assert entornos.entorno_actual().nombre == "staging"
    monkeypatch.delenv("APP_ENV")
    assert entornos.entorno_actual().nombre == "dev"


def test_entorno_desconocido(monkeypatch):
    monkeypatch.setenv("APP_ENV", "qa")
    with pytest.raises(ValueError, match="APP_ENV desconocido"):
        entornos.entorno_actual()
