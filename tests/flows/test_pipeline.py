import sys
import types

import pytest

from flows import fuentes, pipeline


@pytest.fixture
def sin_esperas(monkeypatch):
    # Reintentos inmediatos para que las pruebas no tarden
    for tarea in ("extraer", "correr_etapa"):
        original = getattr(pipeline, tarea)
        monkeypatch.setattr(pipeline, tarea, original.with_options(retry_delay_seconds=0))


@pytest.fixture
def scrapers_falsos(monkeypatch):
    llamados = []

    def falso(fuente):
        def correr():
            llamados.append(fuente)
            return f"s3://radar-rappi/raw/fuente={fuente}/run.jsonl"
        return correr

    monkeypatch.setattr(fuentes, "SCRAPERS", {f: falso(f) for f in fuentes.SCRAPERS})
    return llamados


def test_corre_una_fuente_y_deja_etapas_pendientes(prefect_local, scrapers_falsos):
    resumen = pipeline.pipeline(fuentes=["news"])
    assert scrapers_falsos == ["news"]
    assert resumen["rutas"] == {"news": "s3://radar-rappi/raw/fuente=news/run.jsonl"}
    assert set(resumen["etapas"].values()) == {pipeline.PENDIENTE}


def test_sin_fuentes_corre_todas(prefect_local, scrapers_falsos):
    pipeline.pipeline()
    assert scrapers_falsos == ["google_play", "youtube", "news"]


def test_youtube_sin_api_key_se_omite(prefect_local, monkeypatch):
    monkeypatch.setattr(fuentes, "SCRAPERS", {**fuentes.SCRAPERS, "youtube": fuentes.correr_youtube})
    assert pipeline.pipeline(fuentes=["youtube"])["rutas"] == {"youtube": None}


def test_reintenta_tres_veces(prefect_local, sin_esperas, monkeypatch):
    intentos = []

    def inestable():
        intentos.append(1)
        if len(intentos) < 3:
            raise ConnectionError("caída temporal")
        return "s3://ok"

    monkeypatch.setattr(fuentes, "SCRAPERS", {"news": inestable})
    assert pipeline.pipeline(fuentes=["news"])["rutas"] == {"news": "s3://ok"}
    assert len(intentos) == 3


def test_falla_definitiva_activa_el_gancho(prefect_local, sin_esperas, monkeypatch):
    def siempre_falla():
        raise ConnectionError("Google caído")

    monkeypatch.setattr(fuentes, "SCRAPERS", {"news": siempre_falla})
    pipeline.pipeline(fuentes=["news"], return_state=True)
    from flows import metricas

    assert metricas._leer_fallas() == {"pipeline:news": 1}


def test_etapa_existente_recibe_las_rutas(prefect_local, scrapers_falsos, monkeypatch):
    recibido = {}
    modulo = types.ModuleType("limpieza_falsa")
    modulo.limpiar = lambda rutas: recibido.update(rutas)
    monkeypatch.setitem(sys.modules, "limpieza_falsa", modulo)
    monkeypatch.setattr(pipeline, "ETAPAS", (pipeline.Etapa("limpieza", "limpieza_falsa:limpiar", "P2.3"),))
    resumen = pipeline.pipeline(fuentes=["news"])
    assert resumen["etapas"] == {"limpieza": "ok"} and "news" in recibido


def test_validacion_critica_detiene_el_flujo(prefect_local, sin_esperas, scrapers_falsos, monkeypatch):
    modulo = types.ModuleType("calidad_falsa")

    def validar(rutas):
        raise ValueError("regla crítica: texto vacío")

    modulo.validar = validar
    monkeypatch.setitem(sys.modules, "calidad_falsa", modulo)
    monkeypatch.setattr(pipeline, "ETAPAS", (pipeline.Etapa("validacion_cruda", "calidad_falsa:validar", "P2.2"),))
    assert pipeline.pipeline(fuentes=["news"], return_state=True).is_failed()


def test_fuente_desconocida(prefect_local):
    assert pipeline.pipeline(fuentes=["twitter"], return_state=True).is_failed()


def test_resolver_distingue_pendiente_de_error():
    assert pipeline.resolver("paquete_inexistente.modulo:funcion") is None
    assert pipeline.resolver("flows.pipeline:no_existe") is None
    assert pipeline.resolver("flows.pipeline:resolver") is pipeline.resolver
