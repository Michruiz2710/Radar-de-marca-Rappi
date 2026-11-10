# Construir desde la raíz del repositorio:
#   docker build -f flows/Dockerfile -t radar-orquestador .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src src
COPY flows flows

# Corre como root porque comparte el volumen google_play_estado con scraper-google-play,
# que tambien corre como root. Si ambos pasan a un usuario sin privilegios, debe ser el mismo.
RUN mkdir -p /app/data/estado

CMD ["python", "-m", "flows.servir"]
