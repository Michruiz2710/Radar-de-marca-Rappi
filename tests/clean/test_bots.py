"""Pruebas de las reglas de bots y spam."""

from datetime import datetime, timedelta, timezone

from src.transform.clean.bots import marcar_bots
from src.transform.clean.texto import clave_comparacion

T0 = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def fila(id_, texto="un comentario normal sobre el pedido", autor="a", fuente="youtube", n_urls=0, minutos=0):
    return {
        "id_registro": id_,
        "fuente": fuente,
        "autor_hash": autor,
        "clave": clave_comparacion(texto),
        "n_urls": n_urls,
        "texto_limpio": texto,
        "texto_original": texto,
        "fecha_publicacion": T0 + timedelta(minutes=minutos),
    }


def test_comentario_normal_no_es_bot():
    assert marcar_bots([fila("1"), fila("2", autor="b", minutos=60)]) == {}


def test_dos_o_mas_enlaces():
    assert marcar_bots([fila("1", n_urls=2)]) == {"1": ["multiples_enlaces"]}
    assert marcar_bots([fila("1", n_urls=1)]) == {}


def test_frase_promocional():
    assert marcar_bots([fila("1", texto="Gana dinero desde tu celular, visita mi canal")]) == {"1": ["promocional"]}


def test_whatsapp_en_una_queja_no_es_spam():
    assert marcar_bots([fila("1", texto="no responden por WhatsApp, pésimo")]) == {}


def test_mismo_autor_mismo_texto():
    resultado = marcar_bots([fila("1", texto="Rappi es lo peor"), fila("2", texto="RAPPI es lo peor!!", minutos=90)])
    assert resultado == {"1": ["texto_repetido_autor"], "2": ["texto_repetido_autor"]}


def test_frase_generica_de_varios_autores_no_es_campana():
    # Muchas personas reales escriben reseñas genéricas iguales
    for texto in ["excelente", "Pésimo servicio, el pedido llegó frío"]:
        filas = [fila(str(i), texto=texto, autor=str(i), minutos=30 * i) for i in range(5)]
        assert marcar_bots(filas) == {}


def test_mismo_texto_largo_de_tres_autores_es_campana():
    texto = "Descarga la app con mi código y gana bonos gratis en cada pedido que hagas"
    filas = [fila(str(i), texto=texto, autor=str(i), minutos=30 * i) for i in range(3)]
    assert all(m == ["campana_varios_autores"] for m in marcar_bots(filas).values())
    assert len(marcar_bots(filas)) == 3


def test_rafaga_de_cinco_en_diez_minutos():
    filas = [fila(str(i), texto=f"comentario numero {i} distinto", minutos=2 * i) for i in range(5)]
    assert set(marcar_bots(filas)) == {"0", "1", "2", "3", "4"}


def test_cinco_comentarios_espaciados_no_son_rafaga():
    filas = [fila(str(i), texto=f"comentario numero {i} distinto", minutos=3 * i) for i in range(5)]
    assert marcar_bots(filas) == {}


def test_las_noticias_nunca_son_bots():
    filas = [fila("n1", fuente="news", autor=None, n_urls=3, texto="Gana dinero fácil")]
    assert marcar_bots(filas) == {}
