"""Evaluación del sentimiento y los temas contra las 200 reseñas etiquetadas (P2.4).

Calcula exactitud, precisión/exhaustividad/F1 por clase y matriz de confusión, y compara el
sentimiento del modelo con las estrellas. Escribe un informe en Markdown (por defecto
docs/evaluacion_nlp.md).

    python -m src.transform.nlp.evaluacion [--muestra data/etiquetas/muestra_200.csv]
                                           [--salida docs/evaluacion_nlp.md]

Aviso: la muestra no es representativa (ver data/etiquetas/README.md). El texto se pasa antes por
`limpiar_texto` de P2.3, igual que en el pipeline real, y el informe compara con el texto original.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from src.transform.clean.texto import limpiar_texto
from src.transform.nlp import config
from src.transform.nlp.temas import TEMA_OTRO, TEMAS_VALIDOS, clasificar_tema

SENTIMIENTOS = ("positivo", "neutro", "negativo")
RUTA_MUESTRA = Path("data/etiquetas/muestra_200.csv")
RUTA_INFORME = Path("docs/evaluacion_nlp.md")


# --- Métricas (funciones puras, sin modelo) ------------------------------------------------


def exactitud(reales: Sequence[str], predichos: Sequence[str]) -> float:
    if not reales:
        return 0.0
    return sum(1 for r, p in zip(reales, predichos, strict=True) if r == p) / len(reales)


def matriz_confusion(
    reales: Sequence[str], predichos: Sequence[str], clases: Sequence[str]
) -> list[list[int]]:
    """Filas = etiqueta real, columnas = predicción, en el orden de `clases`."""
    indice = {c: i for i, c in enumerate(clases)}
    matriz = [[0] * len(clases) for _ in clases]
    for r, p in zip(reales, predichos, strict=True):
        matriz[indice[r]][indice[p]] += 1
    return matriz


def metricas_por_clase(matriz: list[list[int]], clases: Sequence[str]) -> dict[str, dict[str, float]]:
    resultado = {}
    for i, clase in enumerate(clases):
        vp = matriz[i][i]
        predichos = sum(fila[i] for fila in matriz)
        reales = sum(matriz[i])
        precision = vp / predichos if predichos else 0.0
        exhaustividad = vp / reales if reales else 0.0
        f1 = (
            2 * precision * exhaustividad / (precision + exhaustividad)
            if precision + exhaustividad
            else 0.0
        )
        resultado[clase] = {
            "precision": precision, "exhaustividad": exhaustividad, "f1": f1, "soporte": reales,
        }
    return resultado


def acierto_entre_detectados(
    reales: Sequence[str], detectados: Sequence[Sequence[str]]
) -> float:
    """Métrica permisiva: el tema real está entre TODOS los temas que el diccionario detectó.

    Una reseña suele mencionar varios temas y la guía pide elegir el que la motivó, algo que un
    diccionario no puede saber. Aquí se acepta que el tema real aparezca entre los detectados.
    `otro` acierta solo si no se detectó ningún tema. Es más generosa que la exactitud: úsala
    como complemento, no como reemplazo.
    """
    if not reales:
        return 0.0
    aciertos = sum(
        1
        for real, d in zip(reales, detectados, strict=True)
        if (real == TEMA_OTRO and not d) or (real != TEMA_OTRO and real in d)
    )
    return aciertos / len(reales)


def f1_macro(por_clase: dict[str, dict[str, float]]) -> float:
    """Promedio simple del F1 de cada clase con ejemplos reales: todas pesan igual.

    Con clases desiguales (140 negativas, 18 neutras) es más honesto que la exactitud,
    porque una clase pequeña mal clasificada baja este número y apenas mueve la exactitud.
    """
    f1s = [m["f1"] for m in por_clase.values() if m["soporte"] > 0]
    return sum(f1s) / len(f1s) if f1s else 0.0


def sentimiento_esperado_por_estrellas(estrellas: int) -> str:
    """1-2 estrellas negativo, 3 neutro, 4-5 positivo (regla simple para comparar)."""
    return "negativo" if estrellas <= 2 else "neutro" if estrellas == 3 else "positivo"


def cruce_estrellas(estrellas: Sequence[int], sentimientos: Sequence[str]) -> dict[int, Counter]:
    cruce: dict[int, Counter] = defaultdict(Counter)
    for e, s in zip(estrellas, sentimientos, strict=True):
        cruce[e][s] += 1
    return dict(cruce)


# --- Evaluación ----------------------------------------------------------------------------


def cargar_muestra(ruta: Path = RUTA_MUESTRA) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def evaluar(filas: list[dict[str, str]], analizador, limpiador=None) -> dict:
    """Evalúa la muestra. Con `limpiador`, cada texto se limpia antes de analizarlo."""
    textos = [limpiador(f["texto"]) if limpiador else f["texto"] for f in filas]
    sent_real = [f["sentimiento"] for f in filas]
    sent_pred = [r.sentimiento for r in analizador.analizar(textos)]
    tema_real = [f["tema"] for f in filas]
    temas = [clasificar_tema(t) for t in textos]
    tema_pred = [t.tema for t in temas]
    tema_detectados = [t.temas_detectados for t in temas]
    estrellas = [int(f["calificacion"]) for f in filas]

    m_sent = matriz_confusion(sent_real, sent_pred, SENTIMIENTOS)
    m_tema = matriz_confusion(tema_real, tema_pred, TEMAS_VALIDOS)

    por_etiquetador = {}
    for quien in sorted({f["etiquetado_por"] for f in filas}):
        idx = [i for i, f in enumerate(filas) if f["etiquetado_por"] == quien]
        por_etiquetador[quien] = {
            "n": len(idx),
            "exactitud_sentimiento": exactitud([sent_real[i] for i in idx], [sent_pred[i] for i in idx]),
            "exactitud_tema": exactitud([tema_real[i] for i in idx], [tema_pred[i] for i in idx]),
            "tema_entre_detectados": acierto_entre_detectados(
                [tema_real[i] for i in idx], [tema_detectados[i] for i in idx]
            ),
        }

    por_clase_sent = metricas_por_clase(m_sent, SENTIMIENTOS)
    por_clase_tema = metricas_por_clase(m_tema, TEMAS_VALIDOS)
    esperado = [sentimiento_esperado_por_estrellas(e) for e in estrellas]
    return {
        "n": len(filas),
        "texto": "limpio" if limpiador else "original",
        "version_modelo": analizador.version,
        "version_nlp": config.VERSION_NLP,
        "sentimiento": {
            "exactitud": exactitud(sent_real, sent_pred),
            "f1_macro": f1_macro(por_clase_sent),
            "matriz": m_sent,
            "por_clase": por_clase_sent,
        },
        "tema": {
            "exactitud": exactitud(tema_real, tema_pred),
            "f1_macro": f1_macro(por_clase_tema),
            "entre_detectados": acierto_entre_detectados(tema_real, tema_detectados),
            "matriz": m_tema,
            "por_clase": por_clase_tema,
        },
        "por_etiquetador": por_etiquetador,
        "estrellas": {
            "cruce": cruce_estrellas(estrellas, sent_pred),
            "concordancia_modelo": exactitud(esperado, sent_pred),
            "concordancia_etiquetas": exactitud(esperado, sent_real),
            "positivo_con_1_2_estrellas": sum(
                1 for e, s in zip(estrellas, sent_pred, strict=True) if e <= 2 and s == "positivo"
            ),
            "negativo_con_4_5_estrellas": sum(
                1 for e, s in zip(estrellas, sent_pred, strict=True) if e >= 4 and s == "negativo"
            ),
        },
    }


# --- Informe -------------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def _tabla_matriz(matriz: list[list[int]], clases: Sequence[str]) -> str:
    cab = "| real \\ predicho | " + " | ".join(clases) + " |"
    sep = "| --- |" + " --- |" * len(clases)
    filas = [f"| **{c}** | " + " | ".join(str(v) for v in matriz[i]) + " |" for i, c in enumerate(clases)]
    return "\n".join([cab, sep, *filas])


def _tabla_clases(por_clase: dict[str, dict[str, float]]) -> str:
    filas = ["| Clase | Precisión | Exhaustividad | F1 | Soporte |", "| --- | --- | --- | --- | --- |"]
    for clase, m in por_clase.items():
        filas.append(
            f"| {clase} | {_pct(m['precision'])} | {_pct(m['exhaustividad'])} | {_pct(m['f1'])} | {m['soporte']} |"
        )
    return "\n".join(filas)


def generar_informe(r: dict, r_original: dict | None = None) -> str:
    est = r["estrellas"]
    cruce_filas = ["| Estrellas | positivo | neutro | negativo |", "| --- | --- | --- | --- |"]
    for e in sorted(est["cruce"]):
        c = est["cruce"][e]
        cruce_filas.append(f"| {e} | {c['positivo']} | {c['neutro']} | {c['negativo']} |")
    etiquetadores = [
        "| Etiquetó | Reseñas | Exactitud sentimiento | Exactitud tema | Tema real entre los detectados |",
        "| --- | --- | --- | --- | --- |",
    ]
    for quien, m in r["por_etiquetador"].items():
        etiquetadores.append(
            f"| {quien} | {m['n']} | {_pct(m['exactitud_sentimiento'])} | {_pct(m['exactitud_tema'])} "
            f"| {_pct(m['tema_entre_detectados'])} |"
        )
    efecto = ""
    if r_original is not None:
        def fila(nombre, a, b):
            return f"| {nombre} | {_pct(a)} | {_pct(b)} |"

        efecto = f"""
