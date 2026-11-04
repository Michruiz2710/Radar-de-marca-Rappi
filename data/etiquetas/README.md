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

## Cómo se usa

```bash
python data/etiquetas/preparar_muestra.py --desde-csv <csv_de_katalina>   # o sin --desde-csv para descargar
# etiquetar data/etiquetas/muestra_200_para_etiquetar.xlsx
python data/etiquetas/validar_muestra.py data/etiquetas/muestra_200_para_etiquetar.xlsx
```

La muestra toma 40 reseñas por estrella para tener casos de todos los tipos; por eso la exactitud de P2.4 mide una muestra equilibrada, no la distribución real de la app. Los correos y teléfonos escritos en las reseñas quedan enmascarados.

## Estado

Pendiente: etiquetar las 200 reseñas. Hay un valor adicional a los 6 temas, `sin_tema`, por confirmar con Jonathan para P2.4.
