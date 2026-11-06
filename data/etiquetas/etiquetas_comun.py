"""Valores y reglas que comparten preparar_muestra.py y validar_muestra.py."""

from __future__ import annotations

import re

SENTIMIENTOS = ["positivo", "neutro", "negativo"]
TEMAS = ["entregas", "cobros_y_pagos", "soporte", "precios", "app", "repartidores", "otro"]
ETIQUETADORES = ["sara", "gabriel"]
COLUMNAS = ["id_registro", "texto", "calificacion", "fecha_publicacion", "sentimiento", "tema", "etiquetado_por"]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# De 7 a 14 dígitos, con un espacio, punto o guion entre ellos. No incluye el separador final.
_NUMERO_LARGO = re.compile(r"(?<![\d.,])\+?\d(?:[\s.\-]?\d){6,13}(?!\d)")
_FECHA = re.compile(r"^(?:\d{4}[\s.\-]\d{1,2}[\s.\-]\d{1,2}|\d{1,2}[\s.\-]\d{1,2}[\s.\-]\d{2,4})$")
# Grupos de tres, como 10 000 000 o 1.200.000. Un teléfono escrito 300 123 456 también cae aquí.
_MONTO = re.compile(r"^\d{1,3}(?:[\s.]\d{3})+$")


def _es_telefono(numero: str) -> bool:
    return not (_FECHA.match(numero) or _MONTO.match(numero))


def enmascarar(texto: str) -> str:
    """La muestra va a Git, así que se tapan correos y teléfonos escritos en la reseña."""
    sin_correos = _EMAIL.sub("[CORREO]", texto)
    return _NUMERO_LARGO.sub(lambda m: "[TELEFONO]" if _es_telefono(m.group()) else m.group(), sin_correos)


def tiene_dato_personal(texto: str) -> bool:
    return enmascarar(texto) != texto
