# Evaluación de sentimiento y temas (P2.4)

Generado el 2026-11-12 con `python -m src.transform.nlp.evaluacion`.

- **Modelo:** `pysentimiento/robertuito-sentiment-analysis@a2cc0f67ebd705c55191e25a05ba23d885fcc09b|pysentimiento==0.7.3`
- **Versión del código NLP:** 0.1.0
- **Reseñas evaluadas:** 200 (`data/etiquetas/muestra_200.csv`)
- **Texto evaluado:** limpio (`limpiar_texto` de P2.3 es lo que analiza el pipeline)

## Cómo leer estas cifras

- La muestra **no es representativa** de la app (140 negativas, 42 positivas, 18 neutras): la
  exactitud global dice poco de las clases pequeñas. Mira la tabla por clase.
- **F1 macro** es el promedio del F1 de cada clase, todas con el mismo peso. Si es mucho más bajo que
  la exactitud, alguna clase pequeña está fallando aunque el total se vea bien.
- **Tema real entre los detectados** acepta el acierto si el tema etiquetado aparece entre todos los
  temas que el diccionario encontró, no solo como principal. Una reseña suele hablar de varios temas
  y la guía pide elegir el que la motivó, algo que un diccionario no puede saber. Es más generosa que
  la exactitud: se reporta como complemento, no como reemplazo. `otro` acierta solo si no se detectó nada.
- El diccionario de temas se ajustó mirando solo las filas 2 a 101 (etiquetó Sara). Las filas
  102 a 201 (Gabriel) no se usaron para ajustarlo; es la cifra que mejor estima el desempeño real.

## Sentimiento

**Exactitud: 87.0 % · F1 macro: 74.2 %**

| Clase | Precisión | Exhaustividad | F1 | Soporte |
| --- | --- | --- | --- | --- |
| positivo | 88.9 % | 76.2 % | 82.1 % | 42 |
| neutro | 38.5 % | 55.6 % | 45.5 % | 18 |
| negativo | 95.7 % | 94.3 % | 95.0 % | 140 |

Matriz de confusión:

| real \ predicho | positivo | neutro | negativo |
| --- | --- | --- | --- |
| **positivo** | 32 | 9 | 1 |
| **neutro** | 3 | 10 | 5 |
| **negativo** | 1 | 7 | 132 |

## Temas (diccionario de palabras clave)

**Exactitud: 57.5 % · F1 macro: 54.3 %**

**Tema real entre los detectados: 73.5 %** (métrica permisiva, ver arriba).

| Clase | Precisión | Exhaustividad | F1 | Soporte |
| --- | --- | --- | --- | --- |
| cobros_y_pagos | 48.9 % | 76.7 % | 59.7 % | 30 |
| repartidores | 33.3 % | 22.2 % | 26.7 % | 9 |
| soporte | 62.5 % | 58.8 % | 60.6 % | 17 |
| precios | 54.5 % | 66.7 % | 60.0 % | 9 |
| app | 80.0 % | 37.5 % | 51.1 % | 64 |
| entregas | 62.7 % | 74.4 % | 68.1 % | 43 |
| otro | 46.2 % | 64.3 % | 53.7 % | 28 |

Matriz de confusión:

| real \ predicho | cobros_y_pagos | repartidores | soporte | precios | app | entregas | otro |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **cobros_y_pagos** | 23 | 0 | 1 | 0 | 0 | 6 | 0 |
| **repartidores** | 2 | 2 | 0 | 0 | 0 | 1 | 4 |
| **soporte** | 4 | 0 | 10 | 0 | 2 | 1 | 0 |
| **precios** | 2 | 0 | 0 | 6 | 0 | 0 | 1 |
| **app** | 7 | 3 | 3 | 3 | 24 | 9 | 15 |
| **entregas** | 6 | 0 | 1 | 1 | 2 | 32 | 1 |
| **otro** | 3 | 1 | 1 | 1 | 2 | 2 | 18 |

## Por quién etiquetó

| Etiquetó | Reseñas | Exactitud sentimiento | Exactitud tema | Tema real entre los detectados |
| --- | --- | --- | --- | --- |
| gabriel | 100 | 90.0 % | 51.0 % | 67.0 % |
| sara | 100 | 84.0 % | 64.0 % | 80.0 % |

## Sentimiento frente a estrellas

Regla de comparación: 1-2 estrellas = negativo, 3 = neutro, 4-5 = positivo.

| Estrellas | positivo | neutro | negativo |
| --- | --- | --- | --- |
| 1 | 0 | 1 | 51 |
| 2 | 0 | 3 | 38 |
| 3 | 1 | 6 | 33 |
| 4 | 7 | 5 | 13 |
| 5 | 28 | 11 | 3 |

- Coincidencia entre el modelo y la regla de estrellas: **65.0 %**.
- Coincidencia entre las etiquetas humanas y la misma regla: **67.0 %**
  (referencia: así de lejos queda el humano de las estrellas).
- Reseñas de 1-2 estrellas que el modelo ve positivas: 0.
- Reseñas de 4-5 estrellas que el modelo ve negativas: 16.

## Efecto de la limpieza (P2.3)

Misma muestra y mismo modelo; cambia solo el texto que se analiza.

| Métrica | Texto original | Texto limpio |
| --- | --- | --- |
| Sentimiento: exactitud | 87.0 % | 87.0 % |
| Sentimiento: F1 macro | 74.2 % | 74.2 % |
| Temas: exactitud | 57.5 % | 57.5 % |
| Temas: F1 macro | 54.3 % | 54.3 % |
| Temas: real entre los detectados | 73.5 % | 73.5 % |
