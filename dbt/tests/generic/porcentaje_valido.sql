{# Falla si algún porcentaje queda fuera de 0 a 1 (los vacíos se permiten: sin datos para calcular). #}
{% test porcentaje_valido(model, column_name) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0 or {{ column_name }} > 1
{% endtest %}
