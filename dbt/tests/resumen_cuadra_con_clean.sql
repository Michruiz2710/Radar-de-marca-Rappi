-- El total de resumen_fuentes debe ser igual al número de filas de clean.menciones: no se pierde nada en el camino.
select 1
where (select coalesce(sum(menciones_total), 0) from {{ ref('resumen_fuentes') }})
   <> (select count(*) from {{ source('clean', 'menciones') }})
