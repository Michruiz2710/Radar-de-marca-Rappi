"""Pruebas del clasificador de temas (P2.4)."""

import pytest

from src.transform.nlp.temas import (
    TEMA_OTRO,
    TEMAS_ORDEN,
    TEMAS_VALIDOS,
    clasificar_tema,
    normalizar,
    puntajes,
)


@pytest.mark.parametrize(
    "texto, tema",
    [
        ("El pedido nunca llegó y la entrega se demoró dos horas", "entregas"),
        ("Me hicieron un cobro doble y el reembolso no llega", "cobros_y_pagos"),
        ("Nadie me responde en el chat de ayuda", "soporte"),
        ("Los precios están carísimos y la propina es obligatoria", "precios"),
        ("La actualización dejó la app con un error y se cierra sola", "app"),
        ("El repartidor fue grosero conmigo", "repartidores"),
    ],
)
def test_cada_tema_se_detecta(texto, tema):
    assert clasificar_tema(texto).tema == tema


@pytest.mark.parametrize("texto", ["Me encanta", "la mejor de todas", "Muy buena experiencia"])
def test_sin_palabras_clave_es_otro(texto):
    resultado = clasificar_tema(texto)
    assert resultado.tema == TEMA_OTRO
    assert resultado.temas_detectados == ()


@pytest.mark.parametrize("texto", [None, "", "   ", 123])
def test_texto_vacio_o_no_valido_es_otro(texto):
    assert clasificar_tema(texto).tema == TEMA_OTRO


def test_ignora_mayusculas_y_tildes():
    assert clasificar_tema("ME COBRARON DE MÁS").tema == "cobros_y_pagos"
    assert clasificar_tema("Reembolso").tema == "cobros_y_pagos"


def test_no_confunde_saludo_con_demora():
    # "tardes" no es "tarde": un saludo no debe contar como entregas
    assert clasificar_tema("Buenas tardes, gracias").tema == TEMA_OTRO


def test_gana_el_tema_con_mas_coincidencias():
    texto = "El repartidor y el domiciliario fueron groseros y maleducados, tardó en llegar"
    resultado = clasificar_tema(texto)
    assert resultado.tema == "repartidores"
    assert "entregas" in resultado.temas_detectados


def test_empate_gana_el_mas_especifico():
    # un patrón de cobros y uno de entregas: gana cobros por el orden de desempate
    resultado = clasificar_tema("cobraron el pedido")
    assert puntajes("cobraron el pedido")["cobros_y_pagos"] == puntajes("cobraron el pedido")["entregas"]
    assert resultado.tema == "cobros_y_pagos"


def test_temas_validos_coinciden_con_la_guia():
    assert set(TEMAS_VALIDOS) == {
        "entregas", "cobros_y_pagos", "soporte", "precios", "app", "repartidores", "otro",
    }
    assert TEMAS_ORDEN[-1] == "entregas"  # el más general va al final del desempate


def test_normalizar_quita_tildes_y_espacios():
    assert normalizar("  ÁRBOL   Ñandú ") == "arbol nandu"
