-- Menciones de la capa clean con los campos que usan los modelos y el día en hora de Colombia.
-- No filtra bots: eso se decide en cada modelo final (resumen_fuentes los cuenta, los demás los quitan).
with fuente as (
    select * from {{ source('clean', 'menciones') }}
)

select
    id_registro,
    fuente,
    texto_limpio,
    hash_texto,
    idioma_detectado,
    fecha_publicacion,
    (fecha_publicacion at time zone '{{ var("zona_horaria") }}')::date as fecha,
    date_trunc('week', fecha_publicacion at time zone '{{ var("zona_horaria") }}')::date as semana,
    calificacion,
    likes,
    nullif(trim(version_app), '') as version_app,
    -- Google Play publica un build por día (8.42.20261030-90052); para comparar se agrupa por 8.42
    substring(version_app from '^[0-9]+\.[0-9]+') as version_app_corta,
    respuesta_marca is not null as tiene_respuesta,
    fecha_respuesta,
    -- Horas entre la reseña y la respuesta de Rappi. Si la reseña se editó después de la respuesta,
    -- Google Play solo guarda la fecha de la edición y se pierde la original (docs/contrato_datos.md,
    -- "Reseñas editadas"): ahí no se puede calcular y queda vacío. agg_respuesta_marca_semanal
    -- cuenta esas respuestas aparte para que se sepa sobre cuántas se calcula la mediana.
    case
        when fecha_respuesta is not null and not coalesce(editada_tras_respuesta, false)
            then round(extract(epoch from fecha_respuesta - fecha_publicacion) / 3600.0, 1)
    end as horas_hasta_respuesta,
    editada_tras_respuesta,
    medio,
    id_contenedor,
    -- Relevancia: si el texto nombra a la marca. En YouTube el filtro es por video, así que
    -- muchos comentarios hablan de Rappi sin nombrarla; esto lo mide (ver README de YouTube).
    texto_limpio ~* '\mrappi' as menciona_marca,
    es_bot,
    motivo_bot,
    run_id,
    version_limpieza
from fuente
