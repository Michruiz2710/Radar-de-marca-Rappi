# Contrato de datos

**Versión:** 1.3.0 · **Responsable:** Katalina (Data Quality) · **Autora:** Michelle · **Paquete:** P1.2

Las fuentes (Google Play, YouTube y noticias de Google News) se guardan con un mismo esquema, para que la limpieza, las validaciones y el análisis de sentimiento funcionen igual sin importar de dónde vino el dato.

El contrato está implementado en código en [`src/common/schema.py`](../src/common/schema.py) (clase `RegistroMencion`). **Si este documento y el código no coinciden, manda el código** y se corrige el documento.

## Campos

| Campo | Tipo | Obligatorio | Regla | Google Play | YouTube | Noticias |
| --- | --- | --- | --- | --- | --- | --- |
| `id_registro` | texto | Sí (calculado) | `<fuente>:<id_original>`, único en todo el sistema | ✓ | ✓ | ✓ |
| `fuente` | texto | Sí | `google_play`, `youtube` o `news` | ✓ | ✓ | ✓ |
| `id_original` | texto | Sí | No vacío. `reviewId`, ID del comentario de YouTube o, en noticias, el `id` del feed de Google News (si falta, el enlace) | ✓ | ✓ | ✓ |
| `texto` | texto | Sí | No vacío. Reseña o comentario; en noticias, el titular | ✓ | ✓ | ✓ |
| `fecha_publicacion` | fecha y hora UTC | Sí | No puede estar en el futuro (margen de 10 min). En Google Play es la fecha de la versión actual de la reseña: si el usuario la edita, cambia | ✓ | ✓ | ✓ |
| `idioma` | texto | Sí | Código ISO de 2 letras, por defecto `es`. Es el idioma **de la consulta**, no el detectado: el idioma real lo calcula la limpieza (`idioma_detectado`) | ✓ | ✓ | ✓ |
| `pais` | texto | Sí | Código ISO de 2 letras, por defecto `co`. Es el país **de la consulta**, no el del autor | ✓ | ✓ | ✓ |
| `fecha_extraccion` | fecha y hora UTC | Sí | Por defecto, el momento de crear el registro | ✓ | ✓ | ✓ |
| `run_id` | texto | Sí | ID de la corrida, generado con `nuevo_run_id()` | ✓ | ✓ | ✓ |
| `version_scraper` | texto | Sí | Versión del código que extrajo el dato | ✓ | ✓ | ✓ |
| `version_contrato` | texto | Sí (automático) | Versión de este contrato | ✓ | ✓ | ✓ |
| `autor_hash` | texto (64) | No | SHA-256 con sal; 64 caracteres hexadecimales. Nunca el nombre real | ✓ | ✓ | |
| `calificacion` | entero | No | Entre 1 y 5 | ✓ | ✗ | ✗ |
| `likes` | entero | No | Mayor o igual a 0 (`thumbsUpCount` o `likeCount`) | ✓ | ✓ | |
| `version_app` | texto | No | `reviewCreatedVersion` | ✓ | ✗ | ✗ |
| `respuesta_marca` | texto | No | Respuesta de Rappi a la reseña | ✓ | ✗ | ✗ |
| `fecha_respuesta` | fecha y hora UTC | No | Cuándo respondió Rappi (`repliedAt`). Puede ser anterior a `fecha_publicacion` si la reseña se editó después | ✓ | ✗ | ✗ |
| `editada_tras_respuesta` | booleano | Calculado | `true` si `fecha_publicacion` es posterior a `fecha_respuesta`; `false` si tiene respuesta y no se editó; vacío si no tiene respuesta. No se envía: se calcula | ✓ | | |
| `fecha_edicion` | fecha y hora UTC | Calculado | Igual a `fecha_publicacion` cuando `editada_tras_respuesta` es `true`; si no, vacío. No se envía: se calcula | ✓ | | |
| `id_contenedor` | texto | No | ID del video (YouTube) | | ✓ | |
| `url` | texto | No | Enlace al video o, en noticias, la redirección de Google News, no la URL del medio | | ✓ | ✓ |
| `medio` | texto | No | Nombre del medio que publica la noticia | ✗ | ✗ | ✓ |

✓ se llena en esa fuente · ✗ prohibido en esa fuente (el registro se rechaza) · vacío: no aplica.

## Reglas generales

