# Sentimiento y temas

Sentimiento con `pysentimiento` (RoBERTuito, español) y clasificación por tema con un diccionario de palabras clave (entregas, cobros y pagos, soporte, precios, app, repartidores, otro).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.4 Sentimiento y temas | Jonathan | Michelle | Katalina | Semana 2 |

## Qué hace

Lee `clean.menciones` (P2.3), analiza solo los registros pendientes y escribe `clean.menciones_nlp` con una fila por `id_registro`:

| Campo | Qué es |
| --- | --- |
| `sentimiento`, `prob_sentimiento` | positivo / neutro / negativo y la probabilidad de la clase elegida |
| `prob_positivo`, `prob_neutro`, `prob_negativo` | probabilidad de cada clase |
| `tema`, `temas_detectados` | tema principal y todos los que tuvieron coincidencia |
| `version_modelo` | modelo, revisión (hash) y versión de pysentimiento, en un solo texto |
| `version_nlp` | versión del código de este módulo (sube si cambia el diccionario) |
| `hash_texto`, `procesado_en` | texto analizado (si cambia, se reanaliza) y cuándo |

Es idempotente: solo se analizan los registros sin resultado, con otra versión del modelo o con texto editado. Los registros `es_bot` también se analizan; se filtran con `es_bot` al consultar.

## Archivos

| Archivo | Qué hace |
| --- | --- |
| `temas.py` | Diccionario de palabras clave y `clasificar_tema` (función pura) |
| `sentimiento.py` | Envoltorio de pysentimiento, por lotes |
| `tabla.py` | Tabla `menciones_nlp` y consultas |
| `pipeline.py` | `correr()` (lo llama el flujo de Prefect, P2.1) y comando `python -m src.transform.nlp.pipeline` |
| `evaluacion.py` | Exactitud, matriz de confusión y comparación con estrellas |
| `Dockerfile`, `requirements-nlp.txt`, `descargar_modelo.py` | Imagen solo CPU con el modelo incluido |

## Cómo se corre

1. Obtén el hash del commit del modelo y ponlo en `.env` como `NLP_MODEL_REVISION` (ver `.env.example`). Es lo que fija la versión.
2. `make up` y luego `make nlp`. Falla (código distinto de 0) si queda algún registro limpio sin resultado.
3. `make evaluar-nlp` escribe `docs/evaluacion_nlp.md`.

Pruebas: `python -m pytest tests/nlp` (no necesitan torch; las del pipeline necesitan `sqlalchemy`).

## Decisiones

- Solo CPU y modelo dentro de la imagen: reproducible y sin red al correr. La imagen es pesada, así que es una imagen propia y no la de limpieza.
- Recursos iniciales del contenedor: 2 CPU, 4 GB y lotes de 32 textos (`NLP_BATCH_SIZE`). Hay que medir y ajustar.
- El esquema sale de `PG_SCHEMA_CLEAN` (clean, clean_staging, clean_prod), igual que en P2.3.

## Estado

Código y pruebas escritos. **Pendiente:** correr `make evaluar-nlp` con el modelo real y documentar la exactitud en `docs/evaluacion_nlp.md`; fijar `NLP_MODEL_REVISION`; probar contra Postgres cuando P2.3 esté fusionada; conectar `correr()` al flujo principal (P2.1).
