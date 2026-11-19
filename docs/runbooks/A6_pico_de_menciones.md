# A6 · Menciones del día superan 2 veces el promedio de 7 días

**Prioridad:** P1 · **Condición:** los registros extraídos en el último día superan el doble del promedio diario de la última semana, durante 10 minutos. Solo se evalúa si hay al menos 7 días de historia; antes de eso no dispara.

## Qué significa

Hoy se extrajeron muchas más menciones de lo normal. Casi siempre es una noticia o un suceso (un problema masivo, una promoción, una crisis), pero también puede ser un **artefacto técnico**: la alerta cuenta lo que se guardó en la capa raw, no lo que se publicó ese día.

## Qué hacer

1. **Identifica la fuente y el día.** En Postgres (reemplaza `<POSTGRES_USER>` por el de tu `.env`):

   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec postgres psql -U <POSTGRES_USER> -d radar -c "select fecha_publicacion::date as dia, fuente, count(*) from clean.menciones where fecha_publicacion >= now() - interval '8 days' group by 1, 2 order by 1 desc, 2"
   ```

   Compara el día de hoy con los anteriores. Si la fuente no subió en `fecha_publicacion` pero sí en lo extraído, es un artefacto (paso 2).

2. **Descarta un artefacto técnico:**
   - **Marca de agua de Google Play reiniciada** (se borró el archivo o el volumen `google_play_estado`) o una corrida con `--full`: vuelve a bajar reseñas viejas y la cifra se infla.
   - **Primera corrida de una fuente**, por ejemplo YouTube al poner la clave: baja el historial de golpe.

3. **Si es real, mira qué pasó.** Para las noticias del día:

   ```sql
   select medio, left(texto_limpio, 160) from clean.menciones
   where fuente = 'news' and fecha_publicacion >= now() - interval '1 day' order by fecha_publicacion desc limit 15;
   ```

   Para el resto, mira los temas con la consulta del paso 2 de [A5](A5_sentimiento_negativo.md).

4. **Revisa los bots.** Un pico de spam también sube las cifras: mira el panel **Bots filtrados (24 h)**.

5. **Avisa al negocio** con la fuente, la cifra comparada con el promedio y la causa probable.

## Cómo saber que quedó resuelta

La alerta se resuelve cuando el volumen diario vuelve por debajo del doble del promedio. Si fue un artefacto técnico, corregirlo no baja la cifra de inmediato: esa ventana es de un día. En ese caso basta con dejar anotado lo que pasó.
