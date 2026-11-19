""" Dashboard de negocio de Rappi Pulse

    Lee únicamente el esquema analytics (tabla de dbt)
    Correr desde la carpeta dashboard/ (así Streamlit lee .streamlit/config.toml):
        PYTHONPATH=.. POSTGRES_HOST=localhost streamlit run app.py
"""

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Engine, text

from src.common.db import crear_motor, esquema_analytics

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

load_dotenv()

esquema = esquema_analytics()

zona_colombia = ZoneInfo("America/Bogota")
nombres_fuente = {"google_play": "Google Play", "youtube": "YouTube", "news": "Noticias"}
filtro_sql = "fecha between :desde and :hasta and fuente = any(:fuentes)"
color_marca = "#FF4940"

@st.cache_resource
def obtener_motor() -> Engine:
    """ Un solo motor para toda la app """
    return crear_motor()

@st.cache_data(ttl=600)
def consultar(sql: str, parametros: dict | None = None) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame."""
    with obtener_motor().connect() as conexion:
        return pd.read_sql(text(sql), conexion, params=parametros)

def resumen(parametros: dict) -> pd.Series:
    """Menciones, % negativo y calificación promedio con los filtros elegidos."""
    sql = f"""
        select
            count(*) as menciones,
            avg((sentimiento = 'negativo')::int) filter (where analizada)::float as pct_negativo,
            avg(calificacion)::float as calificacion_promedio
        from {esquema}.fct_menciones
        where {filtro_sql}
    """
    return consultar(sql, parametros).iloc[0]


def tema_mas_quejado(parametros: dict) -> str | None:
    """Tema con más menciones negativas (sin contar las no analizadas)."""
    sql = f"""
        select tema
        from {esquema}.fct_menciones
        where sentimiento = 'negativo'
            and tema <> 'sin_analizar'
            and {filtro_sql}
        group by tema
        order by count(*) desc
        limit 1
    """
    datos = consultar(sql, parametros)
    return None if datos.empty else datos["tema"].iloc[0]

def filtros() -> dict:
    """Fila de filtros arriba de la página. Devuelve los parámetros para el SQL."""
    hoy = datetime.now(zona_colombia).date()
    col_fechas, col_fuentes = st.columns([1, 2])
    rango = col_fechas.date_input(
        "Rango de fechas (hora de Colombia)",
        value=(hoy - timedelta(days=13), hoy),
        max_value=hoy,
        format="DD/MM/YYYY",
    )
    fuentes = col_fuentes.pills(
        "Fuente",
        options=list(nombres_fuente),
        format_func=nombres_fuente.get,
        selection_mode="multi",
        default=list(nombres_fuente),
    )
    if len(rango) != 2:
        st.info("Elige la fecha final del rango.")
        st.stop()
    if not fuentes:
        st.info("Elige al menos una fuente.")
        st.stop()
    return {"desde": rango[0], "hasta": rango[1], "fuentes": list(fuentes)}

def formatear(valor, formato: str) -> str:
    """Muestra 'Sin datos' cuando la consulta devuelve nulo."""
    return "Sin datos" if pd.isna(valor) else format(valor, formato)

st.set_page_config(page_title="Rappi Pulse", layout="wide")
parametros = filtros()
st.title("Rappi Pulse: radar de marca")
st.caption("Qué se dice de Rappi Colombia en Google Play, YouTube y noticias")

try:
    datos = resumen(parametros)
    tema = tema_mas_quejado(parametros)
    col_menciones, col_negativo, col_calificacion, col_tema = st.columns(4)
    col_menciones.metric("Menciones", formatear(datos["menciones"], ","))
    col_negativo.metric("% negativo", formatear(datos["pct_negativo"], ".1%"))
    col_calificacion.metric("Calificación promedio", formatear(datos["calificacion_promedio"], ".2f"))
    col_tema.metric("Tema más quejado", tema or "Sin datos")
except Exception as error:
    st.error(f"No se pudo leer {esquema}.fct_menciones: {error}")

