-- Una fila por fuente con los totales que el dashboard muestra arriba. Cuenta toda la historia de clean:
-- menciones, bots, cuántas tienen sentimiento vigente, cuántas nombran la marca
-- y cuántas entran a los demás modelos (sin bots, y dentro de dias_historia si se usa).
-- Es el único modelo final que cuenta bots, por eso lee de staging.
with menciones as (
    select * from {{ ref('stg_menciones') }}
),

sentimiento as (
    select id_registro, hash_texto_analizado from {{ ref('stg_sentimiento') }}
),

recientes as (
    select fuente, count(*) as en_modelos
    from {{ ref('fct_menciones') }}
    group by fuente
),

por_fuente as (
    select
        m.fuente,
        count(*) as menciones_total,
        count(*) filter (where m.es_bot) as bots,
        count(*) filter (where not m.es_bot) as reales,
        count(*) filter (where not m.es_bot and s.id_registro is not null) as analizadas,
        count(*) filter (where not m.es_bot and m.menciona_marca) as nombran_marca,
        min(m.fecha) as primera_fecha,
        max(m.fecha) as ultima_fecha
    from menciones as m
    left join sentimiento as s
        on s.id_registro = m.id_registro
        and s.hash_texto_analizado = m.hash_texto
    group by m.fuente
)

select
    p.fuente,
    p.menciones_total,
    p.bots,
    round(p.bots::numeric / p.menciones_total, 4) as pct_bots,
    p.analizadas,
    round(p.analizadas::numeric / nullif(p.reales, 0), 4) as pct_analizadas,
    round(p.nombran_marca::numeric / nullif(p.reales, 0), 4) as pct_menciona_marca,
    coalesce(r.en_modelos, 0) as en_modelos,
    p.primera_fecha,
    p.ultima_fecha,
    current_timestamp as actualizado_en
from por_fuente as p
left join recientes as r on r.fuente = p.fuente
