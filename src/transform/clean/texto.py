"""Reglas de limpieza de texto: normalizar, enmascarar datos personales y detectar idioma.

Todas son funciones puras (no leen ni escriben nada), así que se prueban solas.
"""

import html
import re
import unicodedata

# --- Marcadores que reemplazan lo que se enmascara ---
URL = "[URL]"
CORREO = "[CORREO]"
TELEFONO = "[TELEFONO]"
NUMERO = "[NUMERO]"

_RE_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celulares de Colombia: 3XX XXX XXXX, con o sin +57 y separadores
_RE_CELULAR = re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
# Fijos de Colombia: 60X XXX XXXX
_RE_FIJO = re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?60\d[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
# 7 o más dígitos seguidos: cédulas, tarjetas, números de pedido.
# No toca montos con puntos ("$1.000.000"), que importan para las quejas de cobros.
_RE_NUMERO_LARGO = re.compile(r"(?<![\d.,])\d{7,}(?![\d.,])")

# Caracteres invisibles que se cuelan al copiar y pegar. NO incluye U+200C ni U+200D
# (ZWNJ y ZWJ): el ZWJ une emojis compuestos como 👨‍👩‍👧, 👩‍🍳 o ❤️‍🔥, y sin él
# quedarían partidos en varios emojis.
_RE_INVISIBLES = re.compile("[\u200b\u200e\u200f\u2028\u2029\u2060\ufeff]")
# Lo que no se ve: espacios, uniones de emojis y selectores de variante
_RE_SIN_CONTENIDO = re.compile("[\s\u200c\u200d\ufe0e\ufe0f]+")
_RE_ESPACIOS = re.compile(r"\s+")
_RE_MARCADORES = re.compile(r"\[(?:URL|CORREO|TELEFONO|NUMERO)\]")

# --- Detección de idioma ---
# Las fuentes de Rappi traen español, portugués (Brasil) e inglés. Cada idioma se
# reconoce por palabras muy frecuentes que NO existen en los otros dos, y por
# letras propias (ñ, ¿ en español; ã, ç en portugués). Es simple, explicable y,
# en textos cortos, más confiable que un detector general.
IDIOMA_INDETERMINADO = "und"
_PALABRAS = {
    "es": {
        "el", "la", "los", "las", "del", "al", "y", "es", "son", "pero", "muy", "con", "una",
        "unas", "unos", "un", "en", "qué", "que", "hay", "yo", "bien", "porque", "cuando",
        "esto", "esta", "este", "estos", "estas", "eso", "ese", "esa", "su", "sus", "le", "les",
        "lo", "mi", "mis", "ya", "siempre", "hasta", "donde", "mucho", "muchos", "mucha", "más",
        "sí", "sin", "ni", "tiene", "tienen", "fue", "hace", "hacer", "puede", "he", "ha", "han",
        "nunca", "nada", "llegó", "llega", "servicio", "dinero", "pésimo", "excelente",
        "gracias", "tampoco", "ahora",
    },
    "pt": {
        "não", "é", "com", "uma", "um", "do", "da", "dos", "das", "em", "ao", "aos", "à", "às",
        "muito", "muita", "você", "vocês", "mas", "mais", "foi", "tem", "têm", "eu", "ele",
        "ela", "isso", "isto", "essa", "esse", "estão", "então", "também", "só", "já", "nem",
        "sem", "pelo", "pela", "meu", "minha", "seu", "sua", "pra", "pro", "obrigado",
        "obrigada", "chegou", "demorou", "péssimo", "serviço", "entregador", "aplicativo",
        "dinheiro", "nada",
    },
    "en": {
        "the", "and", "is", "it", "to", "of", "you", "this", "that", "was", "for", "my", "with",
        "not", "are", "have", "they", "very", "but", "good", "bad", "service", "delivery",
        "order", "never", "always", "i", "food", "what", "your", "there",
    },
}
# Palabras que comparten dos idiomas no sirven como pista: se quitan
_COMPARTIDAS = {
    palabra
    for idioma, palabras in _PALABRAS.items()
    for otro, otras in _PALABRAS.items()
    if idioma != otro
    for palabra in palabras & otras
}
_PALABRAS = {idioma: palabras - _COMPARTIDAS for idioma, palabras in _PALABRAS.items()}
_LETRAS = {"es": "ñ¿¡", "pt": "ãõçê"}



def normalizar(texto: str | None) -> str:
    """Deja el texto en una forma estándar sin cambiar su sentido.

    - Convierte entidades HTML (&amp; -> &), que llegan en títulos de noticias.
    - Unifica tildes y caracteres (NFC) y quita caracteres invisibles o de control.
    - Junta espacios y saltos de línea repetidos en un solo espacio.
    - Conserva mayúsculas, signos y emojis: el modelo de sentimiento los usa.
    """
    if not texto:
        return ""
    texto = html.unescape(texto)
    texto = unicodedata.normalize("NFC", texto)
    texto = _RE_INVISIBLES.sub("", texto)
    texto = "".join(" " if unicodedata.category(c) == "Cc" else c for c in texto)
    return _RE_ESPACIOS.sub(" ", texto).strip()


def esta_vacio(texto: str) -> bool:
    """True si al texto no le queda nada visible (por ejemplo, solo uniones de emojis)."""
    return not _RE_SIN_CONTENIDO.sub("", texto)


def contar_urls(texto: str | None) -> int:
    """Cuántos enlaces tiene el texto original (lo usa la regla de bots)."""
    return len(_RE_URL.findall(texto or ""))


def enmascarar(texto: str) -> str:
    """Reemplaza enlaces y datos personales por marcadores (Ley 1581, Habeas Data).

    El orden importa: primero correos y enlaces (pueden tener números dentro),
    luego teléfonos y al final cualquier número largo que quede.
    """
    texto = _RE_CORREO.sub(CORREO, texto)
    texto = _RE_URL.sub(URL, texto)
    texto = _RE_CELULAR.sub(TELEFONO, texto)
    texto = _RE_FIJO.sub(TELEFONO, texto)
    return _RE_NUMERO_LARGO.sub(NUMERO, texto)


def limpiar_texto(texto: str | None) -> str:
    """Normaliza y enmascara. Es lo que se guarda en `texto_limpio`."""
    return enmascarar(normalizar(texto))


def clave_comparacion(texto_limpio: str) -> str:
    """Versión del texto para comparar si dos comentarios son 'el mismo'.

    Ignora mayúsculas, espacios, signos, emojis y marcadores, así
    "¡Gana dinero YA!" y "gana dinero ya" cuentan como el mismo texto.
    """
    sin_marcadores = _RE_MARCADORES.sub(" ", texto_limpio)
    return re.sub(r"[\W_]+", "", sin_marcadores.casefold())


def detectar_idioma(texto_limpio: str, idioma_consulta: str) -> str:
    """Idioma real del texto: 'es', 'pt', 'en' o el de la consulta.

    Cuenta cuántas palabras o letras propias de cada idioma tiene el texto:
    - si un idioma gana con claridad, es ese;
    - si no hay ninguna pista (textos como "excelente" o "jaja") o hay empate,
      se asume el idioma de la consulta, que es el que se pidió a la fuente.
    """
    minusculas = _RE_MARCADORES.sub(" ", texto_limpio).casefold()
    palabras = re.findall(r"[^\W\d_]+", minusculas)
    puntos = {idioma: sum(p in lista for p in palabras) for idioma, lista in _PALABRAS.items()}
    for idioma, letras in _LETRAS.items():
        puntos[idioma] += 2 * sum(minusculas.count(letra) for letra in letras)
    ordenados = sorted(puntos.items(), key=lambda par: par[1], reverse=True)
    (mejor, maximo), (_, segundo) = ordenados[0], ordenados[1]
    if maximo == 0 or maximo == segundo:
        return idioma_consulta
    return mejor
