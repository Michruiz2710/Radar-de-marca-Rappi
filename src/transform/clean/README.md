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

Al final imprime un resumen: leídos, descartados, duplicados, idiomas, bots (cantidad y porcentaje, total y por fuente), nuevos, actualizados y sin cambios.

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

Hecho: lectura de la capa raw, normalización, enmascarado de datos personales (también en la respuesta de Rappi), detección de idioma (español, portugués e inglés), duplicados con la versión más reciente, 5 reglas de bots, carga idempotente por entorno y carga histórica. Probado contra Postgres 16 con 11.540 registros simulados del tamaño de la primera corrida: 2 segundos, sin datos personales visibles y sin cambios al repetir la carga.

**Limitaciones conocidas:** ver la sección del mismo nombre en [`docs/contrato_clean.md`](../../../docs/contrato_clean.md).
