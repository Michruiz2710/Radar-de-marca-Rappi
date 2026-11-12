"""Pruebas de las métricas de evaluación (P2.4)."""

from src.transform.nlp.evaluacion import (
    acierto_entre_detectados,
    cruce_estrellas,
    evaluar,
    exactitud,
    f1_macro,
    generar_informe,
    matriz_confusion,
    metricas_por_clase,
    sentimiento_esperado_por_estrellas,
)
from src.transform.nlp.sentimiento import ResultadoSentimiento

CLASES = ("positivo", "neutro", "negativo")


def test_exactitud():
    assert exactitud(["a", "b", "c", "d"], ["a", "b", "x", "x"]) == 0.5
    assert exactitud([], []) == 0.0


def test_matriz_confusion_filas_reales_columnas_predichas():
    reales = ["positivo", "positivo", "negativo", "neutro"]
    pred = ["positivo", "negativo", "negativo", "negativo"]
    m = matriz_confusion(reales, pred, CLASES)
    assert m == [[1, 0, 1], [0, 0, 1], [0, 0, 1]]


def test_metricas_por_clase():
    m = [[1, 0, 1], [0, 0, 1], [0, 0, 1]]
    r = metricas_por_clase(m, CLASES)
    assert r["positivo"]["precision"] == 1.0 and r["positivo"]["exhaustividad"] == 0.5
    assert r["neutro"]["f1"] == 0.0 and r["neutro"]["soporte"] == 1
    assert round(r["negativo"]["precision"], 3) == 0.333


def test_f1_macro_pesa_igual_a_cada_clase():
    # positivo perfecto (F1 1.0) y neutro nunca acertado (F1 0.0): macro = 0.5, aunque la exactitud sea alta
    m = matriz_confusion(["positivo"] * 9 + ["neutro"], ["positivo"] * 10, CLASES)
    r = metricas_por_clase(m, CLASES)
    assert exactitud(["positivo"] * 9 + ["neutro"], ["positivo"] * 10) == 0.9
    assert round(f1_macro(r), 3) == round((r["positivo"]["f1"] + 0.0) / 2, 3)  # negativo sin soporte no cuenta
    assert f1_macro({}) == 0.0


def test_acierto_entre_detectados_es_mas_permisivo_que_la_exactitud():
    reales = ["app", "cobros_y_pagos", "otro", "otro", "soporte"]
    detectados = [
        ("entregas", "app"),  # el real está entre los detectados, aunque no sea el principal
        ("cobros_y_pagos",),
        (),  # otro sin ningún tema detectado: acierta
        ("app",),  # otro, pero se detectó un tema: no acierta
        (),  # soporte, no se detectó nada: no acierta
    ]
    assert acierto_entre_detectados(reales, detectados) == 0.6
    assert acierto_entre_detectados([], []) == 0.0


def test_estrellas_a_sentimiento():
    assert [sentimiento_esperado_por_estrellas(e) for e in (1, 2, 3, 4, 5)] == [
        "negativo", "negativo", "neutro", "positivo", "positivo",
    ]


def test_cruce_estrellas():
    c = cruce_estrellas([1, 1, 5], ["negativo", "positivo", "positivo"])
    assert c[1]["negativo"] == 1 and c[1]["positivo"] == 1 and c[5]["positivo"] == 1


class _Falso:
    version = "falso@1"

    def analizar(self, textos):
        return [ResultadoSentimiento("negativo", 0.9, 0.05, 0.05, 0.9) for _ in textos]


def test_evaluar_y_generar_informe():
    filas = [
        {"texto": "me cobraron doble", "sentimiento": "negativo", "tema": "cobros_y_pagos",
         "calificacion": "1", "etiquetado_por": "sara"},
        {"texto": "la mejor", "sentimiento": "positivo", "tema": "otro",
         "calificacion": "5", "etiquetado_por": "gabriel"},
    ]
    r = evaluar(filas, _Falso())
    assert r["texto"] == "original"
    assert r["sentimiento"]["exactitud"] == 0.5
    assert r["tema"]["exactitud"] == 1.0
    assert r["tema"]["entre_detectados"] == 1.0
    assert r["por_etiquetador"]["sara"]["tema_entre_detectados"] == 1.0
    assert r["estrellas"]["negativo_con_4_5_estrellas"] == 1
    informe = generar_informe(r)
    assert "falso@1" in informe and "Matriz de confusión" in informe
    assert "Tema real entre los detectados" in informe
    assert "Efecto de la limpieza" not in informe  # sin texto original para comparar


def test_evaluar_con_limpiador_y_comparar_con_el_original():
    filas = [
        {"texto": "  ME COBRARON   doble  ", "sentimiento": "negativo", "tema": "cobros_y_pagos",
         "calificacion": "1", "etiquetado_por": "sara"},
    ]
    vistos = []

    class Registra(_Falso):
        def analizar(self, textos):
            vistos.extend(textos)
            return super().analizar(textos)

    original = evaluar(filas, Registra())
    limpio = evaluar(filas, Registra(), limpiador=lambda t: " ".join(t.split()).lower())
    assert vistos == ["  ME COBRARON   doble  ", "me cobraron doble"]  # el limpiador se aplicó antes de analizar
    assert limpio["texto"] == "limpio"
    informe = generar_informe(limpio, original)
    assert "Efecto de la limpieza" in informe and "Texto original" in informe
