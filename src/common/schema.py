"""Contrato de datos: el registro común que producen los 3 scrapers.

Cada reseña de Google Play, comentario de YouTube o publicación/comentario de
Reddit o noticia de Google News se convierte en
un RegistroMencion antes de guardarse. Si algún campo no cumple el contrato,
Pydantic lanza un error y el registro NO se guarda.

La explicación de cada campo está en docs/contrato_datos.md.

Ejemplo de uso en un scraper:

    from src.common.schema import RegistroMencion, Fuente
    from src.common.privacy import hash_autor

    registro = RegistroMencion(
        fuente=Fuente.GOOGLE_PLAY,
        id_original=review["reviewId"],
        texto=review["content"],
        fecha_publicacion=review["at"],
        autor_hash=hash_autor(review["userName"]),
        calificacion=review["score"],
        run_id=run_id,
        version_scraper="0.1.0",
    )
"""

from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

VERSION_CONTRATO = "1.2.0"

# Margen para diferencias de reloj entre servidores al validar fechas "futuras".
_MARGEN_RELOJ = timedelta(minutes=10)


class Fuente(str, Enum):
    """Valores permitidos para el campo `fuente`."""

    GOOGLE_PLAY = "google_play"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    NEWS = "news"


def _a_utc(valor: datetime) -> datetime:
    """Convierte una fecha a UTC. Una fecha sin zona horaria se asume UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class RegistroMencion(BaseModel):
    """Una mención de Rappi en cualquier fuente, ya anonimizada."""

    # extra="forbid": un campo que no está en el contrato es un error.
    # Así nadie guarda por accidente un nombre de usuario o una foto de perfil.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # --- Obligatorios en todas las fuentes ---
    fuente: Fuente
    id_original: str = Field(min_length=1)
    texto: str = Field(min_length=1)
    fecha_publicacion: datetime
    idioma: str = Field(default="es", pattern=r"^[a-z]{2}$")
    pais: str = Field(default="co", pattern=r"^[a-z]{2}$")
    fecha_extraccion: datetime = Field(default_factory=_ahora_utc)
    run_id: str = Field(min_length=1)
    version_scraper: str = Field(min_length=1)
    version_contrato: str = VERSION_CONTRATO

    # --- Opcionales según la fuente ---
    autor_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    calificacion: int | None = Field(default=None, ge=1, le=5)  # solo Google Play
    likes: int | None = Field(default=None, ge=0)
    version_app: str | None = None  # solo Google Play
    respuesta_marca: str | None = None  # solo Google Play
    # En Google Play, `fecha_publicacion` es la fecha de la versión ACTUAL de la
    # reseña: si el usuario la edita, Google Play actualiza esa fecha. Por eso una
    # respuesta de Rappi puede ser anterior a `fecha_publicacion` (ver
    # `editada_tras_respuesta`).
    fecha_respuesta: datetime | None = None  # solo Google Play
    id_contenedor: str | None = None  # ID del video (YouTube) o del post (comentario de Reddit)
    subreddit: str | None = None  # solo Reddit, sin el prefijo "r/"
    url: str | None = None  # YouTube, Reddit y noticias
    medio: str | None = None  # solo noticias: nombre del medio que publica

    @computed_field
    @property
    def id_registro(self) -> str:
        """ID único en todo el sistema: '<fuente>:<id_original>'."""
        return f"{self.fuente.value}:{self.id_original}"

    @computed_field
    @property
    def editada_tras_respuesta(self) -> bool | None:
        """True si la reseña se modificó después de que Rappi respondiera.

        - None: la reseña no tiene respuesta (no hay con qué comparar).
        - False: tiene respuesta y no se modificó después.
        - True: se modificó después de la respuesta.
        """
        if self.fecha_respuesta is None:
            return None
        return self.fecha_publicacion > self.fecha_respuesta

    @computed_field
    @property
    def fecha_edicion(self) -> datetime | None:
        """Fecha de la modificación posterior a la respuesta, si la hubo."""
        return self.fecha_publicacion if self.editada_tras_respuesta else None

    @field_validator("fecha_publicacion", "fecha_extraccion", "fecha_respuesta")
    @classmethod
    def _fechas_en_utc(cls, valor: datetime | None) -> datetime | None:
        return None if valor is None else _a_utc(valor)

    @field_validator("fecha_publicacion")
    @classmethod
    def _no_futura(cls, valor: datetime) -> datetime:
        if valor > _ahora_utc() + _MARGEN_RELOJ:
            raise ValueError("fecha_publicacion no puede estar en el futuro")
        return valor

    @field_validator("subreddit", mode="before")
    @classmethod
    def _sin_prefijo(cls, valor):
        # "r/Colombia" y "Colombia" se guardan igual: "colombia"
        if isinstance(valor, str):
            return valor.strip().removeprefix("r/").removeprefix("/r/").lower() or None
        return valor

    @field_validator("idioma", "pais", mode="before")
    @classmethod
    def _minusculas(cls, valor):
        return valor.lower() if isinstance(valor, str) else valor

    @model_validator(mode="after")
    def _reglas_por_fuente(self) -> "RegistroMencion":
        """Campos que solo tienen sentido en una fuente."""
        if self.fuente != Fuente.GOOGLE_PLAY:
            for campo in ("calificacion", "version_app", "respuesta_marca", "fecha_respuesta"):
                if getattr(self, campo) is not None:
                    raise ValueError(f"'{campo}' solo aplica a google_play")
        if self.fuente != Fuente.REDDIT and self.subreddit is not None:
            raise ValueError("'subreddit' solo aplica a reddit")
        if self.fuente != Fuente.NEWS and self.medio is not None:
            raise ValueError("'medio' solo aplica a news")
        return self

    def a_json(self) -> str:
        """Una línea JSON con fechas en ISO 8601, lista para JSON Lines."""
        return self.model_dump_json()
