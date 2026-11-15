-- Google Play: cuánto y qué tan rápido responde Rappi, por semana.
-- Se separan las reseñas de 1 y 2 estrellas, que son las que más importa responder.
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
    percentile_cont(0.5) within group (order by horas_hasta_respuesta) as horas_mediana_respuesta
from {{ ref('fct_menciones') }}
where fuente = 'google_play'
group by semana
