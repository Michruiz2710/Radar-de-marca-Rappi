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

## Pendiente: conectarlo al flujo de Prefect (P2.1)

`flows/pipeline.py` espera una función `src.transform.nlp.sentimiento:analizar`. **Todavía no existe a propósito**: la etapa queda "pendiente" y el pipeline sigue. Si se agregara sin más, la imagen del orquestador (`flows/Dockerfile`) no tiene torch ni pysentimiento, la etapa fallaría tras la limpieza y detendría el flujo. Hay que decidir con Sara cómo correrlo: meter las dependencias en la imagen del orquestador (muy pesada), correr la imagen `nlp` como servicio aparte, o usar un worker propio.

## Estado

Hecho: clasificador de temas, sentimiento por lotes, tabla `clean.sentimiento`, pipeline idempotente, evaluación sobre texto limpio, imagen Docker y pruebas. Resultados de la evaluación en [`docs/evaluacion_nlp.md`](../../../docs/evaluacion_nlp.md).

**Pendiente:** probar contra Postgres real con datos de P2.3, regenerar el informe de evaluación con texto limpio, decidir la integración con el orquestador y mejorar el diccionario de temas (acierto actual: ver el informe).
