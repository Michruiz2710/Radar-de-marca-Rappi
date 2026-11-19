""" Dashboard de negocio de Rappi Pulse

    Lee únicamente el esquema analytics (tabla de dbt)
    Correr desde la carpeta dashboard/ (así Streamlit lee .streamlit/config.toml):
        PYTHONPATH=.. POSTGRES_HOST=localhost streamlit run app.py
"""

import pandas as pd
import streamlit as st
import altair as alt
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
colores_fuente = {"google_play": "#FBBC05", "youtube": "#FF0000", "news": "#174EA6"}

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

def sentimiento_diario(parametros: dict) -> pd.DataFrame:
    """% de menciones negativas por día y fuente (solo menciones analizadas)."""
    sql = f"""
        select
            fecha,
            fuente,
            avg((sentimiento = 'negativo')::int)::float as pct_negativo,
            count(*) as analizadas
        from {esquema}.fct_menciones
        where analizada and {filtro_sql}
        group by fecha, fuente
        order by fecha
    """
    datos = consultar(sql, parametros)
    datos["fuente_nombre"] = datos["fuente"].map(nombres_fuente)
    return datos


def noticias_por_dia(parametros: dict) -> pd.DataFrame:
    """Noticias sobre Rappi por día, para marcarlas encima de la curva."""
    sql = f"""
        select
            fecha,
            count(*) as noticias,
            left(min(texto_limpio), 140) as titular,
            min(medio) as medio
        from {esquema}.fct_menciones
        where fuente = 'news' and fecha between :desde and :hasta
        group by fecha
        order by fecha
    """
    return consultar(sql, parametros)

def grafico_sentimiento(datos: pd.DataFrame, noticias: pd.DataFrame) -> alt.LayerChart:
    """Líneas por fuente, umbrales de 30 % y 50 % y una regla por día con noticias."""
    dominio = [nombres_fuente[f] for f in colores_fuente]
    lineas = alt.Chart(datos).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%d %b")),
        y=alt.Y("pct_negativo:Q", title="% negativo", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("fuente_nombre:N", title="Fuente", scale=alt.Scale(domain=dominio, range=list(colores_fuente.values()))),
        strokeDash=alt.StrokeDash("fuente_nombre:N", scale=alt.Scale(domain=dominio, range=[[1, 0], [6, 4], [1, 0]]), legend=None),
        tooltip=[
            alt.Tooltip("fecha:T", title="Fecha", format="%d %b %Y"),
            alt.Tooltip("fuente_nombre:N", title="Fuente"),
            alt.Tooltip("pct_negativo:Q", title="% negativo", format=".0%"),
            alt.Tooltip("analizadas:Q", title="Menciones"),
        ],
    )
    umbrales = alt.Chart(pd.DataFrame({"umbral": [0.3, 0.5]})).mark_rule(
        strokeDash=[4, 4], color="#8F5F00"
    ).encode(y="umbral:Q")
    eventos = alt.Chart(noticias).mark_rule(strokeDash=[2, 3], color="#3A3D44").encode(
        x="fecha:T",
        tooltip=[
            alt.Tooltip("fecha:T", title="Fecha", format="%d %b %Y"),
            alt.Tooltip("noticias:Q", title="Noticias"),
            alt.Tooltip("titular:N", title="Titular"),
            alt.Tooltip("medio:N", title="Medio"),
        ],
    )
    return lineas + umbrales + eventos

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

tab_sentimiento, tab_quejas, tab_app = st.tabs(["Sentimiento y noticias", "Quejas", "App y respuesta"])

with tab_sentimiento:
    st.subheader("Sentimiento diario por fuente")
    st.caption("% de menciones negativas por día. Las líneas punteadas verticales son días con noticias sobre Rappi.")
    try:
        datos_sentimiento = sentimiento_diario(parametros)
        noticias = noticias_por_dia(parametros)
        if datos_sentimiento.empty:
            st.info("Sin menciones analizadas para graficar en este periodo.")
        else:
            st.altair_chart(grafico_sentimiento(datos_sentimiento, noticias))
        st.dataframe(noticias, hide_index=True)
    except Exception as error:
        st.error(f"No se pudo leer el sentimiento diario: {error}")

