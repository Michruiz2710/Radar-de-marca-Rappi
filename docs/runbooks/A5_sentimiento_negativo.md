# A5 · Sentimiento negativo de 24 h supera el 60 %

**Prioridad:** P1 · **Condición:** `sentimiento_negativo_24h_ratio > 0.6` durante 10 minutos, por fuente (la etiqueta `fuente` dice cuál).

## Qué significa

Más del 60 % de las menciones publicadas en las últimas 24 h, sin contar bots, salieron negativas en esa fuente. El sistema funciona; lo que hay que revisar es **qué está pasando con la marca**. Es un aviso para el negocio, no una falla técnica.

## Qué hacer

Todas las consultas se corren en Postgres. Reemplaza `<POSTGRES_USER>` por el de tu `.env` y `clean` por el valor de `PG_SCHEMA_CLEAN` si usas otro entorno:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env exec postgres psql -U <POSTGRES_USER> -d radar
```

1. **Comprueba que no sea ruido por pocos datos.** Con 5 menciones, 3 negativas ya son 60 %:

   ```sql
   select m.fuente, count(*) as menciones, count(*) filter (where s.sentimiento = 'negativo') as negativas
   from clean.menciones m join clean.sentimiento s using (id_registro)
   where m.fecha_publicacion >= now() - interval '24 hours' and not m.es_bot
   group by m.fuente;
   ```

2. **Encuentra el tema que más creció** comparando las últimas 24 h con las 24 h anteriores:

   ```sql
   select s.tema,
          count(*) filter (where m.fecha_publicacion >= now() - interval '24 hours') as ultimas_24h,
          count(*) filter (where m.fecha_publicacion <  now() - interval '24 hours') as dia_anterior
   from clean.sentimiento s join clean.menciones m using (id_registro)
   where s.sentimiento = 'negativo' and not m.es_bot and m.fecha_publicacion >= now() - interval '48 hours'
   group by s.tema order by ultimas_24h desc;
   ```

3. **Lee algunos ejemplos** del tema que subió (el texto ya viene sin datos personales; no consultes ni compartas autores):

   ```sql
   select fuente, calificacion, left(texto_limpio, 200)
   from clean.menciones m join clean.sentimiento s using (id_registro)
   where s.sentimiento = 'negativo' and s.tema = '<tema>' and not m.es_bot
     and m.fecha_publicacion >= now() - interval '24 hours'
   order by m.fecha_publicacion desc limit 10;
   ```

4. **Descarta causas técnicas:**
   - ¿Muchos textos casi iguales? Puede ser una campaña o bots que no se filtraron: mira el panel **Bots filtrados** y `motivo_bot` en `clean.menciones`.
   - ¿El cambio coincide con otra `version_modelo` en `clean.sentimiento`? Un modelo nuevo puede mover las proporciones.

5. **Avisa al negocio** (Katalina y quien lleve el dashboard de negocio) con: la fuente, el porcentaje, el número de menciones, el tema que más creció y dos o tres ejemplos.

## Cómo saber que quedó resuelta

El ratio baja de 0,6 (panel **Sentimiento negativo (24 h)**) y llega el correo `[RESOLVED]`. Si el ratio sigue alto pero ya se avisó, no hay nada técnico que arreglar: la alerta solo se repite cada 12 horas.
