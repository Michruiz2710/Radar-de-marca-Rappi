import asyncio
import io
import sys
import types

import pytest

from flows import fuentes, pipeline

# Antes de que conftest las reemplace por módulos inexistentes
ETAPAS_REALES = pipeline.ETAPAS


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
    from src.observability import metricas

    assert metricas._leer()["flujos"]["pipeline:news"]["fallas"] == 1


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


def test_todas_las_etapas_reales_existen():
    # Si alguna se renombra, la etapa quedaría "pendiente" sin avisar (pasó con sentimiento)
    for etapa in ETAPAS_REALES:
        assert pipeline.resolver(etapa.destino) is not None, etapa.destino


def _todos_los_logs() -> list[str]:
    from prefect.client.orchestration import get_client

    async def leer():
        mensajes, desplazamiento = [], 0
        async with get_client() as cliente:
            while lote := await cliente.read_logs(limit=200, offset=desplazamiento):
                mensajes += [registro.message for registro in lote]
                desplazamiento += len(lote)
        return mensajes

    return asyncio.run(leer())


def test_los_print_de_una_etapa_no_van_a_los_logs_de_prefect(prefect_local, scrapers_falsos, monkeypatch):
    # dill.detect.nestedglobals captura stdout y llama dis.dis: con log_prints=True, Prefect 3.8 manda ese
    # volcado a los logs en vez de al buffer de dill (miles de líneas por lote en la etapa de sentimiento)
    modulo = types.ModuleType("etapa_con_print")

    def etapa(rutas):
        original, buffer = sys.stdout, io.StringIO()
        sys.stdout = buffer
        try:
            print("volcado-de-codigo-de-bytes")
        finally:
            sys.stdout = original
        assert "volcado-de-codigo-de-bytes" in buffer.getvalue()  # el print llega al buffer, no a Prefect

    modulo.analizar = etapa
    monkeypatch.setitem(sys.modules, "etapa_con_print", modulo)
    monkeypatch.setattr(pipeline, "ETAPAS", (pipeline.Etapa("sentimiento", "etapa_con_print:analizar", "P2.4"),))
    assert pipeline.pipeline(fuentes=["news"])["etapas"] == {"sentimiento": "ok"}
    assert not [m for m in _todos_los_logs() if "volcado-de-codigo-de-bytes" in m]


def test_cuenta_los_registros_extraidos(prefect_local, scrapers_falsos, monkeypatch):
    from src.common import storage
    from src.observability import metricas

    monkeypatch.setattr(storage, "leer_registros", lambda ruta, cliente=None: [{}, {}, {}])
    pipeline.pipeline(fuentes=["news"])
    assert metricas._leer()["registros"]["news"] == 3


def test_cuenta_las_validaciones_fallidas_aunque_se_detenga(prefect_local, sin_esperas, scrapers_falsos, monkeypatch):
    from quality.checkpoints import ValidacionCriticaError
    from src.observability import metricas

    modulo = types.ModuleType("calidad_con_resumen")

    def validar(rutas):
        resumen = {"suite": "raw_news", "criticas": [{"regla": "a"}], "advertencias": [{"regla": "b"}, {"regla": "c"}]}
        raise ValidacionCriticaError("regla crítica", [resumen])

    modulo.validar = validar
    monkeypatch.setitem(sys.modules, "calidad_con_resumen", modulo)
    monkeypatch.setattr(pipeline, "ETAPAS", (pipeline.Etapa("validacion_cruda", "calidad_con_resumen:validar", "P2.2"),))
    assert pipeline.pipeline(fuentes=["news"], return_state=True).is_failed()
    # 4 intentos de la tarea (1 + 3 reintentos): cada intento cuenta lo que encontró
    validaciones = metricas._leer()["validaciones"]
    assert validaciones["raw_news|critica"] == 4 and validaciones["raw_news|advertencia"] == 8