## Efecto de la limpieza (P2.3)

Misma muestra y mismo modelo; cambia solo el texto que se analiza.

| Métrica | Texto original | Texto limpio |
| --- | --- | --- |
{fila("Sentimiento: exactitud", r_original["sentimiento"]["exactitud"], r["sentimiento"]["exactitud"])}
{fila("Sentimiento: F1 macro", r_original["sentimiento"]["f1_macro"], r["sentimiento"]["f1_macro"])}
{fila("Temas: exactitud", r_original["tema"]["exactitud"], r["tema"]["exactitud"])}
{fila("Temas: F1 macro", r_original["tema"]["f1_macro"], r["tema"]["f1_macro"])}
{fila("Temas: real entre los detectados", r_original["tema"]["entre_detectados"], r["tema"]["entre_detectados"])}
"""
    return f"""# Evaluación de sentimiento y temas (P2.4)

Generado el {datetime.now(UTC).date().isoformat()} con `python -m src.transform.nlp.evaluacion`.

- **Modelo:** `{r['version_modelo']}`
- **Versión del código NLP:** {r['version_nlp']}
- **Reseñas evaluadas:** {r['n']} (`data/etiquetas/muestra_200.csv`)
- **Texto evaluado:** {r['texto']} (`limpiar_texto` de P2.3 es lo que analiza el pipeline)

