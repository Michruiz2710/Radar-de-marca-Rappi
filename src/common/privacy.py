"""Privacidad: seudonimización de autores (Ley 1581 de 2012, Habeas Data).

Nunca guardamos el nombre de quien escribe una reseña o un comentario.
En su lugar guardamos un hash SHA-256 calculado con una "sal" secreta:

    autor_hash = SHA-256(sal + nombre_normalizado)

- El mismo autor siempre produce el mismo hash, así podemos detectar bots
  (muchos comentarios del mismo autor) sin saber quién es.
- Sin la sal no se puede reconstruir el nombre probando nombres comunes.
- La sal vive solo en el archivo .env (variable HASH_SALT), nunca en Git.
"""

import hashlib
import os
import unicodedata

# Valor de ejemplo de .env.example: si alguien lo deja así, lo rechazamos.
_SAL_DE_EJEMPLO = "cambiar_por_cadena_aleatoria"


class SalNoConfiguradaError(RuntimeError):
    """La variable HASH_SALT no existe, está vacía o tiene el valor de ejemplo."""


def _obtener_sal(sal: str | None = None) -> str:
    """Devuelve la sal recibida o, si no se pasa, la lee de HASH_SALT."""
    sal = sal if sal is not None else os.getenv("HASH_SALT", "")
    if not sal or sal == _SAL_DE_EJEMPLO:
        raise SalNoConfiguradaError(
            "Configura HASH_SALT en tu archivo .env con una cadena larga y aleatoria."
        )
    return sal


def _normalizar(nombre: str) -> str:
    """Quita espacios sobrantes, pasa a minúsculas y unifica tildes.

    Así "Ana María", " ana maría " y "ANA MARÍA" producen el mismo hash.
    """
    nombre = unicodedata.normalize("NFC", nombre)
    return " ".join(nombre.split()).casefold()


def hash_autor(nombre: str | None, sal: str | None = None) -> str | None:
    """Convierte el nombre de un autor en un hash de 64 caracteres hexadecimales.

    Devuelve None si no hay autor (por ejemplo, en las noticias).

    >>> hash_autor("Ana María", sal="sal-de-prueba") == hash_autor(" ana maría ", sal="sal-de-prueba")
    True
    """
    if nombre is None or not nombre.strip():
        return None
    texto = _obtener_sal(sal) + _normalizar(nombre)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
