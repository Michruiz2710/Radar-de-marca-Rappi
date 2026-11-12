# Atajos del proyecto. Los objetivos de Docker usan infra/docker-compose.yml y el archivo .env de la raíz.

# Entorno: dev (por defecto), staging o prod. Ejemplo: make up ENTORNO=staging
# Las claves salen de .env y los valores de cada entorno de config/<ENTORNO>.env (ese gana).
ENTORNO ?= dev
COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env --env-file config/$(ENTORNO).env

.PHONY: help up down logs ps test lint check-env scrapers nlp evaluar-nlp

help:
	@echo "make up     Levanta todos los servicios"
	@echo "make up ENTORNO=staging  Lo mismo con la configuración de staging (dev, staging o prod)"
	@echo "make desplegar  Levanta todo con las imágenes publicadas en ghcr.io (IMAGE_TAG en .env)"
	@echo "make down   Detiene los servicios"
	@echo "make logs   Muestra los logs en vivo"
	@echo "make ps     Lista los contenedores"
	@echo "make scrapers  Corre una vez los 3 scrapers (requiere make up)"
	@echo "make test   Corre las pruebas"
	@echo "make lint   Revisa el estilo del código"
	@echo "make nlp    Calcula sentimiento y tema de los registros pendientes (requiere make up)"
	@echo "make evaluar-nlp  Evalúa sentimiento y temas contra las 200 reseñas etiquetadas"

# Falla con un mensaje claro si todavía no existe el archivo .env
check-env:
	@test -f .env || { echo "No existe .env. Copia el ejemplo y completa las credenciales: cp .env.example .env"; exit 1; }
	@test -f config/$(ENTORNO).env || { echo "No existe config/$(ENTORNO).env. Usa ENTORNO=dev, staging o prod."; exit 1; }

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

nlp: check-env
	$(COMPOSE) --profile nlp run --rm --build nlp

evaluar-nlp: check-env
	$(COMPOSE) --profile nlp run --rm --build nlp python -m src.transform.nlp.evaluacion

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
