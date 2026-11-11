"""Pruebas del envoltorio de sentimiento, con un analizador falso (sin torch)."""

from types import SimpleNamespace

from src.transform.nlp.sentimiento import AnalizadorSentimiento


class FalsoPysentimiento:
    def __init__(self):
        self.llamadas = []

    def predict(self, textos):
        self.llamadas.append(list(textos))
        salida = []
        for t in textos:
            if "malo" in t:
                salida.append(SimpleNamespace(output="NEG", probas={"POS": 0.1, "NEU": 0.1, "NEG": 0.8}))
            else:
                salida.append(SimpleNamespace(output="POS", probas={"POS": 0.9, "NEU": 0.05, "NEG": 0.05}))
        return salida


def test_traduce_etiquetas_y_probabilidades():
    r = AnalizadorSentimiento(FalsoPysentimiento()).analizar(["muy bueno", "muy malo"])
    assert [x.sentimiento for x in r] == ["positivo", "negativo"]
    assert r[0].probabilidad == 0.9 and r[1].probabilidad == 0.8
    assert (r[1].prob_positivo, r[1].prob_neutro, r[1].prob_negativo) == (0.1, 0.1, 0.8)


def test_procesa_por_lotes_y_conserva_el_orden():
    falso = FalsoPysentimiento()
    textos = [f"texto {i}" for i in range(5)]
    r = AnalizadorSentimiento(falso).analizar(textos, tamano_lote=2)
    assert [len(lote) for lote in falso.llamadas] == [2, 2, 1]
    assert len(r) == 5


def test_lista_vacia_no_carga_el_modelo():
    assert AnalizadorSentimiento().analizar([]) == []


def test_un_solo_resultado_se_envuelve_en_lista():
    class UnSolo:
        def predict(self, textos):
            return SimpleNamespace(output="NEU", probas={"POS": 0.2, "NEU": 0.6, "NEG": 0.2})

    r = AnalizadorSentimiento(UnSolo()).analizar(["hola"])
    assert r[0].sentimiento == "neutro"
