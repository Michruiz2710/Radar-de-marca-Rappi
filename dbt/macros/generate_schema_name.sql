{# Todos los modelos van al esquema del entorno (PG_SCHEMA_ANALYTICS), sin prefijos.
   Sin esta macro, dbt crearía esquemas como analytics_staging_algo si un modelo pidiera su propio esquema. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema }}
{%- endmacro %}
