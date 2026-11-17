# Grafana

Dashboard técnico y reglas de alerta P0/P1 guardados como código (provisioning).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.2 Alertas y dashboard técnico | Jonathan | Michelle | Sara | Semana 3 |

## Qué hay aquí

| Ruta | Qué hace |
| --- | --- |
| `provisioning/datasources/prometheus.yml` | Conecta Grafana con el Prometheus del compose (uid `prometheus`) |
| `provisioning/dashboards/dashboards.yml` | Carga los dashboards de la carpeta `dashboards/` al arrancar |
| `dashboards/pipeline_tecnico.json` | Dashboard «Pipeline técnico» |

Nada se crea a mano en la interfaz: si cambias algo ahí, se pierde. Para modificar un panel, edita el JSON y Grafana lo recarga en unos 30 segundos.

## Cómo se abre

Con `make up`, en http://localhost:3000 (cambia el puerto con `GRAFANA_PORT`). El usuario y la contraseña salen de `GRAFANA_ADMIN_USER` y `GRAFANA_ADMIN_PASSWORD` en `.env`; si tu `.env` es anterior a P3.2, agrega esas variables desde `.env.example`. El dashboard está en la carpeta **Radar Rappi**.

## Dashboard «Pipeline técnico»

| Panel | Métrica | Alerta |
| --- | --- | --- |
| Fallas consecutivas | `fallas_consecutivas` | A1 |
| Cuota de YouTube usada hoy | `cuota_youtube_usada` | A7 |
| Sentimiento negativo (24 h) | `sentimiento_negativo_24h_ratio` | A5 |
| Bots filtrados (24 h) | `registros_bot_ratio` | — |
| Registros extraídos por fuente | `registros_extraidos_total` | A2, A6 |
| Errores HTTP por fuente y código | `errores_http_total` | — |
| Duración promedio de la corrida | `duracion_corrida_segundos` | — |
| Validaciones fallidas | `validaciones_fallidas_total` | A4 |
| Última corrida exitosa | `ultima_corrida_exitosa_timestamp` | A3 |

Los contadores se muestran como lo ocurrido en la última hora (`increase`). Con pocas corridas, esos paneles aparecen casi vacíos hasta que haya al menos dos publicaciones de cada serie.

## Estado

Hecho: Grafana en el compose, fuente de datos y dashboard técnico como código. Comprobado en Docker con métricas de prueba en el Pushgateway.

**Pendiente (siguientes commits de P3.2):** reglas de alerta A1–A7, punto de contacto, runbooks en `docs/runbooks/` y `scripts/simular_fallo.sh`.
