-- Ningún bot debe llegar a fct_menciones (contrato de la capa clean: el análisis se hace sin bots).
select f.id_registro
from {{ ref('fct_menciones') }} as f
join {{ ref('stg_menciones') }} as m on m.id_registro = f.id_registro
where m.es_bot
