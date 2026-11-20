# Documentación

Contrato de datos, catálogo de datos, linaje, política de Habeas Data y guía de etiquetado.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P1.2 (contrato) y P3.5 (gobierno, linaje y cierre) | Michelle | Katalina | Gabriel | Semanas 1 y 3 |

## Documentos

| Documento | Qué contiene | Paquete |
| --- | --- | --- |
| [`contrato_datos.md`](contrato_datos.md) | Campos y reglas de la capa raw (v1.3.0) | P1.2 |
| [`contrato_clean.md`](contrato_clean.md) | Tabla `menciones` de la capa clean, reglas de bots | P2.3 |
| [`evaluacion_nlp.md`](evaluacion_nlp.md) | Exactitud del sentimiento y los temas | P2.4 |
| [`catalogo_datos.md`](catalogo_datos.md) | Todos los datos: dueño, ubicación, sensibilidad y retención | P3.5 |
| [`linaje.md`](linaje.md) | Recorrido de los datos de la fuente al dashboard | P3.5 |
| [`politica_datos.md`](politica_datos.md) | Habeas Data: principios, reglas, derechos, borrado e incidentes | P3.5 |
| [`runbooks/`](runbooks/README.md) | Qué hacer ante cada alerta (A1–A8) | P3.2 |

## Estado

P3.5 hecho: catálogo de datos con las capas raw, clean y analytics y la observabilidad; linaje de punta a punta con los modelos reales de dbt; política de Habeas Data; README final con la tabla de contribuciones. Los Data Docs de Great Expectations ahora se guardan en `data/data_docs/`.

**Decisión pendiente del equipo:** qué hacer con `data/etiquetas/muestra_200.csv` en el repositorio público (ver el riesgo en el catálogo).
