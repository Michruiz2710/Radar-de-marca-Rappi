# Imagen de dbt (P3.4). Construir desde la raíz: docker build -f dbt/Dockerfile .
FROM python:3.11-slim

WORKDIR /app/dbt

COPY dbt/requirements-dbt.txt requirements-dbt.txt
RUN pip install --no-cache-dir -r requirements-dbt.txt

COPY dbt/ .
# profiles.yml está en esta misma carpeta y lee todo de variables de entorno
ENV DBT_PROFILES_DIR=/app/dbt

# build = run + test, en orden: si una prueba de una fuente falla, no se construye lo que depende de ella
CMD ["dbt", "build"]
