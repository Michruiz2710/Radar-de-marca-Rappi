# Limpieza y filtrado de bots

Lee la capa raw (MinIO), limpia el texto, quita duplicados, enmascara datos personales, detecta el idioma, marca bots y carga la tabla `menciones` de la capa clean en Postgres. El detalle de la tabla está en [`docs/contrato_clean.md`](../../../docs/contrato_clean.md).

| Paquete | Autor | Coautor | Revisor | Semana |
| --- | --- | --- | --- | --- |
| P2.3 Limpieza y filtrado de bots | Michelle | Sara | Jonathan | Semana 2 |

## Qué hay aquí

| Archivo | Qué hace |
| --- | --- |
| `limpieza.py` | `limpiar(rutas)`: la etapa que llama el orquestador. `transformar()`: los pasos de limpieza, sin leer ni escribir. Comando para la carga histórica |
| `texto.py` | Normalizar, enmascarar datos personales, detectar idioma |
| `bots.py` | Reglas de bots y spam |
| `tabla.py` | Definición de la tabla y carga sin duplicados (insertar o actualizar) |

## Cómo se usa

**En el pipeline:** el orquestador (P2.1) llama a `src.transform.clean.limpieza:limpiar` después de la validación cruda, con las rutas de la corrida. No hay que hacer nada.

**Carga histórica** (limpiar todo lo que ya está en MinIO), con el entorno levantado:

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec orquestador python -m src.transform.clean.limpieza
docker compose -f infra/docker-compose.yml --env-file .env exec orquestador python -m src.transform.clean.limpieza --fuente youtube
```

Al final imprime un resumen: leídos, descartados, duplicados, idiomas, bots (cantidad y porcentaje, total y por fuente), bots anteriores marcados por esta tanda, nuevos, actualizados y sin cambios.

**Ver el resultado** en Postgres:

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec postgres psql -U <POSTGRES_USER> -d radar \
  -c "select fuente, count(*), sum(es_bot::int) as bots from clean.menciones group by fuente"
```

## Pruebas

```bash
python -m pytest -q tests/clean tests/test_storage_db.py
```

Usan SQLite en memoria en lugar de Postgres, así corren en el CI sin base de datos ni internet.

## Estado

Hecho: lectura de la capa raw, normalización, enmascarado de datos personales (también en la respuesta de Rappi), detección de idioma (español, portugués e inglés), duplicados con la versión más reciente, 5 reglas de bots (también entre corridas, desde la versión 1.3.0), carga idempotente por entorno y carga histórica. Probado contra Postgres 16 con 11.540 registros simulados del tamaño de la primera corrida: 2 segundos, sin datos personales visibles y sin cambios al repetir la carga.

### Resultados con datos reales

Carga histórica de la capa raw en el entorno dev (primeras corridas de los tres scrapers, noviembre de 2026):

| Métrica | Valor |
| --- | --- |
| Registros leídos de raw | 11.540 |
| Duplicados eliminados (versiones repetidas de la misma mención) | 450 |
| Filas descartadas | 0 |
| **Filas en `clean.menciones`** | **11.090** (507 Google Play, 10.520 YouTube, 63 noticias) |
| Idioma | 11.039 español, 25 portugués, 26 inglés |
| Bots marcados | 163 (1,47 %), todos de YouTube (1,55 % de esa fuente) |
| Datos personales visibles después del enmascarado | 0 |

**Cómo se llegó a esos bots.** Con la versión 1.0.0 las reglas marcaban 616 bots, pero muchos eran personas: 530 por conversar en un mismo video y 33 repartidores hablando de sus ganancias. La versión 1.1.0 ajustó `rafaga` y `promocional` y los bots bajaron a 163. El detalle está en el historial de `docs/contrato_clean.md`.

**Versión 1.3.0 (bots entre corridas, #29).** Probada en Docker con los mismos datos: las 11.090 filas pasaron a 1.3.0, los bots siguieron en 163 y una segunda carga dio 0 actualizadas y 0 bots anteriores (idempotente). La carga histórica tardó unos 43 s, porque ahora también consulta la tabla.

**Limitaciones conocidas:** ver la sección del mismo nombre en [`docs/contrato_clean.md`](../../../docs/contrato_clean.md).
