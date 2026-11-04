# Contrato de datos

**Versión:** 1.1.0 · **Responsable:** Katalina (Data Quality) · **Autora:** Michelle · **Paquete:** P1.2

Las fuentes (Google Play, YouTube y noticias de Google News) se guardan con un mismo esquema, para que la limpieza, las validaciones y el análisis de sentimiento funcionen igual sin importar de dónde vino el dato.

El contrato está implementado en código en [`src/common/schema.py`](../src/common/schema.py) (clase `RegistroMencion`). **Si este documento y el código no coinciden, manda el código** y se corrige el documento.

## Campos

| Campo | Tipo | Obligatorio | Regla | Google Play | YouTube | Reddit | Noticias |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id_registro` | texto | Sí (calculado) | `<fuente>:<id_original>`, único en todo el sistema | ✓ | ✓ | ✓ | ✓ |
| `fuente` | texto | Sí | `google_play`, `youtube`, `reddit` o `news` | ✓ | ✓ | ✓ | ✓ |
| `id_original` | texto | Sí | No vacío. `reviewId`, ID del comentario de YouTube o ID de Reddit (`t3_…` post, `t1_…` comentario) o enlace de la noticia | ✓ | ✓ | ✓ | ✓ |
| `texto` | texto | Sí | No vacío. Reseña o comentario; en un post de Reddit, título + cuerpo; en noticias, el titular | ✓ | ✓ | ✓ | ✓ |
| `fecha_publicacion` | fecha y hora UTC | Sí | No puede estar en el futuro (margen de 10 min) | ✓ | ✓ | ✓ | ✓ |
| `idioma` | texto | Sí | Código ISO de 2 letras, por defecto `es` | ✓ | ✓ | ✓ | ✓ |
| `pais` | texto | Sí | Código ISO de 2 letras, por defecto `co` | ✓ | ✓ | ✓ | ✓ |
| `fecha_extraccion` | fecha y hora UTC | Sí | Por defecto, el momento de crear el registro | ✓ | ✓ | ✓ | ✓ |
| `run_id` | texto | Sí | ID de la corrida, generado con `nuevo_run_id()` | ✓ | ✓ | ✓ | ✓ |
| `version_scraper` | texto | Sí | Versión del código que extrajo el dato | ✓ | ✓ | ✓ | ✓ |
| `version_contrato` | texto | Sí (automático) | Versión de este contrato | ✓ | ✓ | ✓ | ✓ |
| `autor_hash` | texto (64) | No | SHA-256 con sal; 64 caracteres hexadecimales. Nunca el nombre real | ✓ | ✓ | ✓ | |
| `calificacion` | entero | No | Entre 1 y 5 | ✓ | ✗ | ✗ | ✗ |
| `likes` | entero | No | Mayor o igual a 0 (`thumbsUpCount`, `likeCount` o `score` de Reddit) | ✓ | ✓ | ✓ | |
| `version_app` | texto | No | `reviewCreatedVersion` | ✓ | ✗ | ✗ | ✗ |
| `respuesta_marca` | texto | No | Respuesta de Rappi a la reseña | ✓ | ✗ | ✗ | ✗ |
| `fecha_respuesta` | fecha y hora UTC | No | No puede ser anterior a `fecha_publicacion` | ✓ | ✗ | ✗ | ✗ |
| `id_contenedor` | texto | No | ID del video (YouTube) o del post al que pertenece un comentario (Reddit) | | ✓ | ✓ | |
| `subreddit` | texto | No | Nombre del subreddit sin `r/`, en minúsculas | ✗ | ✗ | ✓ | ✗ |
| `url` | texto | No | Enlace al video, al post o a la noticia | | ✓ | ✓ | ✓ |
| `medio` | texto | No | Nombre del medio que publica la noticia | ✗ | ✗ | ✗ | ✓ |

✓ se llena en esa fuente · ✗ prohibido en esa fuente (el registro se rechaza) · vacío: no aplica.

## Reglas generales

1. **Campos fuera del contrato están prohibidos.** Si un scraper intenta guardar `userName`, el `author` de Reddit, una foto de perfil o cualquier campo no listado, el registro se rechaza. Esto protege contra fugas de datos personales.
2. **Fechas en UTC e ISO 8601.** Una fecha sin zona horaria se asume UTC; una fecha con zona horaria (por ejemplo, hora de Colombia) se convierte a UTC. El dashboard convierte a hora de Colombia al mostrar.
3. **Autores seudonimizados.** El nombre se normaliza (espacios, mayúsculas, tildes) y se convierte con `hash_autor()` usando la sal `HASH_SALT` del `.env`. El mismo autor siempre produce el mismo hash, lo que permite detectar bots sin saber quién es.
4. **Una corrida, una fuente, un archivo.** Cada corrida de un scraper escribe un solo archivo JSON Lines con registros de una sola fuente y sin `id_registro` repetidos.
5. **Cambios al contrato.** Requieren Pull Request revisado por la responsable de Data Quality (Katalina), aviso al grupo y subir `VERSION_CONTRATO` en `schema.py`, porque afectan a todos los paquetes.

## Dónde se guarda

| Capa | Dónde | Formato | Quién escribe |
| --- | --- | --- | --- |
| `raw` | MinIO, bucket `MINIO_BUCKET`, ruta `raw/fuente=<fuente>/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl` | JSON Lines | Scrapers, con `guardar_registros()` |
| `clean` | Postgres, esquema `clean` | Tablas | Limpieza y sentimiento (P2.3, P2.4) |
| `analytics` | Postgres, esquema `analytics` | Tablas y vistas de dbt | dbt (P3.4) |

La fecha de la partición es la fecha de extracción en UTC.

## Ejemplo de registro (una línea del archivo)

```json
{"fuente":"google_play","id_original":"gp-123","texto":"El pedido llegó tarde","fecha_publicacion":"2026-11-02T13:00:00Z","idioma":"es","pais":"co","fecha_extraccion":"2026-11-02T15:00:00Z","run_id":"20261102T150000Z-1a2b3c4d","version_scraper":"0.1.0","version_contrato":"1.1.0","autor_hash":"3f5a…(64 caracteres)","calificacion":2,"likes":null,"version_app":"9.1.0","respuesta_marca":null,"fecha_respuesta":null,"id_contenedor":null,"subreddit":null,"url":null,"medio":null,"id_registro":"google_play:gp-123"}
```

## Historial

| Versión | Fecha | Cambio |
| --- | --- | --- |
| 1.0.0 | 2026-11-04 | Versión inicial (fuentes: Google Play, YouTube y Reddit) |
| 1.1.0 | 2026-11-04 | Se agrega la fuente `news` y el campo `medio`, porque el grupo eligió Google News como tercera fuente. Reddit sigue en el esquema hasta que se decida retirarlo |
