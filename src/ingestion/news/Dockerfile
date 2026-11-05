# Construir desde la raíz del repositorio:
#   docker build -f src/ingestion/news/Dockerfile -t radar-news .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/__init__.py src/__init__.py
COPY src/common src/common
COPY src/ingestion/__init__.py src/ingestion/__init__.py
COPY src/ingestion/news src/ingestion/news

RUN useradd --create-home scraper && chown -R scraper:scraper /app
USER scraper

ENTRYPOINT ["python", "-m", "src.ingestion.news.scraper"]
