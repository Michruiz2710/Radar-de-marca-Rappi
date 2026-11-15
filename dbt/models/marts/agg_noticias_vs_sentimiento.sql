-- Cruce por día entre noticias publicadas sobre Rappi y el sentimiento en redes y reseñas.
-- Sirve para ver si una noticia coincide con un pico de menciones negativas.
with dias as (
    select fecha from {{ ref('fct_menciones') }}
    group by fecha
),

noticias as (
    select
        fecha,
        count(*) as noticias,
        string_agg(distinct medio, ', ' order by medio) as medios
    from {{ ref('fct_menciones') }}
    where fuente = 'news'
    group by fecha
),

social as (
    select
        fecha,
        count(*) as menciones_social,
        count(*) filter (where sentimiento = 'negativo') as negativas_social,
        round(
            (count(*) filter (where sentimiento = 'negativo'))::numeric
            / nullif(count(*) filter (where analizada), 0), 4
        ) as pct_negativo_social
    from {{ ref('fct_menciones') }}
    where fuente <> 'news'
    group by fecha
)

select
    d.fecha,
    coalesce(n.noticias, 0) as noticias,
    n.medios,
    coalesce(s.menciones_social, 0) as menciones_social,
    coalesce(s.negativas_social, 0) as negativas_social,
    s.pct_negativo_social
from dias as d
left join noticias as n on n.fecha = d.fecha
left join social as s on s.fecha = d.fecha
