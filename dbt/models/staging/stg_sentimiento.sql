-- Resultado de sentimiento y tema (P2.4), con un puntaje numérico para promediar.
select
    id_registro,
    hash_texto as hash_texto_analizado,
    sentimiento,
    case sentimiento when 'positivo' then 1 when 'negativo' then -1 else 0 end as puntaje_sentimiento,
    prob_sentimiento,
    prob_positivo,
    prob_neutro,
    prob_negativo,
    tema,
    temas_detectados,
    version_modelo,
    version_nlp
from {{ source('clean', 'sentimiento') }}
