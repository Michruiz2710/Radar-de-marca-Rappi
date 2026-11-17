-- Una fila por mención real (sin bots), con su sentimiento y tema cuando están vigentes.
-- Es la tabla base del dashboard (P3.3) y de los demás modelos.
-- Vigente = se analizó el mismo texto que hay hoy en menciones (si la reseña se editó, se espera el nuevo análisis).
-- Por defecto entra toda la historia; con la var dias_historia se puede dejar solo lo reciente.
with menciones as (
    select * from {{ ref('stg_menciones') }}
    where not es_bot
        {% if var('dias_historia') | int > 0 %}
        and fecha >= current_date - {{ var('dias_historia') | int }}
        {% endif %}
),

sentimiento as (
    select * from {{ ref('stg_sentimiento') }}
)

select
    m.id_registro,
    m.fuente,
    m.fecha,
    m.semana,
    m.fecha_publicacion,
    m.texto_limpio,
    m.idioma_detectado,
    m.calificacion,
    m.likes,
    m.version_app,
    m.version_app_corta,
    m.tiene_respuesta,
    m.editada_tras_respuesta,
    m.horas_hasta_respuesta,
    m.medio,
    m.id_contenedor,
    m.menciona_marca,
    s.id_registro is not null as analizada,
    s.sentimiento,
    s.puntaje_sentimiento,
    s.prob_sentimiento,
    s.prob_negativo,
    coalesce(s.tema, 'sin_analizar') as tema,
    s.temas_detectados,
    s.version_modelo
from menciones as m
left join sentimiento as s
    on s.id_registro = m.id_registro
    and s.hash_texto_analizado = m.hash_texto
