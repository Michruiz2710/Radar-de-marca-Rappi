# Imagen de sentimiento y temas (P2.4): solo CPU, con el modelo incluido en la imagen.
# Construir desde la raíz:  docker build -f src/transform/nlp/Dockerfile --build-arg NLP_MODEL_REVISION=<hash> .
# (make nlp lo hace con NLP_MODEL_REVISION del .env)
FROM python:3.11-slim

ARG NLP_MODEL_REVISION
RUN test -n "$NLP_MODEL_REVISION" || { echo "Falta NLP_MODEL_REVISION en .env (ver src/transform/nlp/README.md)"; exit 1; }

WORKDIR /app

# 1) torch solo CPU (mucho más liviano que la versión con GPU)
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# 2) resto de dependencias
COPY src/transform/nlp/requirements-nlp.txt requirements-nlp.txt
RUN pip install --no-cache-dir -r requirements-nlp.txt

# 3) modelo fijado en una revisión, guardado en la imagen. Esta capa solo se rehace si cambia la revisión.
ENV HF_HOME=/opt/hf NLP_MODEL_REVISION=${NLP_MODEL_REVISION}
COPY src/transform/nlp/descargar_modelo.py /tmp/descargar_modelo.py
RUN python /tmp/descargar_modelo.py

# A partir de aquí el contenedor no necesita internet
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# 4) código: src/common trae db.py y src/transform/clean trae texto.py (limpiar_texto, que usa la evaluación), ambos de P2.3
COPY src/__init__.py src/
COPY src/common/ src/common/
COPY src/transform/__init__.py src/transform/
COPY src/transform/clean/ src/transform/clean/
COPY src/transform/nlp/ src/transform/nlp/

CMD ["python", "-m", "src.transform.nlp.pipeline"]
