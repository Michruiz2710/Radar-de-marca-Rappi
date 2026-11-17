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

def consultar(sql: str) -> pd.DataFrame:
    """ Ejecuta una consulta y devuelve un DataFrame """
    with obtener_motor().connect() as conexion:
        return pd.read_sql(text(sql), conexion)

st.set_page_config(page_title="Rappi Pulse", layout="wide")
st.title("Rappi Pulse: radar de marca")

try:
    conteo = consultar(f"select count(*) as total from {esquema}.fct_menciones")
    st.metric("Menciones", int(conteo["total"].iloc[0]))
except Exception as error:
    st.error(f"No se pudo leer {esquema}.fct_menciones: {error}")

