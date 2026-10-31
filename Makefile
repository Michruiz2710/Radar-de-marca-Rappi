# Atajos del proyecto. Los objetivos de Docker funcionan cuando exista infra/docker-compose.yml (P1.1).

COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help up down logs ps test lint

help:
	@echo "make up     Levanta todos los servicios"
	@echo "make down   Detiene los servicios"
	@echo "make logs   Muestra los logs en vivo"
	@echo "make ps     Lista los contenedores"
	@echo "make test   Corre las pruebas"
	@echo "make lint   Revisa el estilo del código"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

test:
	python -m pytest -q tests

lint:
	python -m ruff check .
