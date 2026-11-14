"""El comando que corre el CI (make validar)."""

from quality import validar


def test_validar_con_datos_de_prueba_termina_bien():
    assert validar.main([]) == 0


def test_validar_detecta_un_archivo_correcto_que_falla(tmp_path, monkeypatch):
    # Simulación de que alguien daña un archivo "correcto", el comando debe terminar en 1.
    (tmp_path / "correctos").mkdir()
    (tmp_path / "incorrectos").mkdir()
    (tmp_path / "correctos" / "news.jsonl").write_text('{"fuente": "news"}\n', encoding="utf-8")
    monkeypatch.setattr(validar, "datos_prueba", tmp_path)
    assert validar.main([]) == 1