# Construir desde la raíz del repositorio:
#   docker build -f flows/Dockerfile -t radar-orquestador .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src src
COPY flows flows

RUN useradd --create-home orquestador && mkdir -p /app/data && chown -R orquestador:orquestador /app
USER orquestador

CMD ["python", "-m", "flows.servir"]
