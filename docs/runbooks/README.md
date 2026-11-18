# Runbooks

Una página por alerta: qué significa y qué hacer.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.2 Alertas y dashboard técnico | Jonathan | Michelle | Sara | Semana 3 |

## Alertas

P0 significa que el sistema dejó de funcionar y hay que actuar ya; P1, que funciona pero hay algo importante que revisar. Las reglas están en `infra/grafana/provisioning/alerting/reglas.yml`; cada una lleva en el correo la anotación `runbook` con el archivo de esta tabla.

| ID | Prioridad | Qué pasó | Runbook |
| --- | --- | --- | --- |
| A1 | P0 | Un flujo falla 2 corridas seguidas | [A1_flujo_falla.md](A1_flujo_falla.md) |
| A2 | P0 | Google Play extrae 0 reseñas en 6 horas | [A2_google_play_sin_resenas.md](A2_google_play_sin_resenas.md) |
| A3 | P0 | Ningún flujo exitoso en más del doble de su intervalo | [A3_flujo_detenido.md](A3_flujo_detenido.md) |
| A4 | P0 | Falla una validación crítica | [A4_validacion_critica.md](A4_validacion_critica.md) |
| A5 | P1 | Sentimiento negativo de 24 h supera el 60 % | [A5_sentimiento_negativo.md](A5_sentimiento_negativo.md) |
| A6 | P1 | Menciones del día superan 2 veces el promedio de 7 días | [A6_pico_de_menciones.md](A6_pico_de_menciones.md) |
| A7 | P1 | Cuota de YouTube usada supera el 80 % | [A7_cuota_youtube.md](A7_cuota_youtube.md) |
| A8 | P0 | Prometheus no ve el Pushgateway (extra: sin él, A1 a A7 quedan ciegas) | [A8_pushgateway_caido.md](A8_pushgateway_caido.md) |

## Antes de empezar

- **Dónde mirar:** el dashboard «Pipeline técnico» en Grafana (http://localhost:3000), la UI de Prefect (http://localhost:4200) y los logs del orquestador. Los logs son JSON y llevan `run_id` y `fuente`.
- **Comandos:** los de los runbooks usan el entorno `dev` y están escritos para correr desde la raíz del repositorio. En staging o prod cambia `config/dev.env` por el del entorno y el sufijo `-dev` de los despliegues.
- **Si una alerta se repite** y ya la atendiste, el correo vuelve a llegar cada hora (P0) o cada 12 horas (P1) mientras la condición siga activa. Cuando se resuelve llega un correo `[RESOLVED]`.
- **Después de un incidente,** anota en el canal del grupo qué pasó y qué lo arregló; si falta algo en el runbook, corrígelo en el mismo PR.

## Estado

Hecho: los siete runbooks de la ruta de trabajo (A1 a A7) y el de A8, una alerta extra, con comprobación de que cada regla apunta a uno que existe (`tests/observability/test_runbooks.py`).
