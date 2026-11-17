"""Métricas del pipeline publicadas en el Pushgateway (P3.1).

Las 8 métricas de la ruta de trabajo más dos de apoyo para las alertas:

| Métrica                              | Tipo        | Etiquetas          |
| ------------------------------------ | ----------- | ------------------ |
| registros_extraidos_total            | contador    | fuente             |
| errores_http_total                   | contador    | fuente, codigo     |
| duracion_corrida_segundos            | histograma  | flujo              |
| ultima_corrida_exitosa_timestamp     | gauge       | flujo              |
| validaciones_fallidas_total          | contador    | suite, severidad   |
| registros_bot_ratio                  | gauge       | fuente             |
| cuota_youtube_usada                  | gauge       | —                  |
| sentimiento_negativo_24h_ratio       | gauge       | fuente             |
| ultima_corrida_fallida_timestamp     | gauge       | flujo              |
| fallas_consecutivas                  | gauge       | flujo  (alerta A1) |

Cómo funciona: durante una corrida, el código llama a ``contar_*``; esos valores quedan
en memoria. Al final, ``registrar_corrida`` los suma a los acumulados guardados en
``data/estado/metricas.json`` y publica todo en un solo grupo del Pushgateway. Así los
contadores nunca bajan aunque el orquestador se reinicie, que es lo que espera Prometheus.

Si el Pushgateway no responde, solo queda un aviso en el log: las métricas nunca
detienen el pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("observability.metricas")

JOB = "radar_pipeline"
FUENTES = ("google_play", "youtube", "news")
BUCKETS = (5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0, 1800.0, 3600.0)
# La cuota de YouTube se reinicia a medianoche hora del Pacífico (se usa UTC-8 fijo)
_PACIFICO = timezone(timedelta(hours=-8))

_lock = threading.Lock()
_pendiente = {"registros": Counter(), "errores": Counter(), "validaciones": Counter(), "cuota": 0}


# ---------- 1. Lo que se cuenta durante la corrida ----------


def contar_registros(fuente: str, cantidad: int) -> None:
    with _lock:
        _pendiente["registros"][fuente] += int(cantidad)


def contar_error_http(fuente: str, codigo: int | str) -> None:
    with _lock:
        _pendiente["errores"][(fuente, str(codigo))] += 1


def contar_validacion(suite: str, severidad: str, cantidad: int = 1) -> None:
    with _lock:
        _pendiente["validaciones"][(suite, severidad)] += int(cantidad)


def sumar_cuota_youtube(unidades: int) -> None:
    with _lock:
        _pendiente["cuota"] += int(unidades)


def _tomar_pendiente() -> dict:
    with _lock:
        copia = {k: (v.copy() if isinstance(v, Counter) else v) for k, v in _pendiente.items()}
        for clave in ("registros", "errores", "validaciones"):
            _pendiente[clave].clear()
        _pendiente["cuota"] = 0
    return copia


# ---------- 2. Estado acumulado en disco ----------


def _clave(*partes: str) -> str:
    return "|".join(partes)


def archivo_estado() -> Path:
    return Path(os.getenv("LOCAL_RAW_DIR", "data")) / "estado" / "metricas.json"


# Series que empiezan en 0 para que aparezcan en Prometheus desde la primera corrida,
# aunque todavía no haya pasado nada. Si no, una alerta como "aumentaron los 429" no
# tendría con qué comparar.
CODIGOS_VIGILADOS = ("403", "429")
SUITES = (*(f"raw_{f}" for f in FUENTES), "clean_menciones")
SEVERIDADES = ("critica", "advertencia")


def _vacio() -> dict:
    return {
        "registros": {f: 0 for f in FUENTES},  # la alerta A2 necesita ver la serie en 0
        "errores": {_clave(f, c): 0 for f in FUENTES for c in CODIGOS_VIGILADOS},
        "validaciones": {_clave(s, v): 0 for s in SUITES for v in SEVERIDADES},
        "cuota_youtube": {"dia": "", "usada": 0},
        "flujos": {},
        "gauges": {},
    }


def _leer() -> dict:
    archivo = archivo_estado()
    try:
        if archivo.exists():
            base, guardado = _vacio(), json.loads(archivo.read_text("utf-8"))
            for clave in ("registros", "errores", "validaciones"):
                base[clave].update(guardado.pop(clave, {}))
            return {**base, **guardado}
    except (OSError, ValueError):
        log.warning("No se pudo leer %s; las métricas empiezan en 0", archivo)
    return _vacio()


def _guardar(estado: dict) -> None:
    archivo = archivo_estado()
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = archivo.with_suffix(f".{os.getpid()}-{threading.get_ident()}.tmp")
        temporal.write_text(json.dumps(estado, ensure_ascii=False), "utf-8")
        temporal.replace(archivo)  # atómico: nunca queda un JSON a medias
    except OSError as error:
        log.warning("No se pudo guardar el estado de las métricas: %s", error)


@contextmanager
def _bloqueo(segundos: float = 30):
    """Evita que dos corridas que terminan a la vez se pisen el archivo. Funciona en Linux y Windows."""
    candado = archivo_estado().with_suffix(".lock")
    candado.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + segundos
    while True:
        try:
            descriptor = os.open(candado, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            try:
                antiguedad = time.time() - candado.stat().st_mtime
            except FileNotFoundError:
                continue  # lo acaban de soltar: se intenta de nuevo
            # Un candado de más de 2 minutos es de un proceso que murió
            if antiguedad > 120:
                candado.unlink(missing_ok=True)
                continue
            if time.monotonic() > limite:
                raise TimeoutError(f"El archivo {candado} sigue bloqueado después de {segundos} s") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        candado.unlink(missing_ok=True)


def _sumar(estado: dict, pendiente: dict, ahora: datetime) -> None:
    for fuente, n in pendiente["registros"].items():
        estado["registros"][fuente] = estado["registros"].get(fuente, 0) + n
    for (fuente, codigo), n in pendiente["errores"].items():
        clave = _clave(fuente, codigo)
        estado["errores"][clave] = estado["errores"].get(clave, 0) + n
    for (suite, severidad), n in pendiente["validaciones"].items():
        clave = _clave(suite, severidad)
        estado["validaciones"][clave] = estado["validaciones"].get(clave, 0) + n
    dia = ahora.astimezone(_PACIFICO).date().isoformat()
    if estado["cuota_youtube"]["dia"] != dia:
        estado["cuota_youtube"] = {"dia": dia, "usada": 0}
    estado["cuota_youtube"]["usada"] += pendiente["cuota"]


def _registrar_flujo(estado: dict, flujo: str, exito: bool, duracion: float | None, ahora: datetime) -> int:
    datos = estado["flujos"].setdefault(
        flujo, {"fallas": 0, "exitosa": None, "fallida": None, "buckets": [0] * len(BUCKETS), "suma": 0.0, "conteo": 0}
    )
    if exito:
        datos["fallas"], datos["exitosa"] = 0, ahora.timestamp()
    else:
        datos["fallas"], datos["fallida"] = datos["fallas"] + 1, ahora.timestamp()
    if duracion is not None:
        datos["suma"] += duracion
        datos["conteo"] += 1
        datos["buckets"] = [b + (duracion <= limite) for b, limite in zip(datos["buckets"], BUCKETS, strict=True)]
    return datos["fallas"]


def registrar_corrida(
    flujo: str, exito: bool, duracion: float | None = None, gauges: dict | None = None, ahora: datetime | None = None
) -> dict:
    """Cierra la corrida: suma lo contado, actualiza el flujo, guarda y publica. Devuelve el estado."""
    ahora = ahora or datetime.now(UTC)
    pendiente = _tomar_pendiente()
    with _bloqueo():
        estado = _leer()
        _sumar(estado, pendiente, ahora)
        _registrar_flujo(estado, flujo, exito, duracion, ahora)
        for nombre, valores in (gauges or {}).items():
            estado["gauges"][nombre] = valores
        _guardar(estado)
    publicar(estado)
    return estado


# ---------- 3. Publicación ----------


class _Coleccion:
    """Convierte el estado en métricas de Prometheus."""

    def __init__(self, estado: dict):
        self.estado = estado

    def collect(self):
        from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily

        e = self.estado
        registros = CounterMetricFamily("registros_extraidos", "Registros guardados en la capa raw", labels=["fuente"])
        for fuente, n in e["registros"].items():
            registros.add_metric([fuente], n)
        yield registros

        errores = CounterMetricFamily("errores_http", "Respuestas HTTP con error de las fuentes", labels=["fuente", "codigo"])
        for clave, n in e["errores"].items():
            errores.add_metric(clave.split("|", 1), n)
        yield errores

        validaciones = CounterMetricFamily(
            "validaciones_fallidas", "Reglas de calidad fallidas", labels=["suite", "severidad"]
        )
        for clave, n in e["validaciones"].items():
            validaciones.add_metric(clave.split("|", 1), n)
        yield validaciones

        yield GaugeMetricFamily("cuota_youtube_usada", "Unidades de la API de YouTube usadas hoy", e["cuota_youtube"]["usada"])

        duracion = HistogramMetricFamily("duracion_corrida_segundos", "Duración de cada corrida", labels=["flujo"])
        exitosa = GaugeMetricFamily("ultima_corrida_exitosa_timestamp", "Última corrida exitosa (Unix)", labels=["flujo"])
        fallida = GaugeMetricFamily("ultima_corrida_fallida_timestamp", "Última corrida fallida (Unix)", labels=["flujo"])
        fallas = GaugeMetricFamily("fallas_consecutivas", "Corridas fallidas seguidas", labels=["flujo"])
        for flujo, d in e["flujos"].items():
            if d["conteo"]:
                cubetas = [(str(limite), n) for limite, n in zip(BUCKETS, d["buckets"], strict=True)]
                duracion.add_metric([flujo], cubetas + [("+Inf", d["conteo"])], d["suma"])
            if d["exitosa"] is not None:
                exitosa.add_metric([flujo], d["exitosa"])
            if d["fallida"] is not None:
                fallida.add_metric([flujo], d["fallida"])
            fallas.add_metric([flujo], d["fallas"])
        yield from (duracion, exitosa, fallida, fallas)

        ayuda = {
            "registros_bot_ratio": "Proporción de bots en las últimas 24 h",
            "sentimiento_negativo_24h_ratio": "Proporción de menciones negativas en las últimas 24 h",
        }
        for nombre, texto in ayuda.items():
            gauge = GaugeMetricFamily(nombre, texto, labels=["fuente"])
            for fuente, valor in (e["gauges"].get(nombre) or {}).items():
                gauge.add_metric([fuente], valor)
            yield gauge


def registro_prometheus(estado: dict):
    from prometheus_client import CollectorRegistry

    registro = CollectorRegistry()
    registro.register(_Coleccion(estado))
    return registro


def publicar(estado: dict) -> bool:
    """Reemplaza el grupo del Pushgateway con todas las métricas. False si no se pudo."""
    url = os.getenv("PUSHGATEWAY_URL", "").strip()
    if not url:
        log.info("PUSHGATEWAY_URL vacía; las métricas quedan solo en %s", archivo_estado())
        return False
    try:
        from prometheus_client import push_to_gateway

        push_to_gateway(url, job=JOB, registry=registro_prometheus(estado), timeout=5)
        return True
    except Exception as error:  # noqa: BLE001 - las métricas no deben romper el flujo
        log.warning("No se pudieron publicar las métricas en %s: %s", url, error)
        return False
