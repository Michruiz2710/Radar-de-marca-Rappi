# Workflows de CI/CD

Pipelines de GitHub Actions: pruebas, validaciones y build de imágenes en cada PR; publicación de imágenes en `main`.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.5 CI/CD y entornos | Gabriel | Jonathan | Sara | Semana 2 |

## Estado

Listo para la semana 2. Hay dos workflows: `ci.yml` y `cd.yml`.

### CI (`ci.yml`)

Corre en cada PR hacia `main` y en cada push a `main`. Tiene tres trabajos que corren en paralelo:

- Pruebas y lint: instala `requirements.txt` con Python 3.11 (la misma versión de los Dockerfiles), corre `make lint` con ruff 0.12.12 y luego `make test`. No usa secretos ni internet.
- Build de imágenes: construye las imágenes de los tres scrapers y del orquestador para comprobar que no se rompen. No las publica.
- Validaciones de calidad: corre `make validar`. Ese objetivo lo agrega P2.2 al Makefile. Mientras no exista, el paso se salta con un aviso y no bloquea el PR. Como en el CI no hay MinIO, internet ni claves, las validaciones tienen que funcionar con datos de ejemplo guardados en el repo.

Para revisar en local lo mismo que el CI, instala ruff con `pip install ruff==0.12.12` y corre `make lint` y `make test`.

### CD (`cd.yml`)

Corre en cada push a `main` y cada vez que se publica una release.

1. Verificar: levanta el compose completo dentro del runner con la configuración de un entorno y las claves de su GitHub Environment. En un push a `main` usa staging; en una release usa prod. Revisa que el orquestador registre sus despliegues en Prefect y que existan el bucket y los dos esquemas de Postgres del entorno. Al terminar apaga todo y borra los volúmenes.
2. Publicación: si la verificación pasa, sube las cuatro imágenes a `ghcr.io/michruiz2710/radar-de-marca-rappi/<servicio>`. En `main` les pone las etiquetas `latest` y `sha-<commit>`. En una release les pone el número de la release, por ejemplo `v0.2.0`.

Los valores de cada entorno están en `config/` y las claves en los Environments `staging` y `prod` del repo (ver `config/README.md`). Las releases las sigue creando Michelle a mano en GitHub; el CD no crea releases. Las imágenes se construyen solo para amd64. Para entrar a ghcr.io se usa el `GITHUB_TOKEN` que GitHub genera en cada corrida.

### Desplegar con las imágenes publicadas

En `.env`, la variable `IMAGE_TAG` elige la versión: `latest` para lo último de `main` o una etiqueta como `v0.2.0`. Después:

```bash
make desplegar
```

Este comando baja las imágenes de ghcr.io y levanta todo sin construir nada. `make up` sigue construyendo las imágenes en el computador, como antes.

### Pendiente

- Michelle: crear los Environments `staging` y `prod` con sus tres secretos, exigir que el CI pase antes de fusionar a `main` y hacer públicos los paquetes de ghcr.io para que se puedan bajar sin iniciar sesión.
- P2.2 (Katalina): agregar el objetivo `validar` al Makefile. Hasta entonces el CI no corre Great Expectations.
