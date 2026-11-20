FROM python:3.11-slim

WORKDIR /app
COPY dashboard/requirements.txt dashboard/requirements.txt
RUN pip install --no-cache-dir -r dashboard/requirements.txt

COPY src/__init__.py src/__init__.py
COPY src/common src/common
COPY dashboard dashboard

WORKDIR /app/dashboard
ENV PYTHONPATH=/app
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]