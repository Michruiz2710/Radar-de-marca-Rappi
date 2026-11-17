-- Temas por fuente y semana. Ordenando por negativas sale el "top de quejas".
select
    semana,
    fuente,
    tema,
    count(*) as menciones,
    count(*) filter (where sentimiento = 'negativo') as negativas,
    round(
        (count(*) filter (where sentimiento = 'negativo'))::numeric / count(*), 4
    ) as pct_negativo,
    round(avg(calificacion)::numeric, 2) as calificacion_promedio
from {{ ref('fct_menciones') }}
where analizada
group by semana, fuente, tema
