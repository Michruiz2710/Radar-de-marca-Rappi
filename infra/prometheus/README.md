# Prometheus

Configuración de Prometheus y Pushgateway para recoger las métricas del pipeline.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.1 Métricas y logs | Sara | Gabriel | Jonathan | Semana 3 |

## Cómo funciona

El orquestador publica sus métricas en el Pushgateway al final de cada corrida, y Prometheus lee el Pushgateway cada 30 segundos (`honor_labels: true` conserva las etiquetas `fuente` y `flujo`). La lista de métricas está en `src/observability/README.md`.

| Servicio | Imagen | En tu computador |
| --- | --- | --- |
| `pushgateway` | `prom/pushgateway:v1.11.3` | http://localhost:9091 |
| `prometheus` | `prom/prometheus:v3.15.1` | http://localhost:9090 |

Los puertos se cambian con `PUSHGATEWAY_PORT` y `PROMETHEUS_PORT` en `.env`. Prometheus guarda 30 días de datos en el volumen `prometheus_data`, y el Pushgateway guarda lo último publicado en `pushgateway_data`.

Las reglas de alerta de P3.2 van en `reglas/` como archivos `.yml`; Prometheus las carga al arrancar.

## Cómo comprobarlo

1. `make up` y luego, en Prefect, correr el despliegue `todas-dev`.
2. Abrir http://localhost:9091: debe aparecer el grupo `job="radar_pipeline"`.
3. En http://localhost:9090, escribir `registros_extraidos_total` y hacer clic en **Execute**.

## Estado

Hecho. Falta comprobar en Docker el criterio de aceptación de P3.1.
