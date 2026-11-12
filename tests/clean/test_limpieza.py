"""Pruebas de la limpieza completa: de archivos raw a la tabla menciones.

Usan SQLite en memoria en lugar de Postgres, así corren en el CI sin base de datos.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from src.transform.clean import limpieza
from src.transform.clean.limpieza import (
    VERSION_LIMPIEZA,
    limpiar,
    limpiar_rutas,
    transformar,
)
from src.transform.clean.tabla import COLUMNAS


def cruda(id_original="r1", fuente="google_play", **cambios):
    datos = {
        "fuente": fuente,
        "id_original": id_original,
        "id_registro": f"{fuente}:{id_original}",
        "texto": "Pésimo, el pedido llegó frío",
        "fecha_publicacion": "2026-11-05T10:00:00Z",
        "fecha_extraccion": "2026-11-06T10:00:00Z",
        "idioma": "es",
        "pais": "co",
        "autor_hash": "a" * 64,
        "calificacion": 1,
        "run_id": "run-1",
        "version_scraper": "0.1.0",
        "version_contrato": "1.3.0",
    }
    datos.update(cambios)
    return datos


def escribir(tmp_path, nombre, filas):
    ruta = tmp_path / nombre
    ruta.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in filas), encoding="utf-8")
    return str(ruta)


@pytest.fixture
def motor():
    return create_engine("sqlite://")


def leer_tabla(motor):
    with motor.connect() as conexion:
        return {f.id_registro: f for f in conexion.execute(text("SELECT * FROM menciones"))}


# ---------- transformar (sin base de datos) ----------


def test_quita_duplicados_y_deja_la_version_mas_reciente():
    vieja = cruda(texto="Regular", calificacion=3, fecha_publicacion="2026-11-01T10:00:00Z")
    editada = cruda(texto="Pésimo, nunca respondieron", calificacion=1, fecha_publicacion="2026-11-05T10:00:00Z")
    filas, resumen = transformar([editada, vieja])
    assert len(filas) == 1 and resumen["duplicados"] == 1
    assert filas[0]["texto_limpio"] == "Pésimo, nunca respondieron" and filas[0]["calificacion"] == 1


def test_descarta_filas_incompletas():
    filas, resumen = transformar([cruda(), cruda(id_original="r2", texto=""), {"fuente": "youtube"}])
    assert len(filas) == 1 and resumen["descartados"] == 2


@pytest.mark.parametrize("texto", ["   ", "\u200b\ufeff", "\u200d", " \u2060\n "])
def test_descarta_textos_que_quedan_vacios_al_limpiar(texto, caplog):
    filas, resumen = transformar([cruda("r1"), cruda("r2", texto=texto)])
    assert [f["id_registro"] for f in filas] == ["google_play:r1"]
    assert resumen["descartados"] == 1
    assert "queda vacío" in caplog.text and "google_play:r2" in caplog.text


def test_conserva_emojis_compuestos_en_texto_limpio():
    filas, _ = transformar([cruda(texto="Llegó tarde otra vez 👨\u200d👩\u200d👧 ❤\ufe0f\u200d🔥")])
    assert filas[0]["texto_limpio"] == "Llegó tarde otra vez 👨\u200d👩\u200d👧 ❤\ufe0f\u200d🔥"


def test_reporta_porcentaje_de_bots_total_y_por_fuente():
    spam = "gana dinero https://bit.ly/a https://t.me/b"
    crudas = [cruda(f"g{i}", autor_hash=f"g{i}".ljust(64, "0")) for i in range(2)] + [
        cruda(f"y{i}", fuente="youtube", calificacion=None, autor_hash=f"{i}" * 64, texto=spam if i == 0 else f"comentario {i}")
        for i in range(4)
    ]
    _, resumen = transformar(crudas)
    assert resumen["bots"] == 1
    assert resumen["pct_bots"] == round(100 / 6, 2)
    assert resumen["bots_por_fuente"] == {"google_play": 0, "youtube": 1}
    assert resumen["pct_bots_por_fuente"] == {"google_play": 0.0, "youtube": 25.0}


def test_porcentaje_de_bots_sin_filas():
    _, resumen = transformar([])
    assert (resumen["bots"], resumen["pct_bots"], resumen["bots_por_fuente"]) == (0, 0.0, {})


def test_el_porcentaje_de_bots_sale_en_el_log(tmp_path, motor, caplog):
    caplog.set_level("INFO", logger="limpieza")
    limpiar({"google_play": escribir(tmp_path, "a.jsonl", [cruda()])}, motor=motor)
    assert '"pct_bots": 0.0' in caplog.text and '"pct_bots_por_fuente"' in caplog.text


def test_recalcula_editada_tras_respuesta_en_archivos_viejos():
    # Archivos anteriores al contrato v1.2.0 no traen estos campos
    filas, _ = transformar([cruda(fecha_respuesta="2026-11-02T10:00:00Z")])
    assert filas[0]["editada_tras_respuesta"] is True
    assert filas[0]["fecha_edicion"] == datetime(2026, 11, 5, 10, tzinfo=timezone.utc)


def test_ignora_campos_de_contratos_anteriores():
    filas, _ = transformar([cruda(subreddit=None)])
    assert len(filas) == 1 and "subreddit" not in filas[0]


def test_no_guarda_el_texto_original():
    # Minimización (Ley 1581): el texto sin enmascarar se queda en la capa raw
    filas, _ = transformar([cruda(texto="llamen al 3001234567")])
    assert filas[0]["texto_limpio"] == "llamen al [TELEFONO]"
    assert "texto" not in filas[0] and set(filas[0]) == set(COLUMNAS)


def test_enmascara_la_respuesta_de_rappi():
    filas, _ = transformar([cruda(respuesta_marca="Escríbenos a soporte@rappi.com", fecha_respuesta="2026-11-05T11:00:00Z")])
    assert filas[0]["respuesta_marca"] == "Escríbenos a [CORREO]"


def test_marca_idioma_y_bots():
    filas, resumen = transformar(
        [
            cruda("y1", fuente="youtube", texto="O entregador demorou muito", calificacion=None),
            cruda("y2", fuente="youtube", texto="gana dinero https://bit.ly/a https://t.me/b", calificacion=None, autor_hash="b" * 64),
        ]
    )
    por_id = {f["id_registro"]: f for f in filas}
    assert por_id["youtube:y1"]["idioma_detectado"] == "pt" and por_id["youtube:y1"]["es_bot"] is False
    assert por_id["youtube:y2"]["es_bot"] is True
    assert por_id["youtube:y2"]["motivo_bot"] == "multiples_enlaces,promocional"
    assert resumen["bots"] == 1


def test_hash_texto_cambia_si_cambia_el_texto():
    a, _ = transformar([cruda(texto="uno")])
    b, _ = transformar([cruda(texto="dos")])
    assert a[0]["hash_texto"] != b[0]["hash_texto"] and len(a[0]["hash_texto"]) == 64


# ---------- carga en la tabla (SQLite) ----------


def test_carga_y_es_idempotente(tmp_path, motor):
    ruta = escribir(tmp_path, "run1.jsonl", [cruda("r1"), cruda("r2")])
    primera = limpiar({"google_play": ruta, "youtube": None}, motor=motor)
    segunda = limpiar({"google_play": ruta}, motor=motor)
    assert (primera["nuevos"], primera["actualizados"]) == (2, 0)
    assert (segunda["nuevos"], segunda["actualizados"], segunda["sin_cambios"]) == (0, 0, 2)
    assert len(leer_tabla(motor)) == 2


def test_una_version_mas_reciente_reemplaza_a_la_anterior(tmp_path, motor):
    limpiar({"google_play": escribir(tmp_path, "a.jsonl", [cruda(texto="Regular", calificacion=3)])}, motor=motor)
    nueva = cruda(texto="Pésimo", calificacion=1, fecha_publicacion="2026-11-07T10:00:00Z")
    resumen = limpiar({"google_play": escribir(tmp_path, "b.jsonl", [nueva])}, motor=motor)
    fila = leer_tabla(motor)["google_play:r1"]
    assert resumen["actualizados"] == 1
    assert (fila.texto_limpio, fila.calificacion) == ("Pésimo", 1)


def test_una_version_vieja_no_reemplaza_a_la_nueva(tmp_path, motor):
    nueva = cruda(texto="Pésimo", fecha_publicacion="2026-11-07T10:00:00Z")
    limpiar({"google_play": escribir(tmp_path, "a.jsonl", [nueva])}, motor=motor)
    resumen = limpiar({"google_play": escribir(tmp_path, "b.jsonl", [cruda(texto="Regular")])}, motor=motor)
    assert resumen["sin_cambios"] == 1 and leer_tabla(motor)["google_play:r1"].texto_limpio == "Pésimo"


def test_nueva_version_de_la_limpieza_actualiza_todo(tmp_path, motor, monkeypatch):
    ruta = escribir(tmp_path, "a.jsonl", [cruda()])
    limpiar({"google_play": ruta}, motor=motor)
    monkeypatch.setattr(limpieza, "VERSION_LIMPIEZA", "9.9.9")
    resumen = limpiar({"google_play": ruta}, motor=motor)
    assert resumen["actualizados"] == 1 and leer_tabla(motor)["google_play:r1"].version_limpieza == "9.9.9"


def test_sin_archivos_nuevos_no_toca_la_base(motor):
    assert limpiar({"google_play": None, "youtube": None}, motor=motor) == {"archivos": 0, "leidos": 0}
    assert limpiar_rutas([], motor=motor)["archivos"] == 0


def test_varias_fuentes_en_una_corrida(tmp_path, motor):
    rutas = {
        "google_play": escribir(tmp_path, "gp.jsonl", [cruda("r1")]),
        "news": escribir(tmp_path, "n.jsonl", [cruda("n1", fuente="news", calificacion=None, autor_hash=None, medio="El Tiempo")]),
    }
    resumen = limpiar(rutas, motor=motor)
    tabla = leer_tabla(motor)
    assert resumen["archivos"] == 2 and set(tabla) == {"google_play:r1", "news:n1"}
    assert tabla["news:n1"].es_bot in (0, False) and tabla["google_play:r1"].version_limpieza == VERSION_LIMPIEZA
