# Muestra etiquetada

`muestra_200.csv`: 200 reseñas etiquetadas a mano (sentimiento y tema) para validar el modelo. Únicos datos que se versionan; sin nombres de autores.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.5 Scraper de noticias y etiquetado | Sara | Gabriel | Jonathan | Semana 1 |

## Qué hay aquí

| Archivo | Qué hace |
| --- | --- |
| `guia_etiquetado.md` | Criterios de sentimiento y tema |
| `preparar_muestra.py` | Selecciona 200 reseñas y crea el Excel con listas desplegables (Git lo ignora) |
| `validar_muestra.py` | Revisa el Excel y genera `muestra_200.csv` |
| `etiquetas_comun.py` | Valores permitidos y enmascarado que usan los dos scripts |

## Cómo se usa

```bash
pip install -r requirements.txt
python data/etiquetas/preparar_muestra.py --desde-csv <csv_de_katalina>   # o sin --desde-csv para descargar
# etiquetar data/etiquetas/muestra_200_para_etiquetar.xlsx
python data/etiquetas/validar_muestra.py data/etiquetas/muestra_200_para_etiquetar.xlsx
```

## Qué tan representativa es

El script busca 40 reseñas por estrella y completa al azar cuando una estrella no alcanza. Por eso la muestra **no quedó equilibrada** ni refleja la distribución real de la app:

| Estrellas | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| Reseñas | 52 | 41 | 40 | 25 | 42 |

| Sentimiento | Negativo | Positivo | Neutro |
| --- | --- | --- | --- |
| Reseñas | 140 | 42 | 18 |

**Para P2.4:** con tan pocas neutras, la exactitud global dice poco de esa clase. Conviene reportar también el resultado por clase, y no generalizar la cifra a toda la app.

## Procedencia y alcance

- **Origen:** descarga directa de Google Play con `preparar_muestra.py`, el 4 de noviembre de 2026, sin el CSV de Katalina. Se pidieron las 2000 reseñas más recientes; no quedó registro de cuántas llegaron ni de cuántas se descartaron. Como Google Play devuelve lo más reciente, repetir la descarga da otra muestra aunque la semilla sea la misma.
- **País:** `country="co"` no garantiza reseñas de Colombia. Al menos las filas 19, 42, 48, 121 y 159 parecen de Perú o Argentina, y puede haber más, porque solo se ve cuando el texto lo menciona. Se conservan porque la muestra evalúa si el modelo acierta el sentimiento y el tema en español; **no sirve para medir la opinión de Colombia**.
- **Fechas:** `fecha_publicacion` no tiene zona horaria y conserva la hora local del computador que descargó (Colombia, UTC-5).
- **Datos personales:** los correos y los teléfonos escritos en las reseñas se enmascaran. Los números en grupos de tres, como `300 123 456`, se tratan como montos y no se tapan. Ninguna fila de esta muestra quedó enmascarada.

## Estado

Las etiquetas las hicieron a mano Sara (filas 2 a 101) y Gabriel (filas 102 a 201). Además de los 6 temas, se usa `otro` para las reseñas generales, según lo definido para P2.4.
