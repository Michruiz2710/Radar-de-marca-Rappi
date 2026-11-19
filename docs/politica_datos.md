# Política de datos personales (Habeas Data)

**Paquete:** P3.5 Gobierno, linaje y cierre · **Autora:** Michelle · **Coautora:** Katalina · **Revisor:** Gabriel

El proyecto recolecta opiniones públicas sobre Rappi: reseñas de Google Play, comentarios de YouTube y titulares de Google News. Aunque son públicas, una reseña o un comentario los escribe una persona, así que se tratan como datos personales bajo la Ley 1581 de 2012 de Colombia (Habeas Data) y según los términos de cada plataforma.

Esta política formaliza las reglas que el equipo acordó en la ruta de trabajo y dice dónde se cumple cada una en el código. Es un trabajo académico: no reemplaza una revisión legal.

## Responsables

| Rol | Quién |
| --- | --- |
| Responsable de esta política y del catálogo | Michelle (Observability y coordinación) |
| Responsable de la calidad y del contrato de datos | Katalina (Data Quality) |
| Responsable de credenciales y entornos | Gabriel (DevOps) |
| Dueño de cada conjunto de datos | Ver la columna "Dueño" del [catálogo](catalogo_datos.md) |

## Principios de la Ley 1581 y cómo los cumple el proyecto

| Principio (art. 4) | Cómo se cumple | Dónde |
| --- | --- | --- |
| **Finalidad** | Los datos se usan solo para el proyecto académico "Radar de Marca: Rappi" del curso Enfoque DataOps. No se publican fila por fila, no se venden y no se usan para contactar ni perfilar personas | Esta política, README |
| **Libertad** | Solo se recolectan opiniones que sus autores publicaron abiertamente. No se entra a cuentas, grupos privados ni al sitio de Rappi | Scrapers (P1.3, P1.4, P1.5) |
| **Veracidad o calidad** | Contrato de datos, validaciones con Great Expectations, versión más reciente de cada reseña, bots marcados y no mezclados con personas | `src/common/schema.py`, `quality/`, `src/transform/clean/` |
| **Transparencia** | El catálogo dice qué se guarda, dónde y hasta cuándo; cada resultado guarda la versión del código y del modelo que lo produjo | [`catalogo_datos.md`](catalogo_datos.md), [`linaje.md`](linaje.md) |
| **Acceso y circulación restringida** | Los datos fila por fila solo los ven los integrantes del equipo; el dashboard muestra agregados y ejemplos enmascarados | Niveles de sensibilidad del catálogo, P3.3 |
| **Seguridad** | Credenciales fuera de Git, autores seudonimizados con sal secreta, datos personales enmascarados en clean | `.env`, GitHub Environments, `src/common/privacy.py`, `src/transform/clean/texto.py` |
| **Confidencialidad** | Las claves y la sal se comparten solo por mensaje privado, nunca en el grupo, issues, Pull Requests ni en el repositorio | Reglas del equipo |

## Reglas

### 1. Minimización

Solo se guardan los campos del [contrato de datos](contrato_datos.md). El modelo `RegistroMencion` rechaza cualquier campo extra (`extra="forbid"`), así que un scraper no puede guardar por accidente un nombre de usuario, una foto de perfil o un enlace a un perfil. Las pruebas `test_campo_fuera_del_contrato_falla` y `test_subreddit_ya_no_es_un_campo` lo comprueban en cada Pull Request.

### 2. Seudonimización de autores

El nombre del autor nunca se guarda. En su lugar se guarda `autor_hash = SHA-256(sal + nombre normalizado)`:

- La sal (`HASH_SALT`) vive solo en el `.env` de cada integrante y en los GitHub Environments. Es la misma para todo el equipo, para que un autor tenga el mismo hash en cualquier máquina.
- Sin la sal no se puede adivinar el nombre probando nombres comunes.
- El código rechaza una sal vacía o la de ejemplo (`SalNoConfiguradaError`).
- El hash permite detectar bots (el mismo autor repitiendo texto) sin saber quién es.

### 3. Enmascarado en la capa clean

La limpieza reemplaza correos, enlaces, teléfonos colombianos y números de 7 o más dígitos por `[CORREO]`, `[URL]`, `[TELEFONO]` y `[NUMERO]`, también en la respuesta de Rappi. El texto original no pasa a la capa clean: queda solo en raw, que es de acceso restringido.

**Limitación:** los nombres propios escritos dentro del texto ("soy Ana Pérez") no se pueden detectar de forma confiable con reglas y no se enmascaran.

### 4. Acceso y credenciales

- MinIO, Postgres, la API de YouTube, el administrador de Grafana y la cuenta de correo que envía las alertas (`GRAFANA_SMTP_PASSWORD`, una contraseña de aplicación de Gmail) usan credenciales del `.env`, que está en `.gitignore`. En staging y prod vienen de los GitHub Environments.
- Cada entorno tiene su propio bucket y sus propios esquemas, así que una prueba nunca toca los datos de otro entorno.
- Las imágenes publicadas en GHCR contienen solo código, no datos.

