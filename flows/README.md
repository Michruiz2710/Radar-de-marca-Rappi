# Flujos de Prefect

Orquestación: un flujo por fuente y un flujo principal ingesta → validación cruda → limpieza → validación limpia → sentimiento.

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.1 Orquestación | Sara | Katalina | Gabriel | Semana 2 |

## Qué hay aquí

| Archivo | Qué hace |
| --- | --- |
| `pipeline.py` | Flujo `pipeline` y un flujo de ingesta por fuente (`ingesta_google_play`, `ingesta_youtube`, `ingesta_news`) |
| `fuentes.py` | Llama al scraper de cada fuente |
| `entornos.py` | Parámetros de dev, staging y prod: intervalos y reintentos |
| `metricas.py` | Ganchos de éxito y fallo que publican métricas en el Pushgateway |
| `servir.py` | Registra los despliegues en Prefect y los deja corriendo |
| `Dockerfile` | Imagen del servicio `orquestador` |

## Cómo funciona

`servir.py` crea un despliegue por fuente. Cada uno corre `pipeline` solo para esa fuente:

| Despliegue | Cada | Qué corre |
| --- | --- | --- |
| `news-<entorno>` | 2 horas | Ingesta de noticias y las etapas siguientes |
| `google_play-<entorno>` | 3 horas | Ingesta de Google Play y las etapas siguientes |
| `youtube-<entorno>` | 6 horas | Ingesta de YouTube y las etapas siguientes |
| `todas-<entorno>` | Manual | Las tres fuentes y las etapas siguientes |

- **Reintentos:** cada tarea reintenta 3 veces con espera creciente: 10, 20 y 40 s en dev; 30, 60 y 120 s en staging; 60, 120 y 240 s en prod.
- **Entorno:** se elige con `APP_ENV` (`dev` por defecto).
- **YouTube sin clave:** si `YOUTUBE_API_KEY` está vacía, la fuente se omite con un aviso y el flujo no falla.
- **Métricas:** al terminar, el gancho publica `ultima_corrida_exitosa_timestamp` o `ultima_corrida_fallida_timestamp`, y `fallas_consecutivas`, con la etiqueta `flujo` (por ejemplo `pipeline:news`). La alerta A1 de P3.2 puede usar `fallas_consecutivas >= 2`. Si el Pushgateway no responde, solo queda un aviso en el log.

## Etapas de otros paquetes

Las etapas se conectan por nombre. Mientras el módulo no exista, la etapa queda `pendiente` y el pipeline sigue. Cuando exista, recibe un diccionario `{fuente: ruta}` con las rutas guardadas en esta corrida (`None` si no hubo datos nuevos). Si lanza un error, el pipeline se detiene: así se aplican las validaciones críticas.

| Etapa | Función esperada | Paquete |
| --- | --- | --- |
| Validación cruda | `quality.checkpoints:validar_cruda(rutas)` | P2.2 |
| Limpieza | `src.transform.clean.limpieza:limpiar(rutas)` | P2.3 |
| Validación limpia | `quality.checkpoints:validar_limpia(rutas)` | P2.2 |
| Sentimiento | `src.transform.nlp.sentimiento:analizar(rutas)` | P2.4 |

Los nombres son una propuesta. Si un paquete usa otro, basta con cambiar `ETAPAS` en `pipeline.py`.

## Cómo se corre

Con el entorno levantado (`docker compose -f infra/docker-compose.yml --env-file .env up -d`), el servicio `orquestador` registra los despliegues y los corre solo. Para verlos, abre http://localhost:4200 y entra a **Deployments**.

Correr una vez a mano, sin esperar el intervalo:

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec orquestador prefect deployment run 'pipeline/news-dev'
```

## Pruebas

```bash
python -m pytest -q tests/flows
```

Usan un servidor temporal de Prefect y scrapers simulados, así que no necesitan red ni Docker.

## Estado

Hecho: flujos por fuente, flujo principal, programación, reintentos, gancho de fallo y parámetros por entorno. Probado con un servidor de Prefect real: la corrida de noticias guardó en un almacenamiento compatible con MinIO y, al forzar una falla, la tarea reintentó 3 veces y el gancho contó la falla.

**Pendiente:**

- **Validación, limpieza y sentimiento:** quedan `pendiente` hasta que lleguen P2.2, P2.3 y P2.4.
- **Corrida de 24 horas:** es el criterio de aceptación y falta hacerla.
- **Pushgateway:** lo agrega P3.1; hasta entonces las métricas solo quedan en el log.

**Decisiones a confirmar:**

- **Versión de Prefect:** el servidor pasó de 3.1.5 a 3.8.8, porque Prefect 3.1.5 no funciona con `pydantic==2.13.5`, que fija P1.2. Cliente y servidor deben tener la misma versión. Además se fija `fastapi==0.142.2`, porque con `fastapi` 0.162 Prefect 3.8.8 falla.
- **Búsqueda de videos una vez al día:** el scraper de YouTube busca videos en cada corrida, así que hoy busca 4 veces al día. Con los valores por defecto son unas 1.200 unidades de búsqueda al día, dentro de la cuota, pero la ruta de trabajo pide una sola búsqueda diaria. Hace falta que P1.4 separe la búsqueda de la bajada de comentarios.
- **Marca de agua de Google Play:** se guarda en un archivo local (`data/estado/`) y no en MinIO. Por eso el servicio tiene el volumen `orquestador_data`; si se borra el volumen, Google Play vuelve a empezar desde cero.
