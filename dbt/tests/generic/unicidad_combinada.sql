{# Falla si una combinación de columnas se repite (por ejemplo, fecha + fuente). #}
{% test unicidad_combinada(model, columnas) %}
select {{ columnas | join(', ') }}, count(*) as veces
from {{ model }}
group by {{ columnas | join(', ') }}
having count(*) > 1
{% endtest %}
