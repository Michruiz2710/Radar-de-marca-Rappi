#!/bin/sh
# Se ejecuta UNA sola vez, cuando Postgres arranca con el volumen vacío.
# Crea la base propia de Prefect dentro del mismo Postgres, para que su estado
# no se mezcle con las capas clean y analytics (base POSTGRES_DB).
# Para que corra de nuevo hay que borrar el volumen: docker compose -f infra/docker-compose.yml down -v

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"${PREFECT_DB_NAME:-prefect}\";"
