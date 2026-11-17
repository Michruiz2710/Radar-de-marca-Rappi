""" Dashboard de negocio de Rappi Pulse

    Lee únicamente el esquema analytics (tabla de dbt)
    Correr desde la raíz del repositorio:
        PYTHONPATH=.POSTGRES_HOST=localhost streamlit run dashboard/app.py
"""

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Engine, text

from src.common.db import crear_motor, esquema_analytics

load_dotenv()

esquema = esquema_analytics()

@st.cache_resource
def obtener_motor() -> Engine:
    """ Un solo motor para toda la app """
    return crear_motor()

@st.cache_data(ttl=600)
def consultar(sql: str) -> pd.DataFrame:
    """ Ejecuta una consulta y devuelve un DataFrame """
    with obtener_motor().connect() as conexion:
        return pd.read_sql(text(sql), conexion)

st.set_page_config(page_title="Rappi Pulse", layout="wide")
st.title("Rappi Pulse: radar de marca")

def resumen() -> pd.Series:
    """Menciones, % negativo y calificación promedio de toda la tabla."""
    sql = f"""
        select
            count(*) as menciones,
            avg((sentimiento = 'negativo')::int) filter (where analizada)::float as pct_negativo,
            avg(calificacion)::float as calificacion_promedio
        from {esquema}.fct_menciones
    """
    return consultar(sql).iloc[0]


def tema_mas_quejado() -> str | None:
    """Tema con más menciones negativas (sin contar las no analizadas)."""
    sql = f"""
        select tema
        from {esquema}.fct_menciones
        where sentimiento = 'negativo' and tema <> 'sin_analizar'
        group by tema
        order by count(*) desc
        limit 1
    """
    datos = consultar(sql)
    return None if datos.empty else datos["tema"].iloc[0]


def formatear(valor, formato: str) -> str:
    """Muestra 'Sin datos' cuando la consulta devuelve nulo."""
    return "Sin datos" if pd.isna(valor) else format(valor, formato)

st.subheader("Resumen")
try:
    datos = resumen()
    tema = tema_mas_quejado()
    col_menciones, col_negativo, col_calificacion, col_tema = st.columns(4)
    col_menciones.metric("Menciones", formatear(datos["menciones"], ","))
    col_negativo.metric("% negativo", formatear(datos["pct_negativo"], ".1%"))
    col_calificacion.metric("Calificación promedio", formatear(datos["calificacion_promedio"], ".2f"))
    col_tema.metric("Tema más quejado", tema or "Sin datos")
except Exception as error:
    st.error(f"No se pudo leer {esquema}.fct_menciones: {error}")

