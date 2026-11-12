# Contrato de la capa clean

**Versión de la limpieza:** 1.2.0 · **Autora:** Michelle (P2.3) · **Acordado en la reunión del 9 de noviembre de 2026**

La limpieza lee la capa raw (MinIO) y deja una fila por mención en la tabla `menciones` de Postgres. De esta tabla leen las validaciones (P2.2), el sentimiento (P2.4) y los modelos de dbt (P3.4). Está implementada en [`src/transform/clean/tabla.py`](../src/transform/clean/tabla.py); si este documento y el código no coinciden, manda el código.

## Dónde está

| Entorno | Esquema | Tabla |
| --- | --- | --- |
| dev | `clean` | `clean.menciones` |
| staging | `clean_staging` | `clean_staging.menciones` |
| prod | `clean_prod` | `clean_prod.menciones` |

El esquema sale de la variable `PG_SCHEMA_CLEAN` (ver `config/<entorno>.env`). En el código, usen siempre `src.common.db.esquema_clean()`, nunca el nombre fijo.

## Garantías

1. **Una fila por `id_registro`** (llave primaria). Si una mención llega varias veces, queda la versión más reciente: la de `fecha_publicacion` mayor (reseña editada) o, si es igual, la de `fecha_extraccion` mayor.
2. **Sin datos personales a la vista.** El texto original no se copia: solo `texto_limpio`, con correos, teléfonos y números de 7 o más dígitos enmascarados. La respuesta de Rappi también se enmascara. El texto original sigue en la capa raw, con acceso restringido.
3. **Los bots no se borran:** quedan con `es_bot = true` y el motivo en `motivo_bot`.
4. **Idempotente:** volver a limpiar los mismos archivos no cambia nada.
5. **Trazable:** cada fila dice de qué corrida de scraping viene (`run_id`), con qué versión del scraper, del contrato y de la limpieza se procesó, y cuándo (`procesado_en`).

## Columnas

| Columna | Tipo | Nulo | Descripción |
| --- | --- | --- | --- |
| `id_registro` | texto | No | `<fuente>:<id_original>`. Llave primaria |
| `fuente` | texto | No | `google_play`, `youtube` o `news` |
| `id_original` | texto | No | ID en la plataforma de origen |
| `texto_limpio` | texto | No | Texto normalizado y con datos personales enmascarados: `[CORREO]`, `[TELEFONO]`, `[NUMERO]`, `[URL]`. Conserva mayúsculas, signos y emojis, incluidos los compuestos (👨‍👩‍👧, 👩‍🍳). Nunca queda vacío: si al limpiar no queda texto visible, la fila se descarta y se registra en el log |
| `hash_texto` | texto (64) | No | SHA-256 de `texto_limpio`. Si cambia, el texto cambió (por ejemplo, reseña editada) y hay que volver a analizarlo |
| `idioma_consulta` | texto | No | Idioma que se pidió a la fuente (`es`) |
| `idioma_detectado` | texto | No | Idioma real del texto: `es`, `pt` o `en`. Si el texto no da pistas (por ejemplo "excelente"), se asume el de la consulta |
| `pais` | texto | No | País de la consulta (`co`), no el del autor |
| `fecha_publicacion` | fecha UTC | No | En Google Play, fecha de la versión actual de la reseña |
| `fecha_extraccion` | fecha UTC | No | Cuándo la recolectó el scraper |
| `autor_hash` | texto (64) | Sí | Autor seudonimizado. Vacío en noticias |
| `calificacion` | entero | Sí | 1 a 5. Solo Google Play |
| `likes` | entero | Sí | |
| `version_app` | texto | Sí | Solo Google Play |
| `respuesta_marca` | texto | Sí | Respuesta de Rappi, enmascarada. Solo Google Play |
| `fecha_respuesta` | fecha UTC | Sí | Solo Google Play |
| `editada_tras_respuesta` | booleano | Sí | Recalculado en la limpieza, también para archivos anteriores al contrato v1.2.0 |
| `fecha_edicion` | fecha UTC | Sí | |
| `id_contenedor` | texto | Sí | ID del video (YouTube) |
| `url` | texto | Sí | |
| `medio` | texto | Sí | Solo noticias |
| `es_bot` | booleano | No | `true` si alguna regla de bots lo marcó |
| `motivo_bot` | texto | Sí | Motivos separados por coma (ver abajo) |
| `run_id` | texto | No | Corrida de scraping de donde viene la versión guardada |
| `version_scraper` | texto | Sí | |
| `version_contrato` | texto | Sí | Versión del contrato con que se guardó en raw |
| `version_limpieza` | texto | No | Versión de las reglas de limpieza |
| `procesado_en` | fecha UTC | No | Cuándo se limpió |

