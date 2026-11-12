"""Prueba rota a propósito para mostrar que main bloquea un PR con el CI en rojo (P2.5). NO FUSIONAR."""


def test_falla_a_proposito():
    assert 1 + 1 == 3
