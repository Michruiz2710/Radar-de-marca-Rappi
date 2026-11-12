""" Reglas de calidad que salen del contrato de datos

    Se definen columnas existentes, obligatorias con valores permitidos. Se utilizan
    las suites de Great Expectations para formar reglas, por lo que si cambia el contrato, cambia 
    el archivo.
"""

from src.common.schema import VERSION_CONTRATO, Fuente, RegistroMencion

# Si falla el flujo de detiene
critica = "critical"
advertencia = "warning"

# Definición de todas las columnas que puede tener un registro de la capa raw:
# campos del contrato más los calculados. Son leídos del modelo para evitar
# la desincronización con el código
campos_contrato = sorted(set(RegistroMencion.model_fields) | set(RegistroMencion.model_computed_fields))

obligatorios = ["id_registro", "fuente", "id_original", "texto", "fecha_publicacion", "idioma", "pais", "fecha_extraccion", "run_id", "version_scraper", "version_contrato",]

columnas_retiradas = ["subreddit"]
columnas_fecha = ["fecha_publicacion", "fecha_extraccion", "fecha_respuesta", "fecha_edicion"]

# Campos prohibidos fuera de su fuente
solo_google_play = ["calificacion", "version_app", "respuesta_marca", "fecha_respuesta"]
solo_news = ["medio"]

fuentes_permitidas = [fuente.value for fuente in Fuente]
patron_autor_hash = r"^[0-9a-f]{64}$"
margen_reloj_minutos = 10

# Valores esperados
idioma_esperado = "es"
pais_esperado = "co"
version_contrato_actual = VERSION_CONTRATO