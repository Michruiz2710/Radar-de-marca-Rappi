# Modelos analíticos

Proyecto dbt que lee la capa clean de Postgres y deja en `analytics` las tablas que usa el dashboard de negocio (P3.3).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.4 Modelos analíticos con dbt | Gabriel | Sara | Katalina | Semana 3 |

## De dónde lee y dónde escribe

Lee dos tablas: `menciones`, que llena la limpieza (P2.3), y `sentimiento`, que llena P2.4. Escribe en el esquema de analytics del entorno. Los dos esquemas salen de `PG_SCHEMA_CLEAN` y `PG_SCHEMA_ANALYTICS` (`config/<entorno>.env`), así que el mismo proyecto sirve para dev, staging y prod sin cambiar nada.

## Modelos

Los de `staging/` son vistas y solo preparan columnas. Los de `marts/` son tablas y son los que debe leer el dashboard.

| Modelo | Una fila por | Para qué |
| --- | --- | --- |
| `stg_menciones` | mención | Día y semana en hora de Colombia, horas hasta la respuesta de Rappi y si el texto nombra la marca |
| `stg_sentimiento` | mención analizada | Sentimiento con puntaje 1, 0 o -1 para poder promediar |
| `fct_menciones` | mención real (sin bots) | Tabla base: datos de la mención con su sentimiento y tema |
| `agg_sentimiento_diario` | día y fuente | Positivas, neutras, negativas, porcentaje negativo e índice neto (de -1 a 1) |
| `agg_temas_semanal` | semana, fuente y tema | Top de quejas: ordenar por `negativas` |
| `agg_calificacion_version` | versión de la app (8.41, 8.42...) | Google Play: estrellas promedio, porcentaje de 1 y 2 estrellas y porcentaje negativo. Junta los builds diarios y marca con `muestra_suficiente` las versiones con 10 reseñas o más |
| `agg_respuesta_marca_semanal` | semana | Google Play: cuánto responde Rappi, también en reseñas de 1 y 2 estrellas, y en cuántas horas |
| `agg_noticias_vs_sentimiento` | día | Noticias publicadas frente a menciones negativas en redes y reseñas |
| `resumen_fuentes` | fuente | Totales de toda la historia: menciones, bots, analizadas y porcentaje que nombra la marca. `en_modelos` dice cuántas entran a las demás tablas |

Decisiones que conviene saber al leer estas tablas:

- Los bots se quitan en `fct_menciones`. Solo `resumen_fuentes` los cuenta.
- Las tablas finales tienen toda la historia: YouTube trae comentarios desde 2020 y las noticias llegan hasta 2018. El dashboard decide qué periodo mostrar con la columna `fecha` o `semana`. Si algún día se quiere recortar en dbt, existe la variable `dias_historia` (0 = sin recorte): `dbt build --vars '{dias_historia: 365}'`.
- Google Play publica casi un build por día (`8.42.20261030-90052`), así que las versiones se comparan por mayor y menor (`8.42`).
- El sentimiento se usa solo si es del texto actual. Si una reseña se editó y P2.4 todavía no la vuelve a analizar, queda con `analizada = false` y tema `sin_analizar`.
- Las fechas se agrupan en hora de Colombia (`zona_horaria` en `dbt_project.yml`). En clean están en UTC.
- Las reseñas editadas después de la respuesta de Rappi no tienen `horas_hasta_respuesta`: Google Play solo guarda la fecha de la edición y se pierde la original. `agg_respuesta_marca_semanal` las cuenta en `respondidas_editadas`, y `respondidas_con_tiempo` dice sobre cuántas respuestas se calcula la mediana.
- El nombre de cada tabla agregada termina en su periodo (`_diario`, `_semanal`) cuando lo tiene. Las que no lo tienen agrupan por otra cosa: versión, fuente o día con noticias.
- `menciona_marca` sirve sobre todo para YouTube, donde el filtro es por video y muchos comentarios hablan de Rappi sin nombrarla.

## Cómo se corre

En el pipeline, dbt es la última etapa de Prefect (`modelos`, en `flows/modelos.py`): después del sentimiento, cada corrida con datos nuevos ejecuta `dbt build`. Si una prueba falla, la etapa falla y el pipeline lo reporta. Las corridas de las tres fuentes pueden coincidir, así que dbt corre de a una.

A mano, con Postgres encendido y la capa clean cargada:

```bash
make dbt                  # dbt build: crea los modelos y corre las pruebas
make dbt ENTORNO=staging  # lo mismo contra los esquemas de staging
make dbt-docs             # documentación y linaje en http://localhost:8080 (Ctrl+C para cerrar)
```

Sin Docker, desde un entorno de Python 3.11:

```bash
pip install -r dbt/requirements-dbt.txt
cd dbt
POSTGRES_HOST=localhost POSTGRES_USER=... POSTGRES_PASSWORD=... dbt build --profiles-dir .
```

## Pruebas

`dbt build` construye 9 modelos y corre 44 pruebas (por eso al final dice `PASS=53`). Las pruebas revisan las fuentes (ids únicos, fuentes y sentimientos válidos, que cada sentimiento tenga su mención) y los modelos: llaves únicas, porcentajes entre 0 y 1, estrellas entre 1 y 5, que ningún bot llegue a `fct_menciones` y que el total de `resumen_fuentes` sea igual al de `clean.menciones`. Las pruebas propias están en `tests/` y `tests/generic/`.

En el CI, el job "Modelos dbt" levanta un Postgres y carga 9 menciones inventadas (`datos_ci.py`) con el mismo código de P2.3 y P2.4. Incluyen un bot, una mención en inglés, una reseña editada después de la respuesta y un sentimiento viejo. Después corre `dbt build` y revisa 8 resultados conocidos, por ejemplo que el bot no llegue a `fct_menciones` o que la mediana de respuesta sea 5 horas. Si alguien cambia una columna de clean o la lógica de un modelo, el job se pone en rojo.

## Estado

Hecho: 2 modelos de staging, 7 tablas finales, 44 pruebas, etapa `modelos` en Prefect, imagen Docker, `make dbt`, `make dbt-docs` y job en el CI con datos de prueba. Probado con los datos reales de dev (google_play, youtube y news).

Pendiente: la etapa de sentimiento (P2.4) todavía no está conectada a Prefect. Mientras tanto, dbt corre en el pipeline con el sentimiento que haya en `clean.sentimiento` (el de la última vez que alguien corrió `make nlp`).
