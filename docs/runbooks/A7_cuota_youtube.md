# A7 · La cuota de YouTube supera el 80 %

**Prioridad:** P1 · **Condición:** `cuota_youtube_usada > 8000` de las 10.000 unidades diarias de la API.

## Qué significa

Hoy se usaron más de 8.000 unidades de la API de YouTube Data v3. La cuota se reinicia a la medianoche de la hora del Pacífico. Si llega a 10.000, la API responde 403 (`quotaExceeded`) y YouTube deja de traer datos hasta el reinicio.

El scraper se detiene solo al llegar a `YT_QUOTA_BUDGET` (8.000 por defecto) y guarda lo que alcanzó, así que normalmente esta alerta avisa, pero no se pierde nada: mañana retoma desde donde quedó.

## Cuánto cuesta cada cosa

| Operación | Costo |
| --- | --- |
| Una búsqueda de videos (`YT_MAX_SEARCHES_PER_DAY` por día, 3 por defecto) | 100 unidades |
| Una página de 100 comentarios | 1 unidad |

## Qué hacer

1. **Mira cuánto se usó y cuándo.** En el dashboard, el panel **Cuota de YouTube usada hoy**.

2. **Averigua quién la gastó.** La clave de la API la usan varios integrantes del grupo: las corridas locales de los demás **también gastan la misma cuota**. Pregunta en el canal del grupo si alguien está corriendo el scraper de YouTube en su computador.

3. **Revisa cuántas búsquedas hace el orquestador.** El flujo de YouTube corre cada 6 horas, y hoy cada corrida busca videos otra vez (unas 4 veces al día, ver `flows/README.md`). Con los valores por defecto son unas 1.200 unidades al día solo en búsquedas.

4. **Reduce el gasto** si hace falta. En `.env`:
   - `YT_MAX_SEARCHES_PER_DAY` más bajo (cada una cuesta 100).
   - `YT_MAX_COMMENTS_PER_VIDEO` más bajo.

   Aplica el cambio con:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env up -d orquestador
   ```

5. **Si hay que parar YouTube por hoy,** en Prefect (http://localhost:4200) → **Deployments** → `youtube-<entorno>` → pausa el horario. Acuérdate de reactivarlo mañana.

## Cómo saber que quedó resuelta

La alerta se resuelve sola con el reinicio de la cuota (medianoche del Pacífico: las 3 a. m. en Colombia en invierno de EE. UU., las 2 a. m. en verano). Si pasó el reinicio y el panel sigue arriba de 8.000, revisa el paso 3: el flujo está gastando más de lo previsto.

**Si ya se agotó la cuota,** el panel de errores HTTP mostrará 403 de YouTube y A1 puede dispararse porque la corrida de esa fuente falla. No hay nada que hacer hasta el reinicio, salvo pausar el despliegue para no acumular fallas.