### 5. Datos fuera de Git

La carpeta `data/` y los `.env` están en `.gitignore`. Excepciones permitidas:

- `quality/datos_prueba/`: datos sintéticos inventados para las pruebas, sin personas reales.
- `data/etiquetas/muestra_200.csv`: 200 reseñas reales usadas para evaluar el modelo. Ver el riesgo identificado en el catálogo: decisión pendiente antes de la entrega final.

### 6. Resultados agregados

El dashboard y la presentación muestran tendencias, conteos y porcentajes. Cuando muestran un ejemplo de texto, es el texto limpio (enmascarado), sin `autor_hash` ni `id_registro`. Nunca se señala ni se rankea a una persona.

El dashboard (P3.3) lo cumple así: lee solo `analytics.fct_menciones`, que ya excluye los bots; los ejemplos de quejas muestran fecha, fuente, estrellas y los primeros 200 caracteres del texto limpio, con una segunda pasada que tapa correos y teléfonos; y las tablas escapan el HTML, así que un comentario con código no se ejecuta en el navegador.

Las alertas por correo (P3.2) llevan solo métricas del pipeline (fallas, conteos, porcentajes), nunca textos ni autores.

### 7. Respeto a las plataformas

- **Google Play:** volumen moderado (máximo 500 reseñas por corrida) y solo reseñas nuevas gracias a la marca de agua.
- **YouTube:** API oficial, dentro de la cuota diaria y con un presupuesto de cuota por corrida.
- **Google News:** feed RSS público, identificándose como proyecto académico en el `User-Agent`.
- **Rappi:** no se hace scraping de su sitio ni de su app.

## Derechos de las personas

La ley da a cada persona derecho a conocer, actualizar, rectificar y pedir la supresión de sus datos (art. 8). Como el proyecto no guarda nombres, no se puede buscar a alguien por su nombre. Si una persona pide que se borre su opinión:

1. Se le pide el texto de su reseña o comentario, o el enlace.
2. Se busca la mención en `clean.menciones` por texto o por `id_original`.
3. Se borra de todas las capas: la fila de `clean.menciones`, la de `clean.sentimiento`, sus líneas en los archivos raw (única excepción a la regla de que raw no se modifica) y, si aparece, de la muestra etiquetada.
4. Como el scraper podría volver a traerla, se excluye su `id_registro` en la limpieza (hoy no hay solicitudes; la lista de exclusión se implementa si llega la primera) y se deja constancia en un issue sin datos personales.

## Retención y borrado

Todos los datos recolectados se borran al terminar el curso. Cada integrante, en su máquina:

```bash
# Apaga el entorno y borra los volúmenes: MinIO, Postgres, la marca de agua de Google Play,
# Prometheus, Pushgateway y Grafana
docker compose -f infra/docker-compose.yml --env-file .env --env-file config/dev.env down -v

# Borra los datos locales que quedan fuera de Docker (incluye los Data Docs)
rm -rf data/raw data/estado data/data_docs
```

Además, una sola vez:

- Gabriel borra los secretos de los GitHub Environments `staging` y `prod`.
- Quien creó la clave de la API de YouTube la revoca en Google Cloud.
- Quien administra `radar.rappi.alertas@gmail.com` revoca la contraseña de aplicación de Grafana y cierra la cuenta.
- Se elimina la sal (`HASH_SALT`) de todos los `.env`: sin ella, los hashes que hayan quedado en cualquier copia no se pueden volver a calcular.
- Se aplica la decisión sobre la muestra etiquetada y el repositorio.

Staging y prod no requieren borrado: corren en runners temporales de GitHub Actions que terminan con `docker compose down -v`.

## Incidentes

| Incidente | Qué hacer |
| --- | --- |
| Se subió un `.env`, una clave o la sal a Git o a un chat | Avisar al grupo por privado, cambiar la clave filtrada de inmediato (la sal también), borrar el mensaje o el commit y revisar que no quede en el historial |
| Un dato personal aparece sin enmascarar en clean o en el dashboard | Abrir un issue con la etiqueta `bug` (sin copiar el dato), corregir la regla de enmascarado, subir `VERSION_LIMPIEZA` y volver a correr la carga histórica |
| Un scraper empieza a guardar un campo nuevo | El contrato lo rechaza. Si se necesita, se agrega con un cambio de contrato revisado por Katalina |

## Ética del análisis

- **Sesgo del modelo:** `pysentimiento` puede fallar con jerga colombiana o sarcasmo. Su exactitud se midió contra 200 reseñas etiquetadas (87 % en sentimiento, F1 45 % en la clase neutra) y está documentada en [`evaluacion_nlp.md`](evaluacion_nlp.md).
- **Transparencia:** cada resultado guarda la versión del modelo y del código, para poder explicar por qué un texto quedó como negativo.
- **Bots:** se marcan, no se borran, y cada marca dice el motivo. Así se puede auditar y corregir una regla sin perder datos.
- **Responsabilidad:** cada conjunto del catálogo tiene un dueño que responde por él.
