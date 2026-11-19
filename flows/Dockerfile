# Construir desde la raíz del repositorio:
#   docker build -f flows/Dockerfile -t radar-orquestador .
# Incluye torch (solo CPU) y el modelo de sentimiento, porque la etapa `sentimiento` del
# pipeline corre dentro de este mismo proceso. Por eso la imagen es pesada y la primera
# construcción tarda más de 10 minutos (las siguientes reutilizan la caché de capas).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Revisión (hash del commit) del modelo en Hugging Face. El compose la pasa desde NLP_MODEL_REVISION
# del .env; si llega vacía (CI, build suelto) se usa la misma que fija .env.example.
ARG NLP_MODEL_REVISION=
ENV NLP_MODEL_REVISION=${NLP_MODEL_REVISION:-a2cc0f67ebd705c55191e25a05ba23d885fcc09b}

# 1) dependencias del pipeline
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# dbt para la etapa de modelos (P3.4)
COPY dbt/requirements-dbt.txt ./requirements-dbt.txt
RUN pip install --no-cache-dir -r requirements-dbt.txt

# 2) NLP (P2.4): torch solo CPU, el resto de dependencias y el modelo fijado en la imagen.
#    Va antes del código para que estas capas casi nunca se rehagan.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY src/transform/nlp/requirements-nlp.txt requirements-nlp.txt
# El constraint evita que pip, al resolver accelerate/pysentimiento, reemplace torch por la
# versión de PyPI (con CUDA, varios GB más): obliga a quedarse con la de CPU ya instalada.
RUN echo "torch==2.5.1" > /tmp/constraints.txt \
    && pip install --no-cache-dir -c /tmp/constraints.txt -r requirements-nlp.txt
ENV HF_HOME=/opt/hf
COPY src/transform/nlp/descargar_modelo.py /tmp/descargar_modelo.py
RUN python /tmp/descargar_modelo.py
# A partir de aquí el contenedor no necesita internet para el modelo
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY src src
COPY flows flows
COPY quality quality
COPY dbt dbt

# Corre como root porque comparte el volumen google_play_estado con scraper-google-play,
# que tambien corre como root. Si ambos pasan a un usuario sin privilegios, debe ser el mismo.
RUN mkdir -p /app/data/estado

CMD ["python", "-m", "flows.servir"]
