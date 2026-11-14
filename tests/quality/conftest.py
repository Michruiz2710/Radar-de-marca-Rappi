import pytest

from quality import checkpoints

@pytest.fixture(autouse=True)
def data_docs_temporales(tmp_path, monkeypatch):
    # Las pruebas generan Data Docs en una carpeta temporal, 
    # y cada prueba arranca con un contexto de GX nuevo.
    monkeypatch.setenv("DATA_DOCS_DIR", str(tmp_path / "data_docs"))
    checkpoints._contexto.cache_clear()
    yield
    checkpoints._contexto.cache_clear()