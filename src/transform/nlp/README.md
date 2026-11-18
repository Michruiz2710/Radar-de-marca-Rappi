# Sentimiento y temas

Sentimiento con `pysentimiento` (RoBERTuito, español) y clasificación por tema con un diccionario de palabras clave (entregas, cobros y pagos, soporte, precios, app, repartidores, otro).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.4 Sentimiento y temas | Jonathan | Michelle | Katalina | Semana 2 |

## Qué hace

Lee `clean.menciones` (P2.3), analiza solo los registros pendientes y escribe `clean.sentimiento` con una fila por `id_registro`. Como pide el [contrato de la capa clean](../../../docs/contrato_clean.md), solo se analizan los registros **en español** (`idioma_detectado = 'es'`) que **no son bots** (`es_bot = false`) y tienen texto.

| Campo | Qué es |
| --- | --- |
| `id_registro` | Llave primaria; une con `clean.menciones` |
| `sentimiento`, `prob_sentimiento` | positivo / neutro / negativo y la probabilidad de la clase elegida |
| `prob_positivo`, `prob_neutro`, `prob_negativo` | probabilidad de cada clase |
| `tema`, `temas_detectados` | tema principal y todos los que tuvieron coincidencia |
| `version_modelo` | modelo, revisión (hash) y versión de pysentimiento, en un solo texto |
| `version_nlp` | versión del código de este módulo (sube si cambia el diccionario) |
| `hash_texto`, `procesado_en` | hash del texto analizado (si cambia en `menciones`, se reanaliza) y cuándo |

Es idempotente: solo se analizan los registros sin resultado, con otra versión del modelo o con texto editado. Si un registro ya analizado pasa a ser bot después, su fila antigua sigue en `sentimiento`; quien consulte debe unir con `menciones` y filtrar por `es_bot`.

## Archivos

| Archivo | Qué hace |
| --- | --- |
| `temas.py` | Diccionario de palabras clave y `clasificar_tema` (función pura) |
| `sentimiento.py` | Envoltorio de pysentimiento, por lotes |
| `tabla.py` | Tabla `sentimiento` y consultas |
| `pipeline.py` | `correr()` y comando `python -m src.transform.nlp.pipeline` |
| `evaluacion.py` | Exactitud, F1, matriz de confusión y comparación con estrellas |
| `Dockerfile`, `requirements-nlp.txt`, `descargar_modelo.py` | Imagen solo CPU con el modelo incluido |

## Cómo se corre

1. `NLP_MODEL_REVISION` (hash del commit del modelo) viene en `.env.example`; cópialo a tu `.env`. Es lo que fija la versión.
2. `make up` y luego `make nlp` (o `make nlp ENTORNO=staging`). Falla si queda algún registro elegible sin resultado.
3. `make evaluar-nlp` escribe `docs/evaluacion_nlp.md`. Evalúa sobre el texto limpio (`limpiar_texto` de P2.3) y lo compara con el original.

Pruebas: `python -m pytest tests/nlp` (no necesitan torch).

## Decisiones

- Solo CPU y modelo dentro de la imagen: reproducible y sin red al correr. La imagen es pesada, así que es una imagen propia.
- Recursos iniciales del contenedor: 2 CPU, 4 GB y lotes de 32 textos (`NLP_BATCH_SIZE`). Hay que medir y ajustar.
- El esquema sale de `PG_SCHEMA_CLEAN` (clean, clean_staging, clean_prod), como en P2.3.
- La imagen `nlp` no está en el CI ni en el CD: construirla exige bajar torch y el modelo (más de 10 minutos). Decidir con Gabriel si entra en el CI.

## En el flujo de Prefect (P2.1 y P3.2)

La etapa `sentimiento` de `flows/pipeline.py` llama a `sentimiento.analizar(rutas)`, que corre `correr()` y falla si queda algún registro elegible sin resultado. Corre **dentro del orquestador**: `flows/Dockerfile` instala torch (solo CPU), `requirements-nlp.txt` y el modelo fijado en `NLP_MODEL_REVISION`, igual que la imagen `nlp`. Si no se pasa esa variable al construir, usa la revisión de `.env.example`.

- La imagen del orquestador es pesada: la primera construcción tarda más de 10 minutos y el CI y el CD tienen un límite de tiempo más largo por eso. El contenedor tiene `mem_limit: 4g`.
- `analizar` ignora el diccionario de rutas: procesa todo lo pendiente en `clean.menciones`, también lo de corridas anteriores que no terminaron.
- Si la etapa falla, la tarea reintenta 3 veces (es idempotente) y luego el pipeline falla y cuenta para la alerta A1.
- `make nlp` sigue sirviendo para correr el análisis a mano o evaluar el modelo.
- **Primera corrida con mucho atraso.** Dentro de Prefect el análisis va a unos 2 registros por segundo (a unos 5 fuera de él) y cada tarea tiene un límite de 30 minutos. Con miles de menciones pendientes (por ejemplo, tras la primera extracción de Google Play o YouTube), conviene procesar el atraso antes, directamente en el contenedor, y después dejar que el pipeline solo analice lo nuevo:

  ```bash
  docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec orquestador python -m src.transform.nlp.pipeline
  ```

  En pruebas, 9.362 registros tardaron unos 40 minutos así; una corrida normal con registros nuevos tarda segundos.
- Dentro de Prefect, esta etapa escribe en los logs cientos de miles de líneas de código de bytes de Python (probablemente por `log_prints=True`). No afecta el resultado, pero llena la base de logs y la frena; el origen no está investigado.

## Estado

Hecho: clasificador de temas, sentimiento por lotes, tabla `clean.sentimiento`, pipeline idempotente, evaluación sobre texto limpio, imagen Docker y pruebas. Resultados de la evaluación en [`docs/evaluacion_nlp.md`](../../../docs/evaluacion_nlp.md).

**Pendiente:** probar contra Postgres real con datos de P2.3, regenerar el informe de evaluación con texto limpio, probar la etapa dentro de Prefect con Docker y mejorar el diccionario de temas (acierto actual: ver el informe).
