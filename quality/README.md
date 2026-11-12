# Calidad de datos

Suites y checkpoints de Great Expectations para las capas raw y clean.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.2 Validaciones | Katalina | Gabriel | Michelle | Semana 2 |

## Estado

Listo para la semana 2. Great Expectations 1.24.1, en modo efímero (sin carpeta `gx/`): las suites se arman en código a partir del contrato.

## Qué valida

Cada regla tiene una severidad:

- **Crítica:** el dato rompe el contrato. La función lanza `ValidacionCriticaError` y el pipeline se detiene.
- **Advertencia:** el dato es raro pero usable. Solo queda en el log.

### Capa raw (`suite_raw(fuente)`, una por fuente)

| Regla | Severidad |
| --- | --- |
| Columnas exactas del contrato (falta una obligatoria o sobra una, p. ej. `userName`) | Crítica |
| Campos obligatorios no vacíos | Crítica |
| `fuente` igual a la del archivo; `id_registro` único y con prefijo `<fuente>:` | Crítica |
| `texto` no vacío; `autor_hash` de 64 caracteres hex; `likes` ≥ 0 | Crítica |
| `fecha_publicacion` no futura (margen de 10 min) | Crítica |
| Google Play: `calificacion` entre 1 y 5 | Crítica |
| YouTube y noticias: campos solo de Google Play vacíos; fuera de noticias, `medio` vacío | Crítica |
| Archivo sin filas; `idioma` ≠ `es`; `pais` ≠ `co`; `version_contrato` distinta a la actual | Advertencia |
| Google Play: más del 5 % de reseñas sin calificación | Advertencia |

### Capa clean (`suite_clean()`, tabla `menciones`)

| Regla | Severidad |
| --- | --- |
| Columnas exactas de `src/transform/clean/tabla.py` | Crítica |
| `id_registro` no vacío, único y con fuente válida; `fuente` permitida | Crítica |
| `texto_limpio` no vacío; `calificacion` entre 1 y 5 | Crítica |
| `fecha_publicacion` y `fecha_extraccion` no futuras | Crítica |
| `autor_hash` y `hash_texto` de 64 caracteres hex; `es_bot` y `version_limpieza` no vacíos | Crítica |
| Tabla vacía; `idioma_detectado` fuera de es/pt/en; `pais` ≠ `co` | Advertencia |

## Archivos

| Archivo | Qué hace |
| --- | --- |
| `reglas.py` | Constantes que salen del contrato (columnas, obligatorios, patrones, severidades) |
| `suites.py` | `preparar_tabla`, `suite_raw(fuente)`, `preparar_tabla_clean`, `suite_clean()` |
| `checkpoints.py` | `validar_cruda(rutas)` y `validar_limpia(rutas)`: las etapas que llama `flows/pipeline.py` |
| `validar.py` | Comando del CI (`make validar`) |
| `generar_datos_prueba.py` | Genera `datos_prueba/correctos` y `datos_prueba/incorrectos` |

## Cómo se corre

```bash
make validar                      # o: python -m quality.validar  (lo corre el CI en cada PR)
python -m quality.validar --raw   # además valida todos los archivos de la capa raw
python -m pytest -q tests/quality
python -m quality.generar_datos_prueba   # solo si cambia el contrato
```

En el pipeline, las etapas `validacion_cruda` y `validacion_limpia` se conectan solas: `flows/pipeline.py` ya apunta a `quality.checkpoints`.

**Data Docs:** cada validación corre como un Checkpoint de Great Expectations y actualiza el reporte HTML en `data/data_docs/index.html` (se cambia con `DATA_DOCS_DIR`). Está en `data/`, así que no se sube a Git. Hay un contexto de GX por proceso: en el orquestador (que queda prendido) el índice acumula las validaciones desde que arrancó; al reiniciarlo empieza de nuevo.

## Datos de prueba

`datos_prueba/correctos/` tiene un archivo válido por fuente. `datos_prueba/incorrectos/` tiene 10 archivos con **un solo defecto** cada uno, de las tres fuentes; el nombre dice la fuente y el defecto (`<fuente>__<defecto>.jsonl`). Son sintéticos, sin datos personales, y están exceptuados del `*.jsonl` del `.gitignore` porque el CI no tiene MinIO.

## Decisiones y hallazgos

- **Archivos de contratos anteriores.** La prueba con datos reales (459 reseñas de Google Play del 6 nov, guardadas con el contrato 1.0.0) encontró que esos archivos traen la columna `subreddit` (vacía), retirada en el contrato 1.3.0. Se decidió: una columna retirada **vacía** se ignora; si trae datos, sigue siendo crítica (`columnas_retiradas` en `reglas.py`). Las columnas opcionales nuevas que falten (`fecha_edicion`, etc.) se agregan vacías. Una versión de contrato antigua es advertencia, no crítica.
- **Con datos reales:** los 2 archivos de Google Play pasan sin críticas (solo la advertencia de versión). YouTube y noticias quedan cubiertos con los datos de prueba hasta tener datos reales en MinIO.

## Pendiente

- **Reintentos:** las etapas del pipeline tienen 3 reintentos (P2.1). Una validación crítica fallida se reintenta 3 veces antes de detener el flujo; no cambia el resultado, pero demora la alerta. Revisar con Sara si conviene no reintentar `ValidacionCriticaError`.
- **Métrica `validaciones_fallidas_total{suite, severidad}`:** se publica con la observabilidad de P3.1.