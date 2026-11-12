"""Sentimiento en español con pysentimiento (RoBERTuito), P2.4.

pysentimiento y torch se importan solo al usarlos (`_cargar`), así que importar este módulo
es barato y las pruebas pueden pasar un analizador falso.

Ejemplo:

    from src.transform.nlp.sentimiento import AnalizadorSentimiento

    resultados = AnalizadorSentimiento().analizar(["Llegó rápido", "Pésimo servicio"])
    resultados[0].sentimiento   # "positivo"
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.transform.nlp import config

# pysentimiento devuelve POS, NEU y NEG; el proyecto usa los nombres de la guía de etiquetado.
ETIQUETAS = {"POS": "positivo", "NEU": "neutro", "NEG": "negativo"}


@dataclass(frozen=True)
class ResultadoSentimiento:
    sentimiento: str  # positivo | neutro | negativo
    probabilidad: float  # probabilidad de la clase elegida
    prob_positivo: float
    prob_neutro: float
    prob_negativo: float


def _a_resultado(salida: Any) -> ResultadoSentimiento:
    """Convierte un AnalyzerOutput de pysentimiento (output + probas) en nuestro resultado."""
    probas = {ETIQUETAS[k]: float(v) for k, v in salida.probas.items()}
    sentimiento = ETIQUETAS[salida.output]
    return ResultadoSentimiento(
        sentimiento=sentimiento,
        probabilidad=probas[sentimiento],
        prob_positivo=probas.get("positivo", 0.0),
        prob_neutro=probas.get("neutro", 0.0),
        prob_negativo=probas.get("negativo", 0.0),
    )


class AnalizadorSentimiento:
    """Envuelve el analizador de pysentimiento. El modelo se carga la primera vez que se usa."""

    def __init__(self, analizador: Any | None = None) -> None:
        self._analizador = analizador

    @property
    def version(self) -> str:
        """Modelo + revisión + versión de la librería, para guardar junto a cada resultado."""
        return config.version_modelo()

    def _cargar(self) -> Any:
        if self._analizador is None:
            from pysentimiento import create_analyzer  # import tardío: arrastra torch

            self._analizador = create_analyzer(task="sentiment", lang="es")
        return self._analizador

    def analizar(
        self, textos: Iterable[str], tamano_lote: int | None = None
    ) -> list[ResultadoSentimiento]:
        """Un resultado por texto, en el mismo orden. Procesa por lotes para limitar la memoria."""
        textos = list(textos)
        if not textos:
            return []
        tamano = tamano_lote or config.tamano_lote()
        analizador = self._cargar()
        resultados: list[ResultadoSentimiento] = []
        for inicio in range(0, len(textos), tamano):
            lote = textos[inicio : inicio + tamano]
            salidas = analizador.predict(lote)
            if not isinstance(salidas, list):  # un solo texto devuelve un solo objeto
                salidas = [salidas]
            resultados.extend(_a_resultado(s) for s in salidas)
        return resultados
