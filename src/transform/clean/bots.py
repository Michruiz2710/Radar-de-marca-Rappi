"""Reglas para marcar bots y spam.

Los bots NO se borran: se marcan con `es_bot = true` y `motivo_bot` dice por
qué. Así se puede auditar cada decisión y cambiar una regla sin perder datos.

Las reglas comparan los registros de una misma tanda de limpieza (una corrida
del orquestador, o toda la carga histórica). Las noticias nunca son bots.
"""

import re
from collections import defaultdict
from datetime import timedelta

# --- Umbrales (si se cambian, subir VERSION_LIMPIEZA en limpieza.py) ---
MAX_ENLACES = 1  # dos o más enlaces en un comentario
# "Mismo texto, varios autores" solo cuenta con textos largos: frases cortas y
# genéricas ("Pésimo servicio, el pedido llegó frío") las escribe mucha gente real.
MIN_LARGO_CAMPANA = 40  # letras y números, sin espacios ni signos
MIN_AUTORES_CAMPANA = 3
RAFAGA_COMENTARIOS = 5  # 5 comentarios o más del mismo autor...
RAFAGA_VENTANA = timedelta(minutes=10)  # ...en 10 minutos

# Frases típicas de spam. Se evitan palabras sueltas como "whatsapp", que también
# aparecen en quejas reales ("no responden por WhatsApp").
_RE_PROMOCIONAL = re.compile(
    r"gana(?:r)? dinero|ingresos? extra|dinero f[aá]cil|trabaja desde (?:tu )?casa"
    r"|visita mi canal|suscr[ií]bete a mi canal|mira mi canal|sorteo en mi perfil"
    r"|bit\.ly/|t\.me/|wa\.me/|tinyurl\.com/",
    re.IGNORECASE,
)

MOTIVOS = {
    "multiples_enlaces": "dos o más enlaces en el texto",
    "texto_repetido_autor": "el mismo autor publicó el mismo texto más de una vez",
    "campana_varios_autores": f"el mismo texto lo publicaron {MIN_AUTORES_CAMPANA} o más autores",
    "rafaga": f"{RAFAGA_COMENTARIOS} o más comentarios del mismo autor en {RAFAGA_VENTANA.seconds // 60} minutos",
    "promocional": "frase o enlace típico de spam",
}


def marcar_bots(filas: list[dict]) -> dict[str, list[str]]:
    """Devuelve {id_registro: [motivos]} para los registros marcados como bot.

    Cada fila necesita: id_registro, fuente, autor_hash, clave, n_urls,
    texto_limpio y fecha_publicacion. No modifica las filas.
    """
    motivos: dict[str, set[str]] = defaultdict(set)
    candidatas = [f for f in filas if f["fuente"] != "news"]

    for f in candidatas:
        if f["n_urls"] > MAX_ENLACES:
            motivos[f["id_registro"]].add("multiples_enlaces")
        if _RE_PROMOCIONAL.search(f["texto_limpio"]) or _RE_PROMOCIONAL.search(f.get("texto_original") or ""):
            motivos[f["id_registro"]].add("promocional")

    # Mismo autor, mismo texto
    por_autor_y_texto: dict[tuple[str, str], list[str]] = defaultdict(list)
    for f in candidatas:
        if f["autor_hash"] and f["clave"]:
            por_autor_y_texto[(f["autor_hash"], f["clave"])].append(f["id_registro"])
    for ids in por_autor_y_texto.values():
        if len(ids) > 1:
            for i in ids:
                motivos[i].add("texto_repetido_autor")

    # Mismo texto (largo), varios autores distintos: campaña coordinada
    por_texto: dict[str, list[dict]] = defaultdict(list)
    for f in candidatas:
        if len(f["clave"]) >= MIN_LARGO_CAMPANA:
            por_texto[f["clave"]].append(f)
    for grupo in por_texto.values():
        autores = {f["autor_hash"] for f in grupo if f["autor_hash"]}
        if len(autores) >= MIN_AUTORES_CAMPANA:
            for f in grupo:
                motivos[f["id_registro"]].add("campana_varios_autores")

    # Ráfaga: muchos comentarios del mismo autor en poco tiempo
    por_autor: dict[str, list[dict]] = defaultdict(list)
    for f in candidatas:
        if f["autor_hash"]:
            por_autor[f["autor_hash"]].append(f)
    for grupo in por_autor.values():
        if len(grupo) < RAFAGA_COMENTARIOS:
            continue
        grupo = sorted(grupo, key=lambda f: f["fecha_publicacion"])
        inicio = 0
        for fin in range(len(grupo)):
            while grupo[fin]["fecha_publicacion"] - grupo[inicio]["fecha_publicacion"] > RAFAGA_VENTANA:
                inicio += 1
            if fin - inicio + 1 >= RAFAGA_COMENTARIOS:
                for f in grupo[inicio : fin + 1]:
                    motivos[f["id_registro"]].add("rafaga")

    return {i: sorted(m) for i, m in motivos.items()}
