"""Clasificación por tema con un diccionario de palabras clave (P2.4).

Temas: entregas, cobros_y_pagos, soporte, precios, app, repartidores, y `otro` cuando no
aparece ninguna palabra clave (mismos valores que la guía de etiquetado).

Cómo funciona:
1. El texto se pasa a minúsculas y sin tildes.
2. Cada tema tiene patrones (expresiones regulares) que deben empezar al inicio de una palabra.
3. Gana el tema con más patrones distintos encontrados. En un empate gana el primero de
   TEMAS_ORDEN, que va de lo más específico a lo más general.
4. Sin ninguna coincidencia el tema es `otro`.

No se lee ninguna base de datos ni se carga ningún modelo: es una función pura.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TEMA_OTRO = "otro"

# Los patrones se escriben sin tildes y se buscan al inicio de palabra (\b).
# Un patrón sin \b al final cubre variantes: "entreg" encuentra entrega, entregaron, entregar.
PALABRAS_CLAVE: dict[str, tuple[str, ...]] = {
    "cobros_y_pagos": (
        r"cobr", r"reembols", r"rappipay", r"tarjeta", r"pag(?:o|os|ar|ue|aron|ando|ado)\b",
        r"debit", r"credit", r"efectivo", r"nequi", r"daviplata", r"\bpse\b", r"saldo",
        r"devolv", r"devoluc", r"factur", r"estaf", r"fraude", r"doble cargo", r"cargo",
        r"descont(?:ar|aron|o|ado)\b", r"dinero", r"plata", r"cashback", r"credito",
    ),
    "repartidores": (
        r"repartidor", r"rappitendero", r"mensajero", r"domiciliario", r"rapper",
        r"conductor", r"motorizado", r"grosero", r"maleducado", r"mal trato", r"amabl",
    ),
    "soporte": (
        r"soporte", r"atencion al cliente", r"servicio al cliente", r"\bchat\b",
        r"ayuda", r"reclamo", r"queja", r"no me (?:respond|contest|solucion)",
        r"nadie (?:respond|contest|solucion)", r"sin respuesta", r"respuesta", r"agente",
        r"asesor", r"\bpqr\b", r"atencion",
    ),
    "precios": (
        r"precio", r"cost(?:o|os|oso|osa)\b", r"car(?:o|os|a|as|isimo|isima)\b", r"barat",
        r"propina", r"promo", r"cupon", r"descuento", r"oferta", r"\bprime\b", r"suscrip",
        r"tarifa", r"valor", r"sobrecosto", r"costo de (?:envio|domicilio)",
    ),
    "app": (
        r"actualiz", r"error", r"falla", r"funciona", r"se cae",
        r"se cierra", r"se traba", r"lent(?:o|a)\b", r"abre", r"cargar", r"inicia(?:r)? sesion",
        r"iniciar", r"contrasena", r"cuenta", r"version", r"interfaz", r"mapa", r"ubicacion",
        r"bug", r"pantalla", r"notificacion", r"\bgps\b", r"crash", r"instal", r"descarg", r"funcion", r"facil de usar",
    ),
    "entregas": (
        r"entreg", r"envio", r"demor", r"tard(?:o|a|an|ar|aron|ando|e|anza)\b", r"lleg(?:o|a|an|ar|aron|ando)\b",
        r"pedido", r"orden", r"incomplet", r"equivoc", r"falt(?:o|a|aron|ante|antes)\b",
        r"esper", r"rastre", r"cancel", r"nunca llego", r"\bhoras?\b", r"minutos",
    ),
}

# Orden de desempate: de lo más específico (cobros, repartidores) a lo más general (entregas).
TEMAS_ORDEN: tuple[str, ...] = tuple(PALABRAS_CLAVE)

TEMAS_VALIDOS: tuple[str, ...] = (*TEMAS_ORDEN, TEMA_OTRO)

_PATRONES: dict[str, tuple[re.Pattern[str], ...]] = {
    tema: tuple(re.compile(r"\b" + p if not p.startswith(r"\b") else p) for p in patrones)
    for tema, patrones in PALABRAS_CLAVE.items()
}


@dataclass(frozen=True)
class ResultadoTema:
    """Tema principal y todos los temas con alguna coincidencia (de más a menos fuerte)."""

    tema: str
    temas_detectados: tuple[str, ...]


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples. Conserva letras, números y signos."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def puntajes(texto: str | None) -> dict[str, int]:
    """Cuántos patrones distintos de cada tema aparecen en el texto."""
    if not isinstance(texto, str) or not texto.strip():
        return {tema: 0 for tema in TEMAS_ORDEN}
    normal = normalizar(texto)
    return {
        tema: sum(1 for patron in patrones if patron.search(normal))
        for tema, patrones in _PATRONES.items()
    }


def clasificar_tema(texto: str | None) -> ResultadoTema:
    """Devuelve el tema principal del texto, o `otro` si no hay coincidencias."""
    cuenta = puntajes(texto)
    con_coincidencia = [t for t in TEMAS_ORDEN if cuenta[t] > 0]
    if not con_coincidencia:
        return ResultadoTema(tema=TEMA_OTRO, temas_detectados=())
    # sorted es estable: a igual puntaje se conserva el orden de TEMAS_ORDEN.
    ordenados = sorted(con_coincidencia, key=lambda t: -cuenta[t])
    return ResultadoTema(tema=ordenados[0], temas_detectados=tuple(ordenados))
