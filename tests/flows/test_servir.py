from flows import entornos, servir


def test_un_despliegue_por_fuente_mas_uno_manual():
    despliegues = servir.crear_despliegues(entornos.ENTORNOS["prod"])
    por_nombre = {d.name: d for d in despliegues}
    assert set(por_nombre) == {"google_play-prod", "youtube-prod", "news-prod", "todas-prod"}
    assert por_nombre["news-prod"].parameters == {"fuentes": ["news"]}
    horas = {n: d.schedules[0].schedule.interval.total_seconds() / 3600 for n, d in por_nombre.items() if d.schedules}
    assert horas == {"google_play-prod": 3, "youtube-prod": 6, "news-prod": 2}
    assert not por_nombre["todas-prod"].schedules
