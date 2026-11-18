-- Google Play: cuánto y qué tan rápido responde Rappi, por semana.
-- Se separan las reseñas de 1 y 2 estrellas, que son las que más importa responder.
-- La mediana de horas solo puede usar las respuestas a reseñas no editadas: en las editadas
-- Google Play pierde la fecha original. respondidas_con_tiempo dice sobre cuántas se calculó.
select
    semana,
    count(*) as resenas,
    count(*) filter (where tiene_respuesta) as respondidas,
    round((count(*) filter (where tiene_respuesta))::numeric / count(*), 4) as tasa_respuesta,
    count(*) filter (where calificacion <= 2) as resenas_1_2_estrellas,
    round(
        (count(*) filter (where calificacion <= 2 and tiene_respuesta))::numeric
        / nullif(count(*) filter (where calificacion <= 2), 0), 4
    ) as tasa_respuesta_1_2_estrellas,
    count(*) filter (where horas_hasta_respuesta is not null) as respondidas_con_tiempo,
    count(*) filter (where tiene_respuesta and editada_tras_respuesta) as respondidas_editadas,
    round((percentile_cont(0.5) within group (order by horas_hasta_respuesta))::numeric, 1) as horas_mediana_respuesta
from {{ ref('fct_menciones') }}
where fuente = 'google_play'
group by semana
