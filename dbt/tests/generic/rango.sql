{# Falla si algún valor queda fuera de [minimo, maximo]. #}
{% test rango(model, column_name, minimo, maximo) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ minimo }} or {{ column_name }} > {{ maximo }}
{% endtest %}
