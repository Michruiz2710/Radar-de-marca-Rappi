"""Pruebas de las reglas de texto: normalizar, enmascarar datos personales e idioma."""

import pytest

from src.transform.clean.texto import (
    clave_comparacion,
    contar_urls,
    detectar_idioma,
    enmascarar,
    esta_vacio,
    limpiar_texto,
    normalizar,
)

# ---------- normalizar ----------


def test_normalizar_junta_espacios_y_saltos_de_linea():
    assert normalizar("  muy   mal\n\n servicio\t ") == "muy mal servicio"


def test_normalizar_convierte_entidades_html():
    assert normalizar("Rappi &amp; la SIC") == "Rappi & la SIC"


def test_normalizar_quita_caracteres_invisibles():
    assert normalizar("pési\u200bmo\ufeff") == "pésimo"


def test_normalizar_conserva_emojis_mayusculas_y_signos():
    assert normalizar("¡PÉSIMO! 😡") == "¡PÉSIMO! 😡"


@pytest.mark.parametrize("emoji", ["👨\u200d👩\u200d👧", "👩\u200d🍳", "❤\ufe0f\u200d🔥", "🏳\ufe0f\u200d🌈"])
def test_normalizar_conserva_emojis_compuestos(emoji):
    # El ZWJ (U+200D) une varios emojis en uno; quitarlo los partiría
    assert normalizar(f"pedido tarde {emoji}") == f"pedido tarde {emoji}"


def test_normalizar_quita_los_demas_invisibles_pero_no_el_zwj():
    assert normalizar("a\u200bb\u2060c\ufeffd 👩\u200d🍳") == "abcd 👩\u200d🍳"


@pytest.mark.parametrize("texto", ["", "   ", "\u200b\ufeff", "\u200d", "\u200c\u200d\ufe0f", " \u2060 \n\t"])
def test_texto_sin_contenido_visible_queda_vacio(texto):
    assert esta_vacio(limpiar_texto(texto))


def test_texto_con_un_emoji_no_esta_vacio():
    assert not esta_vacio(limpiar_texto("👍"))


def test_normalizar_texto_vacio():
    assert normalizar(None) == "" and normalizar("") == ""


# ---------- enmascarar (Habeas Data) ----------


@pytest.mark.parametrize(
    "texto",
    ["llamen al 3001234567", "llamen al 300 123 4567", "llamen al +57 300-123-4567", "llamen al 573001234567"],
)
def test_enmascara_celulares(texto):
    assert enmascarar(texto) == "llamen al [TELEFONO]"


def test_enmascara_telefono_fijo():
    assert enmascarar("fijo 601 234 5678") == "fijo [TELEFONO]"


def test_enmascara_correos():
    assert enmascarar("escriban a ana.perez+rappi@mail.com.co ya") == "escriban a [CORREO] ya"


def test_enmascara_numeros_largos_como_cedulas_o_pedidos():
    assert enmascarar("mi cédula 1020304050 y pedido 987654321") == "mi cédula [NUMERO] y pedido [NUMERO]"


def test_no_enmascara_montos_ni_numeros_cortos():
    # Los montos importan para las quejas de cobros
    texto = "me cobraron $1.000.000 y 25.900 por 2 pedidos"
    assert enmascarar(texto) == texto


def test_enmascara_enlaces():
    assert enmascarar("miren https://bit.ly/abc y www.rappi.com") == "miren [URL] y [URL]"


def test_limpiar_texto_normaliza_y_enmascara():
    assert limpiar_texto("  Llamen  al 3001234567 &amp; ya ") == "Llamen al [TELEFONO] & ya"


def test_contar_urls():
    assert contar_urls("a https://x.com b http://y.co c www.z.org") == 3
    assert contar_urls(None) == 0


# ---------- clave de comparación ----------


def test_clave_ignora_mayusculas_signos_espacios_y_emojis():
    assert clave_comparacion("¡Gana dinero YA! 🤑") == clave_comparacion("gana  dinero ya")


def test_clave_ignora_marcadores():
    assert clave_comparacion("visita [URL]") == clave_comparacion("visita [URL] [URL]")


# ---------- idioma ----------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Pésimo servicio, el pedido nunca llegó y no me devuelven el dinero", "es"),
        ("SIC multa a Rappi por cobros & cláusulas", "es"),
        ("¿Por qué cobran tanto por el domicilio?", "es"),
        ("O entregador demorou muito e a comida chegou fria, péssimo serviço", "pt"),
        ("Pedi uma pizza e veio errada", "pt"),
        ("Não funciona", "pt"),
        ("The delivery was very late and the food was cold", "en"),
    ],
)
def test_detecta_espanol_portugues_e_ingles(texto, esperado):
    assert detectar_idioma(texto, "es") == esperado


@pytest.mark.parametrize("texto", ["excelente", "jajaja", "Rappi 😡", "[URL]"])
def test_sin_pistas_usa_el_idioma_de_la_consulta(texto):
    assert detectar_idioma(texto, "es") == "es"
