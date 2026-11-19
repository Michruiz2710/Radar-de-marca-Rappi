-- Sentimiento por día y fuente: cuántas menciones, cuántas positivas, neutras y negativas,
-- y el índice neto ((positivas - negativas) / analizadas), que va de -1 a 1.
select
    fecha,
    fuente,
    count(*) as menciones,
    count(*) filter (where analizada) as analizadas,
    count(*) filter (where sentimiento = 'positivo') as positivas,
    count(*) filter (where sentimiento = 'neutro') as neutras,
    count(*) filter (where sentimiento = 'negativo') as negativas,
    round(
        (count(*) filter (where sentimiento = 'negativo'))::numeric
        / nullif(count(*) filter (where analizada), 0), 4
    ) as pct_negativo,
    round(avg(puntaje_sentimiento)::numeric, 4) as indice_neto
from {{ ref('fct_menciones') }}
group by fecha, fuente
