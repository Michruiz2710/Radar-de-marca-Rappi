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


@pytest.fixture(autouse=True)
def etapas_aisladas(monkeypatch):
    # Estas pruebas verifican la orquestación, no las etapas de otros paquetes
    # (limpieza, validaciones, sentimiento), que tienen sus propias pruebas y
    # necesitan MinIO y Postgres. Aquí apuntan a módulos que no existen, así
    # quedan "pendientes"; las pruebas que necesitan una etapa la reemplazan.
    from flows import pipeline

    aisladas = tuple(
        pipeline.Etapa(e.nombre, f"etapa_inexistente_{e.nombre}:funcion", e.paquete) for e in pipeline.ETAPAS
    )
    monkeypatch.setattr(pipeline, "ETAPAS", aisladas)
