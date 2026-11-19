-- Google Play: estrellas y sentimiento por versión de la app (8.41, 8.42...).
-- Sirve para ver si una versión nueva empeoró la experiencia.
-- muestra_suficiente marca las versiones con pocas reseñas, que el dashboard no debería comparar.
select
    version_app_corta as version_app,
    split_part(version_app_corta, '.', 1)::int * 1000
        + split_part(version_app_corta, '.', 2)::int as orden_version,
    count(*) as resenas,
    count(distinct version_app) as builds,
    count(*) >= {{ var('min_resenas_version') }} as muestra_suficiente,
    round(avg(calificacion)::numeric, 2) as calificacion_promedio,
    round((count(*) filter (where calificacion <= 2))::numeric / count(*), 4) as pct_1_2_estrellas,
    round(
        (count(*) filter (where sentimiento = 'negativo'))::numeric
        / nullif(count(*) filter (where analizada), 0), 4
    ) as pct_negativo,
    min(fecha) as primera_resena,
    max(fecha) as ultima_resena
from {{ ref('fct_menciones') }}
where fuente = 'google_play'
    and version_app_corta is not null
group by version_app_corta
