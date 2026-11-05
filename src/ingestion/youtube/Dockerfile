# Imagen del scraper de YouTube. Se construye desde la RAÍZ del repo:
#   docker build -f src/ingestion/youtube/Dockerfile -t radar-youtube .
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src/ /app/src/

CMD ["python", "-m", "src.ingestion.youtube.scraper"]
