#!/bin/sh
# Crea los esquemas de las capas clean y analytics del entorno actual y termina.
# Lo ejecuta el servicio postgres-init del docker-compose. No falla si ya existen.
# Los nombres salen de config/<entorno>.env (PG_SCHEMA_CLEAN y PG_SCHEMA_ANALYTICS).
set -e
psql -v ON_ERROR_STOP=1 \
  -c "CREATE SCHEMA IF NOT EXISTS \"${PG_SCHEMA_CLEAN}\";" \
  -c "CREATE SCHEMA IF NOT EXISTS \"${PG_SCHEMA_ANALYTICS}\";"
echo "Esquemas ${PG_SCHEMA_CLEAN} y ${PG_SCHEMA_ANALYTICS} listos"
