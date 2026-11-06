import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "data" / "etiquetas"
sys.path.insert(0, str(RAIZ))  # los scripts importan etiquetas_comun


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


preparar = cargar("preparar_muestra")
validar = cargar("validar_muestra")


def resenas(por_estrella=60):
    return [
        {"reviewId": f"id{e}-{i}", "content": f"reseña inventada numero {e} {i} para probar", "score": e, "at": "2026-11-01T10:00:00"}
        for e in range(1, 6) for i in range(por_estrella)
    ]


def etiquetadas():
    muestra = preparar.seleccionar(resenas())
    for fila in muestra:
        fila.update(sentimiento="neutro", tema="app", etiquetado_por="sara", calificacion=str(fila["calificacion"]))
    return muestra


def test_selecciona_200_equilibradas_y_reproducibles():
    muestra = preparar.seleccionar(resenas())
    assert len(muestra) == 200
    assert all(sum(r["calificacion"] == e for r in muestra) == 40 for e in range(1, 6))
    assert muestra == preparar.seleccionar(resenas())


def test_completa_si_una_estrella_se_queda_corta():
    filas = [f for f in resenas() if f["score"] != 3 or f["reviewId"].endswith(("-1", "-2"))]
    muestra = preparar.seleccionar(filas)
    assert len(muestra) == 200


def test_falla_si_no_alcanzan():
    with pytest.raises(SystemExit):
        preparar.seleccionar(resenas(por_estrella=10))


def test_descarta_cortas_y_textos_repetidos():
    filas = resenas() + [{"reviewId": "x", "content": "muy buena", "score": 5, "at": "2026-11-01"}]
    assert all(r["id_registro"] != "google_play:x" for r in preparar.seleccionar(filas))
    repetida = {"id_original": "a", "texto": "texto igual para las dos reseñas", "calificacion": 5, "fecha_publicacion": "2026"}
    otra = {**repetida, "id_original": "b"}
    assert len(preparar.seleccionar([repetida, otra] + resenas(40), por_estrella=1)) == 5


@pytest.mark.parametrize("telefono", ["300 123 4567", "300.123.4567", "300-123-4567", "3001234567", "+57 300 123 4567"])
def test_enmascara_telefonos(telefono):
    assert preparar.enmascarar(f"mi numero {telefono} no llega") == "mi numero [TELEFONO] no llega"


def test_enmascara_correos():
    assert preparar.enmascarar("escribeme a ana.perez@correo.com ya") == "escribeme a [CORREO] ya"


@pytest.mark.parametrize("texto", ["el 2026-11-04 no llego", "el 04/11/2026 no llego", "pague 10 000 000 pesos", "costo 1.200.000 pesos", "costo 120.000"])
def test_no_tapa_fechas_ni_montos(texto):
    assert preparar.enmascarar(texto) == texto


def test_validador_acepta_lo_correcto():
    assert validar.validar(etiquetadas()) == []


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("sentimiento", "", "vacíos"), ("tema", "inventado", "tema inválido"), ("sentimiento", "bueno", "sentimiento inválido"),
    ("calificacion", "7", "calificacion inválida"), ("texto", "llama al 3001234567", "correo o teléfono"),
])
def test_validador_detecta_errores(campo, valor, mensaje):
    filas = etiquetadas()
    filas[3][campo] = valor
    assert any(mensaje in e for e in validar.validar(filas))


def test_validador_detecta_filas_faltantes_y_repetidas():
    filas = etiquetadas()
    assert any("199 filas" in e for e in validar.validar(filas[:-1]))
    filas[1]["id_registro"] = filas[0]["id_registro"]
    assert any("repetidos" in e for e in validar.validar(filas))


def test_ciclo_completo_con_excel(tmp_path):
    from openpyxl import load_workbook

    destino = tmp_path / "hoja.xlsx"
    preparar.escribir_hoja(preparar.seleccionar(resenas()), destino)
    assert any("vacíos" in e for e in validar.validar(validar.leer(destino)))
    libro = load_workbook(destino)
    hoja = libro.active
    assert len(hoja.data_validations.dataValidation) == 3
    for fila in range(2, 202):
        hoja.cell(fila, 5).value, hoja.cell(fila, 6).value, hoja.cell(fila, 7).value = "positivo", "entregas", "gabriel"
    libro.save(destino)
    assert validar.validar(validar.leer(destino)) == []


def test_texto_que_empieza_por_igual_no_es_formula_y_quita_controles(tmp_path):
    from openpyxl import load_workbook

    fila = {"reviewId": "f", "content": "=SUM(A1) cuatro palabras aqui\x0b", "score": 1, "at": "2026"}
    registro = preparar.normalizar(fila)
    assert "\x0b" not in registro["texto"]
    destino = tmp_path / "h.xlsx"
    preparar.escribir_hoja([registro], destino)
    assert load_workbook(destino).active["B2"].data_type == "s"


def test_excel_de_google_sheets_con_enteros_como_decimales(tmp_path):
    from openpyxl import load_workbook

    destino = tmp_path / "hoja.xlsx"
    preparar.escribir_hoja(preparar.seleccionar(resenas()), destino)
    libro = load_workbook(destino)
    hoja = libro.active
    for fila in range(2, 202):
        hoja.cell(fila, 3).value = float(hoja.cell(fila, 3).value)
        hoja.cell(fila, 5).value, hoja.cell(fila, 6).value, hoja.cell(fila, 7).value = "positivo", "entregas", "gabriel"
    libro.save(destino)
    filas = validar.leer(destino)
    assert filas[0]["calificacion"] in {"1", "2", "3", "4", "5"}
    assert validar.validar(filas) == []


def test_muestra_entregada_cumple_el_validador():
    assert validar.validar(validar.leer(RAIZ / "muestra_200.csv")) == []
