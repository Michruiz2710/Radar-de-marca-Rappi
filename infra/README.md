# Infraestructura

`docker-compose.yml` con MinIO, Postgres y Prefect. Desde la Semana 3 se suman Prometheus, Pushgateway, Grafana y Streamlit.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.1 Entorno | Jonathan | Sara | Gabriel | Semana 1 |

## Servicios

| Servicio | Imagen | Puertos | Para qué sirve |
| --- | --- | --- | --- |
| `minio` | `pgsty/silo` (ver nota más abajo) | 9000 (API S3), 9001 (consola web) | Capa raw: archivos `.jsonl` de los scrapers |
| `minio-init` | `python:3.11-slim` | — | Crea el bucket `radar-rappi` al iniciar y termina |
| `postgres` | `postgres:16.6-alpine` | 5432 | Base `radar` (capas clean y analytics) y base `prefect` |
| `prefect` | `prefecthq/prefect:3.1.5-python3.11` | 4200 | Servidor y UI del orquestador |

Que `minio-init` aparezca como `Exited (0)` es lo normal: crea el bucket y termina.

## Cómo se usa

Desde la raíz del repositorio, con Docker Desktop abierto y el archivo `.env` creado (ver el README principal):

```bash
make up      # levanta todo
make ps      # estado de los contenedores
make logs    # logs en vivo
make down    # apaga, conserva los datos
```

Sin `make`: `docker compose -f infra/docker-compose.yml --env-file .env up -d`.

- Consola de MinIO: http://localhost:9001 (usuario y contraseña de `MINIO_ROOT_USER` y `MINIO_ROOT_PASSWORD`).
- UI de Prefect: http://localhost:4200.

Para borrar todos los datos y empezar desde cero: `docker compose -f infra/docker-compose.yml --env-file .env down -v`.

## Decisiones y notas

- **MinIO se sirve con Silo.** MinIO retiró sus imágenes de Docker Hub y Quay en septiembre de 2026 (`minio/minio` y `minio/mc` ya no se pueden descargar). Usamos `pgsty/silo`, un fork comunitario compatible: mismas variables `MINIO_*`, mismo comando y misma API S3, así que el código de `src/common/storage.py` no cambia. Más información en https://silo.pigsty.io. El tag está fijado en el compose. Si deja de existir, la alternativa es `cgr.dev/chainguard/minio` (solo publica `latest` y corre con otro usuario).
- **El bucket se crea con un script de Python** (`infra/minio/crear_bucket.py`) y no con el cliente `mc`, que tampoco se puede descargar. Usa la misma librería `minio` que el módulo común. La primera vez necesita internet para instalarla con `pip`. Si el bucket ya existe, no hace nada.
- **Prefect tiene su propia base de datos** (`prefect`) dentro del mismo Postgres, separada de `radar`. La crea `infra/postgres/init/01-crear-base-prefect.sh`, que solo corre cuando el volumen de Postgres está vacío; para repetirlo hay que hacer `down -v`.
- **Credenciales.** MinIO y Postgres usan usuarios y contraseñas distintos, definidos en `.env` (nunca en Git). La contraseña de Postgres no debe tener caracteres como `@`, `:` o `/`, porque va dentro de la URL de conexión de Prefect. Prefect y las capas del pipeline comparten el mismo usuario de Postgres.
- **Datos.** Los datos viven en volúmenes de Docker (`minio_data` y `postgres_data`), fuera del repositorio.

## Problemas frecuentes

- *Un puerto ya está en uso (5432, 9000, 9001 o 4200):* hay otro programa usándolo, por ejemplo un Postgres instalado en tu equipo. Ciérralo o cambia el puerto del lado izquierdo en `docker-compose.yml`.
- *`make up` dice que no existe `.env`:* copia el ejemplo con `cp .env.example .env` y completa las credenciales.
- *Prefect tarda en abrir:* en el primer arranque necesita unos 20 segundos para quedar disponible.
- *Faltan imágenes o hay errores al descargarlas:* revisa que Docker Desktop esté corriendo y que haya internet.

## Estado

Terminado (P1.1). Levanta MinIO, Postgres 16 y Prefect con `make up`, crea el bucket `radar-rappi` y la base de Prefect al iniciar.

Pendiente para otros paquetes: Prometheus, Pushgateway, Grafana y Streamlit (P3.1, P3.2 y P3.3), y las variables y entornos por ambiente (P2.5).
