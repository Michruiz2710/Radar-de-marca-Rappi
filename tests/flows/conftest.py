import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session")
def prefect_local():
    # Servidor temporal de Prefect solo para las pruebas (no usa el de Docker)
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def entorno_limpio(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_RAW_DIR", str(tmp_path))
    monkeypatch.setenv("PUSHGATEWAY_URL", "")
    # Vacia y no borrada: load_dotenv no reemplaza variables que ya existen
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