1. **Campos fuera del contrato están prohibidos.** Si un scraper intenta guardar `userName`, una foto de perfil o cualquier campo no listado, el registro se rechaza. Esto protege contra fugas de datos personales.
2. **Fechas en UTC e ISO 8601.** Una fecha sin zona horaria se asume UTC; una fecha con zona horaria (por ejemplo, hora de Colombia) se convierte a UTC. El dashboard convierte a hora de Colombia al mostrar.
3. **Autores seudonimizados.** El nombre se normaliza (espacios, mayúsculas, tildes) y se convierte con `hash_autor()` usando la sal `HASH_SALT` del `.env`. El mismo autor siempre produce el mismo hash, lo que permite detectar bots sin saber quién es.
4. **Una corrida, una fuente, un archivo.** Cada corrida de un scraper escribe un solo archivo JSON Lines con registros de una sola fuente y sin `id_registro` repetidos.
5. **Cambios al contrato.** Requieren Pull Request revisado por la responsable de Data Quality (Katalina), aviso al grupo y subir `VERSION_CONTRATO` en `schema.py`, porque afectan a todos los paquetes.

## Reseñas editadas en Google Play

Google Play no conserva la fecha original de una reseña: cuando el usuario la edita, `at` (nuestro `fecha_publicacion`) pasa a ser la fecha de la edición. Si Rappi ya había respondido, la respuesta queda con fecha anterior a la reseña.

- Hasta la versión 1.1.0 esas reseñas se **rechazaban**. En la primera corrida real (7 nov 2026) se perdieron 43 de 500 (8,6 %).
- Desde la 1.2.0 se aceptan y se marcan con `editada_tras_respuesta = true` y su `fecha_edicion`.
- **Límites:** no se puede saber la fecha original de la reseña, ni detectar ediciones en reseñas sin respuesta, ni ediciones hechas antes de que Rappi respondiera.
- **Versiones:** una reseña editada vuelve a aparecer como nueva en el scraper, con el mismo `id_registro`. La capa raw guarda todas las versiones y la limpieza (P2.3) conserva la más reciente por `id_registro`.

## Dónde se guarda

| Capa | Dónde | Formato | Quién escribe |
| --- | --- | --- | --- |
| `raw` | MinIO, bucket `MINIO_BUCKET`, ruta `raw/fuente=<fuente>/fecha=<AAAA-MM-DD>/run_<run_id>.jsonl` | JSON Lines | Scrapers, con `guardar_registros()` |
| `clean` | Postgres, esquema `clean` | Tablas | Limpieza y sentimiento (P2.3, P2.4) |
| `analytics` | Postgres, esquema `analytics` | Tablas y vistas de dbt | dbt (P3.4) |

La fecha de la partición es la fecha de extracción en UTC.

El scraper de noticias también escribe `state/fuente=news/enlaces_vistos.json` en el mismo bucket. Es su estado interno, no sigue este esquema y queda fuera de `raw/`, así que quienes lean la capa raw no deben procesarlo.

## Ejemplo de registro (una línea del archivo)

```json
{"fuente":"google_play","id_original":"gp-123","texto":"El pedido llegó tarde","fecha_publicacion":"2026-11-02T13:00:00Z","idioma":"es","pais":"co","fecha_extraccion":"2026-11-02T15:00:00Z","run_id":"20261102T150000Z-1a2b3c4d","version_scraper":"0.1.0","version_contrato":"1.3.0","autor_hash":"3f5a…(64 caracteres)","calificacion":2,"likes":null,"version_app":"9.1.0","respuesta_marca":null,"fecha_respuesta":null,"id_contenedor":null,"url":null,"medio":null,"id_registro":"google_play:gp-123","editada_tras_respuesta":null,"fecha_edicion":null}
```

## Historial

| Versión | Fecha | Cambio |
| --- | --- | --- |
| 1.0.0 | 2026-11-04 | Versión inicial (fuentes: Google Play, YouTube y Reddit) |
| 1.1.0 | 2026-11-04 | Se agrega la fuente `news` y el campo `medio`, porque el grupo eligió Google News como tercera fuente. Reddit sigue en el esquema hasta que se decida retirarlo |
| 1.2.0 | 2026-11-07 | Se aceptan las reseñas de Google Play editadas después de la respuesta de Rappi (antes se rechazaban) y se agregan los campos calculados `editada_tras_respuesta` y `fecha_edicion` |
| 1.3.0 | 2026-11-07 | Se retira Reddit: la fuente `reddit` y el campo `subreddit`. La tercera fuente es Google News, y Reddit cerró las nuevas solicitudes de acceso a su API (31 oct 2026) y su RSS (13 nov 2026). No había datos de Reddit guardados |
