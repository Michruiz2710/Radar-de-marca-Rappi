import pytest

from src.observability import metricas


@pytest.fixture(autouse=True)
def estado_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    monkeypatch.setenv("PUSHGATEWAY_URL", "")
    metricas._tomar_pendiente()  # lo contado por otras pruebas no se cuela
    yield
    metricas._tomar_pendiente()
