# Configuración por entorno

Archivos de configuración de dev, staging y prod. Solo valores no sensibles; los secretos van en `.env` y en GitHub Environments.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.5 CI/CD y entornos | Gabriel | Jonathan | Sara | Semana 2 |

## Estado

Listo para la semana 2.

## Qué cambia por entorno

| Variable | dev | staging | prod |
| --- | --- | --- | --- |
| `APP_ENV` | `dev` | `staging` | `prod` |
| `MINIO_BUCKET` | `radar-rappi` | `radar-rappi-staging` | `radar-rappi-prod` |
| `PG_SCHEMA_CLEAN` | `clean` | `clean_staging` | `clean_prod` |
| `PG_SCHEMA_ANALYTICS` | `analytics` | `analytics_staging` | `analytics_prod` |

Dev conserva los nombres del contrato de datos (`radar-rappi`, `clean`, `analytics`) para que nadie pierda lo que ya tiene en su MinIO.

`APP_ENV` también elige los intervalos y reintentos del orquestador, que están en `flows/entornos.py`. Ese archivo sigue siendo la fuente de esos valores; aquí solo se elige el entorno.

## Cómo se usa

En el computador, el entorno se elige con `ENTORNO` (si no se pone, es dev):

```bash
make up                    # dev
make up ENTORNO=staging    # staging
make down ENTORNO=staging
```

El Makefile carga primero `.env` (claves) y después `config/<ENTORNO>.env`, que gana si una variable está en los dos. Por eso nadie tiene que cambiar su `.env`.

Al levantar el compose, `minio-init` crea el bucket del entorno y `postgres-init` crea sus dos esquemas en la base `radar`. Los dos terminan solos y no fallan si ya existen.

Quien escriba en Postgres (limpieza, sentimiento, dbt) debe leer los nombres de `PG_SCHEMA_CLEAN` y `PG_SCHEMA_ANALYTICS` en vez de escribir `clean` o `analytics` fijos. El orquestador ya recibe las dos variables.

## Secretos en GitHub Environments

El CD usa dos Environments del repo, `staging` y `prod`, cada uno con tres secretos: `MINIO_ROOT_PASSWORD`, `POSTGRES_PASSWORD` y `HASH_SALT`. Los usuarios y el resto de valores salen de `.env.example` y de esta carpeta. Si falta un secreto, el CD falla y dice cuál.

Las contraseñas deben ser largas y sin `@`, `:` ni `/`, porque la de Postgres va dentro de la URL de conexión de Prefect. Una cadena hexadecimal sirve: `openssl rand -hex 24`.
