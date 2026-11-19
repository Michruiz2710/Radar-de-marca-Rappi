# Scripts

Utilidades del proyecto, incluido `simular_fallo.sh` para la demo.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P3.2 Alertas y dashboard técnico | Jonathan | Michelle | Sara | Semana 3 |

## `simular_fallo.sh`

Provoca un fallo para comprobar que las alertas funcionan y mide cuánto tarda Grafana en dispararlas. El criterio de P3.2 es que una alerta P0 llegue al canal en menos de 5 minutos. Necesita el entorno levantado (`make up`) y se puede correr desde cualquier carpeta del repositorio.

| Comando | Qué hace | Alerta | Tarda |
| --- | --- | --- | --- |
| `scripts/simular_fallo.sh inyectar` (o `inyectar A1`) | Publica en el Pushgateway un flujo con 2 corridas fallidas | A1 (P0) | menos de 1 min |
| `scripts/simular_fallo.sh inyectar A4` | Publica una validación crítica fallida (espera 40 s entre dos valores) | A4 (P0) | unos 2 min |
| `scripts/simular_fallo.sh inyectar A7` | Publica una cuota de YouTube de 8.500 unidades | A7 (P1) | 1 a 2 min |
| `scripts/simular_fallo.sh real` | Lanza 2 corridas reales en Prefect con una fuente inválida: fallan al instante | A1 (P0) | 1 a 2 min |
| `scripts/simular_fallo.sh minio` | Apaga MinIO: el scraper de noticias falla de verdad, pero agota sus reintentos | A1 (P0) | unos 5 min |
| `scripts/simular_fallo.sh restaurar` | Borra lo simulado, limpia el flujo simulado y enciende MinIO si estaba apagado | — | segundos |

- **`inyectar`** publica en un grupo aparte del Pushgateway (`radar_simulacion`), así que no toca las métricas reales ni el estado del pipeline. Es la opción segura y rápida para ensayar. Aparece en el dashboard como un flujo `pipeline:simulacion` (A1) o como una serie extra (A4, A7).
- **`real`** es la que recomiendo para la demo: las corridas se ven en **Runs** de Prefect en estado *Failed*, pasan por el gancho de fallo real y el dashboard cuenta las fallas, igual que en un fallo verdadero. El flujo aparece como `pipeline:simulacion`, así que no se mezcla con `pipeline:news` ni con los demás.
- **`minio`** es lo más parecido a la caída de un servicio: sin MinIO, la tarea `extraer_news` falla, reintenta y la corrida termina en error. Pero cada corrida tarda unos 5 minutos en agotar los reintentos (en pruebas fueron 4,5), más que el criterio de P3.2. Úsalo para mostrar el fallo en Prefect, no para medir el tiempo. Pide confirmación antes de apagar nada y deja a `pipeline:news` con fallas hasta que corra una corrida exitosa de noticias.
- **Después de cada simulación** corre `restaurar`. Las alertas se resuelven en un par de minutos y Grafana envía el aviso `[RESOLVED]`.

El script imprime el tiempo que tardó la alerta en estar en estado *Firing* en Grafana (lo consulta con el usuario y la contraseña de `.env`). El correo sale en segundos después de eso; la confirmación final es que llegue a la bandeja.

Variables opcionales: `ENTORNO` (`dev` por defecto), `PUSHGATEWAY_PORT`, `GRAFANA_PORT`, `GRAFANA_ADMIN_USER` y `GRAFANA_ADMIN_PASSWORD`. Sin ellas, las lee de `.env`.

Necesita `bash`, `curl` y `docker`; con `python` además mide el tiempo (sin él, la simulación funciona pero hay que mirar Grafana a mano). En Windows, correrlo con Git Bash.

### Ensayo general para la demo

1. `make up` y deja que el pipeline haya corrido al menos una vez (para que el dashboard tenga datos).
2. Abre el dashboard y tu bandeja de entrada.
3. `scripts/simular_fallo.sh real` (o `inyectar A1`). Debe imprimir `Firing` y llegar el correo.
4. `scripts/simular_fallo.sh restaurar` y espera el correo `[RESOLVED]`.

Si usas Gmail como remitente, desactiva el escaneo SSL del correo en tu antivirus o pon `GRAFANA_SMTP_SKIP_VERIFY=true` en `.env` (ver `infra/grafana/README.md`).

## Estado

Hecho: `simular_fallo.sh` con los modos `inyectar` (A1, A4 y A7), `real`, `minio` y `restaurar`. Probado en un entorno Docker aparte: `inyectar A1` disparó A1 en 28 s, `inyectar A4` en 108 s, `inyectar A7` en 74 s y `real` en 74 s; `minio` provoca la falla real pero tarda unos 5 min.