## Cómo leer estas cifras

- La muestra **no es representativa** de la app (140 negativas, 42 positivas, 18 neutras): la
  exactitud global dice poco de las clases pequeñas. Mira la tabla por clase.
- **F1 macro** es el promedio del F1 de cada clase, todas con el mismo peso. Si es mucho más bajo que
  la exactitud, alguna clase pequeña está fallando aunque el total se vea bien.
- **Tema real entre los detectados** acepta el acierto si el tema etiquetado aparece entre todos los
  temas que el diccionario encontró, no solo como principal. Una reseña suele hablar de varios temas
  y la guía pide elegir el que la motivó, algo que un diccionario no puede saber. Es más generosa que
  la exactitud: se reporta como complemento, no como reemplazo. `otro` acierta solo si no se detectó nada.
- El diccionario de temas se ajustó mirando solo las filas 2 a 101 (etiquetó Sara). Las filas
  102 a 201 (Gabriel) no se usaron para ajustarlo; es la cifra que mejor estima el desempeño real.

## Sentimiento

**Exactitud: {_pct(r['sentimiento']['exactitud'])} · F1 macro: {_pct(r['sentimiento']['f1_macro'])}**

{_tabla_clases(r['sentimiento']['por_clase'])}

Matriz de confusión:

{_tabla_matriz(r['sentimiento']['matriz'], SENTIMIENTOS)}

## Temas (diccionario de palabras clave)

**Exactitud: {_pct(r['tema']['exactitud'])} · F1 macro: {_pct(r['tema']['f1_macro'])}**

**Tema real entre los detectados: {_pct(r['tema']['entre_detectados'])}** (métrica permisiva, ver arriba).

{_tabla_clases(r['tema']['por_clase'])}

Matriz de confusión:

{_tabla_matriz(r['tema']['matriz'], TEMAS_VALIDOS)}

## Por quién etiquetó

{chr(10).join(etiquetadores)}

## Sentimiento frente a estrellas

Regla de comparación: 1-2 estrellas = negativo, 3 = neutro, 4-5 = positivo.

{chr(10).join(cruce_filas)}

- Coincidencia entre el modelo y la regla de estrellas: **{_pct(est['concordancia_modelo'])}**.
- Coincidencia entre las etiquetas humanas y la misma regla: **{_pct(est['concordancia_etiquetas'])}**
  (referencia: así de lejos queda el humano de las estrellas).
- Reseñas de 1-2 estrellas que el modelo ve positivas: {est['positivo_con_1_2_estrellas']}.
- Reseñas de 4-5 estrellas que el modelo ve negativas: {est['negativo_con_4_5_estrellas']}.
{efecto}"""


def main() -> None:
    from src.transform.nlp.sentimiento import AnalizadorSentimiento

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--muestra", type=Path, default=RUTA_MUESTRA)
    parser.add_argument("--salida", type=Path, default=RUTA_INFORME)
    args = parser.parse_args()

    filas = cargar_muestra(args.muestra)
    analizador = AnalizadorSentimiento()
    original = evaluar(filas, analizador)
    resultado = evaluar(filas, analizador, limpiador=limpiar_texto)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(generar_informe(resultado, original), encoding="utf-8")
    print(f"Sentimiento: {_pct(resultado['sentimiento']['exactitud'])} (F1 macro {_pct(resultado['sentimiento']['f1_macro'])}) | "
          f"Tema: {_pct(resultado['tema']['exactitud'])} | informe: {args.salida}")


if __name__ == "__main__":
    main()