## Reglas de bots

| Motivo | Regla |
| --- | --- |
| `multiples_enlaces` | Dos o más enlaces en el texto |
| `promocional` | Enlaces o frases típicas de spam (`bit.ly/`, `t.me/`, "visita mi canal"...). Las frases de dinero ("gana dinero", "ingresos extra") solo cuentan si el texto trae un enlace, porque entre repartidores son conversación normal |
| `texto_repetido_autor` | El mismo autor publicó el mismo texto más de una vez |
| `campana_varios_autores` | El mismo texto, de 40 caracteres o más, lo publicaron 3 o más autores. Las frases cortas o genéricas no cuentan, porque mucha gente real las escribe igual |
| `rafaga` | 5 o más comentarios del mismo autor en 10 minutos, en 3 o más videos distintos. Una persona conversando en un mismo video no cuenta |

Las noticias nunca se marcan como bot. Las reglas comparan los registros de una misma tanda de limpieza.

## Resumen de cada carga

`limpiar()` devuelve y registra en el log un resumen con: `leidos`, `descartados`, `duplicados`, `idiomas`, `nuevos`, `actualizados`, `sin_cambios`, `archivos` y los bots:

- `bots` y `bots_por_fuente`: cantidad de filas marcadas como bot.
- `pct_bots` y `pct_bots_por_fuente`: porcentaje de bots sobre las filas limpias de la tanda (0 a 100). Alimentan la métrica `registros_bot_ratio` de la observabilidad (P3.1).

## Limitaciones conocidas

- **Ráfaga solo entre videos.** La regla `rafaga` exige comentarios en 3 o más videos distintos. Un bot que comente muchas veces en un solo video, o en Google Play (que no tiene `id_contenedor`), no se marca por esa regla. Sí lo marca `texto_repetido_autor` si repite el mismo texto.
- **Reglas de bots dentro de una tanda.** Las reglas comparan solo los registros de la misma tanda de limpieza. Un autor que repite texto en corridas distintas del orquestador no se detecta; solo lo detecta la carga histórica, que procesa todo junto. Seguimiento en un issue aparte: consultar el historial de autores en la tabla y actualizar las filas ya cargadas.
- **Idioma.** Solo distingue español, portugués e inglés, que son los que aparecen en las fuentes.
- **Nombres propios.** Se enmascaran correos, teléfonos y números largos, pero no nombres ("soy Ana Pérez"), que no se pueden detectar de forma confiable con reglas.
- **Comentarios fuera de tema.** Algunos videos nombran a Rappi en el título, pero sus comentarios no hablan de la marca (por ejemplo, videos musicales). No son bots y se conservan; la clasificación por tema (P2.4) puede dejarlos como "otro".

## Para quien lee la tabla

- **Sentimiento (P2.4):** analizar solo `idioma_detectado = 'es'` y `es_bot = false`. Guardar en `clean.sentimiento` el `hash_texto` analizado y volver a analizar cuando no coincida con el de `menciones`.
- **Validaciones (P2.2):** las garantías de arriba son las que deben comprobarse en `validar_limpia`.
- **dbt (P3.4):** leer siempre desde `{{ source('clean', 'menciones') }}`, con el esquema del entorno.

## Historial

| Versión | Fecha | Cambio |
| --- | --- | --- |
| 1.0.0 | 2026-11-10 | Versión inicial |
| 1.2.0 | 2026-11-11 | Revisión de Jonathan: se conservan los emojis compuestos (antes se quitaba el ZWJ, U+200D, y se partían); se descartan las filas cuyo texto queda vacío al limpiarlo; el resumen reporta el porcentaje de bots total y por fuente |
| 1.1.0 | 2026-11-10 | Con los datos reales (11.090 filas), las reglas `rafaga` y `promocional` marcaban personas reales: 530 por conversar en un video y 33 repartidores hablando de ganancias. Ahora la ráfaga exige 3 o más videos distintos, y las frases de dinero exigen un enlace |
