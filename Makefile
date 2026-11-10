# Atajos del proyecto. Los objetivos de Docker usan infra/docker-compose.yml y el archivo .env de la raíz.

COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help up down logs ps test lint check-env scrapers desplegar

help:
	@echo "make up     Levanta todos los servicios"
	@echo "make desplegar  Levanta todo con las imágenes publicadas en ghcr.io (IMAGE_TAG en .env)"
	@echo "make down   Detiene los servicios"
	@echo "make logs   Muestra los logs en vivo"
	@echo "make ps     Lista los contenedores"
	@echo "make scrapers  Corre una vez los 3 scrapers (requiere make up)"
	@echo "make test   Corre las pruebas"
	@echo "make lint   Revisa el estilo del código"

# Falla con un mensaje claro si todavía no existe el archivo .env
check-env:
	@test -f .env || { echo "No existe .env. Copia el ejemplo y completa las credenciales: cp .env.example .env"; exit 1; }

up: check-env
	$(COMPOSE) up -d --build
	@echo "Listo. MinIO: http://localhost:9001 | Prefect: http://localhost:4200"

down: check-env
	$(COMPOSE) down

logs: check-env
	$(COMPOSE) logs -f

ps: check-env
	$(COMPOSE) ps

# Corre una vez cada scraper y guarda los datos crudos en MinIO
scrapers: check-env
	$(COMPOSE) --profile scrapers run --rm --build scraper-news
	$(COMPOSE) --profile scrapers run --rm --build scraper-youtube
	$(COMPOSE) --profile scrapers run --rm --build scraper-google-play

# pytest termina con código 5 cuando todavía no hay pruebas; eso no es un error
test:
	@python -m pytest -q tests; code=$$?; \
	if [ $$code -eq 5 ]; then echo "Aún no hay pruebas en tests/."; exit 0; fi; \
	exit $$code

lint:
	python -m ruff check .

# Levanta el entorno con las imágenes que publicó el CD en ghcr.io, sin construir nada.
# La versión sale de IMAGE_TAG en .env (latest o una etiqueta como v0.2.0).
desplegar: check-env
	$(COMPOSE) pull
	$(COMPOSE) up -d --no-build
	@echo "Listo. MinIO: http://localhost:9001 | Prefect: http://localhost:4200"
