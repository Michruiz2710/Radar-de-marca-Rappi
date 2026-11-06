# Imagen del scraper de Google Play
FROM python:3.11-slim

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/__init__.py src/
COPY src/common/ src/common/
COPY src/ingestion/__init__.py src/ingestion/
COPY src/ingestion/google_play/ src/ingestion/google_play/

CMD ["python", "-m", "src.ingestion.google_play.scraper"]