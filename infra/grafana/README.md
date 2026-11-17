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
| `provisioning/alerting/reglas.yml` | Las 7 reglas de alerta A1–A7 |
| `provisioning/alerting/contactpoints.yml` | Punto de contacto: correo del grupo |
| `provisioning/alerting/policies.yml` | Cuánto tarda cada prioridad en avisar y cada cuánto se repite |
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

## Alertas

Grafana evalúa las reglas cada minuto sobre las métricas de Prometheus y avisa al punto de contacto. Cada regla dispara cuando su expresión devuelve un valor mayor que 0 y lleva la etiqueta `severidad` y la anotación `runbook` con su guía en `docs/runbooks/`.

| ID | Prioridad | Condición | Espera antes de avisar |
| --- | --- | --- | --- |
| A1 | P0 | `fallas_consecutivas >= 2` en algún flujo | 0 s |
| A2 | P0 | Google Play sin registros nuevos en 6 h | 0 s |
| A3 | P0 | Sin corrida exitosa hace más del doble del intervalo: news 4 h, Google Play 6 h, YouTube 12 h | 0 s |
| A4 | P0 | Una validación crítica falló en la última hora | 0 s |
| A5 | P1 | `sentimiento_negativo_24h_ratio > 0,6` | 10 min |
| A6 | P1 | Menciones de hoy > 2 × el promedio diario de 7 días (solo con 7 días de historia) | 10 min |
| A7 | P1 | `cuota_youtube_usada > 8000` | 0 s |

Las P0 se envían de inmediato y se repiten cada hora mientras sigan activas; las P1 esperan 30 s y se repiten cada 12 h. Cuando una alerta se resuelve, Grafana también avisa. La alerta A3 no vigila el flujo manual `pipeline`, porque no tiene horario.

### Configurar el correo

Las alertas llegan por correo. Grafana necesita una cuenta que envíe y una lista de destinatarios, las dos en tu `.env` (son secretos: no van en Git; para staging y prod van en los GitHub Environments):

| Variable | Qué es |
| --- | --- |
| `ALERTAS_CORREO_DESTINO` | Quién recibe las alertas. Varias direcciones se separan con `;` |
| `GRAFANA_SMTP_HOST` | Servidor de correo. Para Gmail, `smtp.gmail.com:587` (ya viene en `.env.example`) |
| `GRAFANA_SMTP_USER` | Cuenta que envía, por ejemplo la de Gmail del grupo |
| `GRAFANA_SMTP_PASSWORD` | Para Gmail, una **contraseña de aplicación**, no la contraseña de la cuenta |

Con Gmail: activa la verificación en dos pasos en la cuenta que envía y crea la contraseña en https://myaccount.google.com/apppasswords. Luego reinicia Grafana:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env up -d grafana
```

Si faltan el usuario, la contraseña o los destinatarios, Grafana arranca igual pero las alertas no llegan a nadie. Para ver si se enviaron, mira **Alerting → Contact points** (el estado de cada envío) y **Alert rules**.

**Si el correo no llega y el log de Grafana dice `x509: certificate signed by unknown authority`:** un antivirus está interceptando la conexión con Gmail y reemplaza su certificado (en Windows pasa con Avast: «Mail Shield»). Comprueba el log con `docker logs radar-rappi-grafana-1 | grep "failed to send email"`. Hay dos salidas:

1. **Mejor:** en el antivirus, desactiva el escaneo SSL del correo saliente (en Avast: Ajustes → Protección → Escudos principales → Escudo de correo → desmarca «Analizar correo saliente» y el escaneo SSL).
2. **Solo en desarrollo:** `GRAFANA_SMTP_SKIP_VERIFY=true` en tu `.env`. Grafana deja de verificar el certificado del servidor de correo, así que no lo uses en staging ni en prod.

### Cambiar el punto de contacto

Para usar Discord en lugar de correo, o además, en `contactpoints.yml` agrega un receptor `type: discord` con `settings.url` apuntando a una variable de `.env` (el webhook se crea en **Ajustes del canal → Integraciones → Webhooks**), y en `policies.yml` añade ese receptor a las rutas.

### Qué se comprobó

Con un servidor de correo de prueba en el computador (Mailpit), métricas falsas en el Pushgateway y Grafana en Docker: el correo de A1 llegó unos 60 segundos después de publicar dos corridas fallidas, con resumen, descripción y runbook, y los avisos de A4 y A7 llegaron en menos de 2 minutos con el mismo mecanismo. Todo dentro de los 5 minutos del criterio de aceptación. También se probó con una cuenta real de Gmail: el correo de A1 llegó a la bandeja del destinatario.

## Estado

Hecho: Grafana en el compose, fuente de datos y dashboard técnico como código, reglas A1–A7, correo como punto de contacto y políticas de notificación.

**Pendiente (siguiente commit de P3.2):** runbooks en `docs/runbooks/` y `scripts/simular_fallo.sh`.
