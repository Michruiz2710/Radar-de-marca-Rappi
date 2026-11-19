""" Dashboard de negocio de Rappi Pulse

    Lee únicamente el esquema analytics (tabla de dbt)
    Correr desde la carpeta dashboard/ (así Streamlit lee .streamlit/config.toml):
        PYTHONPATH=.. POSTGRES_HOST=localhost streamlit run app.py
"""

import pandas as pd
import streamlit as st
import altair as alt
import re
from dotenv import load_dotenv
from sqlalchemy import Engine, text
from pathlib import Path

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
color_bien = "#1E7B34"
color_atencion = "#8F5F00"
color_alerta = "#B42318"
color_neutro = "#9FA3AB"
muestra_minima = 30
patron_correo = re.compile(r"\S+@\S+")
patron_telefono = re.compile(r"\+?\d[\d\s-]{6,}\d")
reglas_estado = {
    "negativo": "menos de 30 % · 30 a 50 % · más de 50 %",
    "calificacion": "4,0 o más · 3,0 a 3,9 · menos de 3,0",
}
etiquetas_estado = {"Bien": ":green[● Bien]", "Atención": ":orange[■ Atención]", "Alerta": ":red[▲ Alerta]"}


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
            count(*) as menciones, count(calificacion) as resenas,
            avg((sentimiento = 'negativo')::int) filter (where analizada)::float as pct_negativo,
            avg(calificacion)::float as calificacion_promedio
        from {esquema}.fct_menciones
        where {filtro_sql}
    """
    return consultar(sql, parametros).iloc[0]

def filtros() -> dict:
    """Fila de filtros arriba de la página. Devuelve los parámetros para el SQL."""
    hoy = datetime.now(zona_colombia).date()
    with st.container(key="filtros"):
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
    lineas = alt.Chart(datos).mark_line(point=True, strokeWidth=3.5).encode(
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

def calificacion_por_version(parametros: dict) -> pd.DataFrame:
    """Calificación promedio de Google Play en las últimas 5 versiones (mayor.menor)."""
    sql = f"""
        select
            version_app_corta as version,
            avg(calificacion)::float as calificacion_promedio,
            count(*) as resenas
        from {esquema}.fct_menciones
        where fuente = 'google_play'
            and calificacion is not null
            and version_app_corta is not null
            and fecha between :desde and :hasta
        group by version_app_corta
        order by string_to_array(version_app_corta, '.')::int[] desc
        limit 5
    """
    datos = consultar(sql, parametros).iloc[::-1]
    datos["estado"] = [
        estado_calificacion(promedio, resenas)
        for promedio, resenas in zip(datos["calificacion_promedio"], datos["resenas"])
    ]
    return datos


def estado_calificacion(promedio: float, resenas: int) -> str:
    """Semáforo de la calificación; con poca muestra no se juzga."""
    if resenas < muestra_minima:
        return "Poca muestra"
    if promedio >= 4:
        return "Bien"
    if promedio >= 3:
        return "Atención"
    return "Alerta"


def respuesta_a_negativas(parametros: dict) -> pd.Series:
    """Reseñas de 1 o 2 estrellas: % respondidas, mediana de horas y tramos."""
    sql = f"""
        select
            count(*) as negativas,
            avg(tiene_respuesta::int)::float as pct_respondidas,
            percentile_cont(0.5) within group (order by horas_hasta_respuesta)::float as mediana_horas,
            count(*) filter (where horas_hasta_respuesta < 24) as menos_24,
            count(*) filter (where horas_hasta_respuesta between 24 and 72) as entre_24_72,
            count(*) filter (where horas_hasta_respuesta > 72) as mas_72
        from {esquema}.fct_menciones
        where fuente = 'google_play'
            and calificacion <= 2
            and fecha between :desde and :hasta
    """
    return consultar(sql, parametros).iloc[0]

def grafico_versiones(datos: pd.DataFrame) -> alt.LayerChart:
    """Barras por versión coloreadas por semáforo, con reglas en 3 y 4 estrellas."""
    barras = alt.Chart(datos).mark_bar().encode(
        x=alt.X("version:N", title="Versión", sort=None),
        y=alt.Y("calificacion_promedio:Q", title="Calificación promedio", scale=alt.Scale(domain=[1, 5])),
        color=alt.Color(
            "estado:N",
            title="Estado",
            scale=alt.Scale(
                domain=["Bien", "Atención", "Alerta", "Poca muestra"],
                range=[color_bien, color_atencion, color_alerta, color_neutro],
            ),
        ),
        tooltip=[
            alt.Tooltip("version:N", title="Versión"),
            alt.Tooltip("calificacion_promedio:Q", title="Promedio", format=".2f"),
            alt.Tooltip("resenas:Q", title="Reseñas"),
            alt.Tooltip("estado:N", title="Estado"),
        ],
    )
    reglas = alt.Chart(pd.DataFrame({"umbral": [3, 4]})).mark_rule(
        strokeDash=[4, 4], color="#5C6068"
    ).encode(y="umbral:Q")
    return barras + reglas

def ultima_semana(parametros: dict) -> dict:
    """Los últimos 7 días del rango elegido (o menos si el rango es más corto)."""
    desde = max(parametros["desde"], parametros["hasta"] - timedelta(days=6))
    return {**parametros, "desde": desde}


def quejas_por_tema(parametros: dict) -> pd.DataFrame:
    """Menciones negativas por tema y su % sobre el total de negativas."""
    sql = f"""
        select tema, count(*) as negativas
        from {esquema}.fct_menciones
        where sentimiento = 'negativo'
            and tema <> 'sin_analizar'
            and {filtro_sql}
        group by tema
        order by negativas desc
    """
    datos = consultar(sql, parametros)
    datos["pct"] = datos["negativas"] / datos["negativas"].sum()
    datos["principal"] = ["sí"] + ["no"] * (len(datos) - 1) if len(datos) else []
    return datos


def anonimizar(texto: str) -> str:
    """Tapa correos y teléfonos y deja el texto en una sola línea."""
    texto = patron_correo.sub("[correo]", texto)
    texto = patron_telefono.sub("[teléfono]", texto)
    return " ".join(texto.split())


def ejemplos_quejas(parametros: dict, por_tema: int = 3) -> pd.DataFrame:
    """Hasta 3 menciones negativas por tema, las de más likes primero."""
    sql = f"""
        select tema, fuente, fecha, calificacion, texto
        from (
            select
                tema,
                fuente,
                fecha,
                calificacion,
                left(texto_limpio, 200) as texto,
                row_number() over (partition by tema order by likes desc nulls last, fecha desc) as orden
            from {esquema}.fct_menciones
            where sentimiento = 'negativo'
                and tema <> 'sin_analizar'
                and {filtro_sql}
        ) as negativas
        where orden <= :por_tema
    """
    datos = consultar(sql, {**parametros, "por_tema": por_tema})
    datos["texto"] = datos["texto"].map(anonimizar)
    return datos


def grafico_quejas(datos: pd.DataFrame) -> alt.LayerChart:
    """Barras horizontales de mayor a menor; la queja principal más intensa."""
    base = alt.Chart(datos).encode(
        y=alt.Y("tema:N", sort="-x", title=None),
        x=alt.X("pct:Q", title="% de las quejas", axis=alt.Axis(format="%")),
    )
    barras = base.mark_bar(color=color_marca).encode(
        opacity=alt.Opacity("principal:N", scale=alt.Scale(domain=["sí", "no"], range=[1, 0.75]), legend=None),
        tooltip=[
            alt.Tooltip("tema:N", title="Tema"),
            alt.Tooltip("negativas:Q", title="Menciones negativas"),
            alt.Tooltip("pct:Q", title="% de las quejas", format=".0%"),
        ],
    )
    etiquetas = base.mark_text(align="left", dx=4, fontWeight="bold").encode(
        text=alt.Text("pct:Q", format=".0%")
    )
    return barras + etiquetas

def encabezado(parametros: dict) -> None:
    """Franja de marca con el título, el subtítulo y el rango elegido."""
    rango = f"{parametros['desde']:%d/%m/%Y} – {parametros['hasta']:%d/%m/%Y}"
    st.html(f"""
        <div style="background: {color_marca}; color: #FFFFFF; border-radius: 12px;
                    padding: 28px 36px; display: flex; flex-wrap: wrap;
                    align-items: flex-end; justify-content: space-between; gap: 12px">
            <div>
                <h1 style="margin: 0; font-size: 34px; line-height: 1.1; font-weight: 700; color: #FFFFFF">
                    Rappi Pulse: radar de marca
                </h1>
                <div style="font-size: 19px; font-weight: 700">
                    Qué se dice de Rappi Colombia en Google Play, YouTube y noticias
                </div>
            </div>
            <div style="font-size: 19px; font-weight: 700">{rango}</div>
        </div>
    """)

def periodo_anterior(parametros: dict) -> dict:
    """Mismo número de días, justo antes del rango elegido."""
    dias = (parametros["hasta"] - parametros["desde"]).days + 1
    return {
        **parametros,
        "desde": parametros["desde"] - timedelta(days=dias),
        "hasta": parametros["desde"] - timedelta(days=1),
    }


def estado_negativo(pct: float) -> str | None:
    """Semáforo del % negativo."""
    if pd.isna(pct):
        return None
    if pct < 0.3:
        return "Bien"
    if pct <= 0.5:
        return "Atención"
    return "Alerta"


def diferencia(actual: float, anterior: float, formato: str, unidad: str = "") -> str | None:
    """Cambio absoluto, ej. '+6.0 pp' o '-0.20'."""
    if pd.isna(actual) or pd.isna(anterior):
        return None
    return f"{actual - anterior:{formato}}{unidad}"


def fuentes_sin_datos(parametros: dict) -> list[str]:
    """Fuentes elegidas en el filtro que no tienen menciones en el rango."""
    sql = f"""
        select distinct fuente
        from {esquema}.fct_menciones
        where {filtro_sql}
    """
    con_datos = set(consultar(sql, parametros)["fuente"])
    return [nombres_fuente[f] for f in parametros["fuentes"] if f not in con_datos]


def mostrar_veredicto(actual: pd.Series, anterior: pd.Series, tema: pd.Series | None) -> None:
    """Una frase arriba de las tarjetas: ¿la conversación va bien o mal?"""
    estado = estado_negativo(actual["pct_negativo"])
    if estado is None:
        st.info("No hay menciones analizadas en este rango. Prueba ampliar las fechas.")
        return
    cambio = actual["pct_negativo"] - anterior["pct_negativo"]
    if pd.isna(cambio) or abs(cambio) < 0.05:
        tendencia, detalle = "se mantuvo estable", ""
    else:
        tendencia = "empeoró" if cambio > 0 else "mejoró"
        detalle = f" ({cambio * 100:+.0f} pp)"
    texto = (
        f"**{estado}: la conversación {tendencia} frente al periodo anterior.** "
        f"El {actual['pct_negativo']:.0%} de las menciones son negativas{detalle}."
    )
    if tema is not None:
        texto += f" La queja principal es **{tema['tema']}**."
    {"Bien": st.success, "Atención": st.warning, "Alerta": st.error}[estado](texto)


def mostrar_resumen(parametros: dict) -> None:
    """Aviso de fuentes vacías, veredicto y las 4 tarjetas con delta y semáforo."""
    actual = resumen(parametros)
    anterior = resumen(periodo_anterior(parametros))
    quejas = quejas_por_tema(parametros)
    tema = None if quejas.empty else quejas.iloc[0]

    vacias = fuentes_sin_datos(parametros)
    if vacias and len(vacias) < len(parametros["fuentes"]):
        st.warning(f"{', '.join(vacias)} no tiene menciones en este rango. Los totales solo incluyen las demás fuentes.")
    mostrar_veredicto(actual, anterior, tema)

    col_menciones, col_negativo, col_calificacion, col_tema = st.columns(4)
    with col_menciones:
        st.metric(
            "Menciones totales",
            f"{int(actual['menciones']):,}".replace(",", "."),
            border=True,
        )
        st.caption("Volumen: no es bueno ni malo")
    with col_negativo:
        st.metric(
            "% menciones negativas",
            formatear(actual["pct_negativo"], ".0%"),
            delta=diferencia(actual["pct_negativo"] * 100, anterior["pct_negativo"] * 100, "+.1f", " pp"),
            delta_color="inverse",
            border=True,
        )
        estado = estado_negativo(actual["pct_negativo"])
        st.caption(f"{etiquetas_estado[estado]} · {reglas_estado['negativo']}" if estado else "Sin datos · sin semáforo")
    with col_calificacion:
        if "google_play" not in parametros["fuentes"]:
            st.metric("Calificación promedio · Google Play", "No aplica", border=True)
            st.caption("Agrega Google Play al filtro para verla")
        else:
            promedio = actual["calificacion_promedio"]
            st.metric(
                "Calificación promedio · Google Play",
                "—" if pd.isna(promedio) else f"{promedio:.1f} / 5 ★",
                delta=diferencia(promedio, anterior["calificacion_promedio"], "+.2f"),
                border=True,
            )
            estado = None if pd.isna(promedio) else estado_calificacion(promedio, actual["resenas"])
            if estado in etiquetas_estado:
                st.caption(f"{etiquetas_estado[estado]} · {reglas_estado['calificacion']}")
            else:
                st.caption("Poca muestra · no concluyente" if estado else "Sin reseñas en el rango")
    with col_tema:
        st.metric("Tema más quejado", "—" if tema is None else tema["tema"], border=True)
        st.caption("Sin quejas registradas" if tema is None else f"{tema['pct']:.0%} de las quejas · detalle en la pestaña Quejas")

st.set_page_config(page_title="Rappi Pulse", layout="wide")
st.html(Path(__file__).parent / "estilos.css")
parametros = filtros()
encabezado(parametros)

try:
    mostrar_resumen(parametros)
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

with tab_app:
    if "google_play" not in parametros["fuentes"]:
        st.info("Esta pestaña usa solo Google Play. Agrégalo en el filtro de fuentes para verla.")
    else:
        col_versiones, col_respuesta = st.columns([3, 2])
        with col_versiones:
            st.subheader("Calificación por versión de la app")
            st.caption(f"Últimas 5 versiones. En gris: menos de {muestra_minima} reseñas, no concluyente.")
            try:
                versiones = calificacion_por_version(parametros)
                if versiones.empty:
                    st.info("Sin reseñas con versión en este periodo.")
                else:
                    st.altair_chart(grafico_versiones(versiones))
            except Exception as error:
                st.error(f"No se pudo leer la calificación por versión: {error}")
        with col_respuesta:
            st.subheader("Respuesta a reseñas negativas")
            st.caption("Respuestas de Rappi en Google Play a reseñas de 1 o 2 estrellas.")
            try:
                respuesta = respuesta_a_negativas(parametros)
                col_mediana, col_pct = st.columns(2)
                col_mediana.metric("Mediana de respuesta", formatear(respuesta["mediana_horas"], ".0f") + " h" if pd.notna(respuesta["mediana_horas"]) else "Sin datos")
                col_pct.metric("% negativas respondidas", formatear(respuesta["pct_respondidas"], ".0%"))
                tramos = pd.DataFrame({
                    "tramo": ["Menos de 24 h", "24 a 72 h", "Más de 72 h"],
                    "resenas": [respuesta["menos_24"], respuesta["entre_24_72"], respuesta["mas_72"]],
                })
                if tramos["resenas"].sum() > 0:
                    st.bar_chart(tramos, x="tramo", y="resenas", horizontal=True, x_label="Reseñas", y_label="")
            except Exception as error:
                st.error(f"No se pudo leer la respuesta a negativas: {error}")

with tab_quejas:
    semana = ultima_semana(parametros)
    st.subheader("Top de quejas por tema")
    st.caption(f"Del {semana['desde']:%d/%m} al {semana['hasta']:%d/%m}: últimos 7 días del rango. Solo menciones negativas.")
    try:
        quejas = quejas_por_tema(semana)
        if quejas.empty:
            st.info("No hay quejas en los últimos 7 días del rango.")
        else:
            ejemplos = ejemplos_quejas(semana)
            col_grafico, col_ejemplos = st.columns([3, 2])
            col_grafico.altair_chart(grafico_quejas(quejas))
            with col_ejemplos:
                for posicion, tema in enumerate(quejas["tema"].head(5)):
                    with st.expander(f"{tema} · ejemplos", expanded=posicion == 0):
                        for fila in ejemplos[ejemplos["tema"] == tema].itertuples():
                            estrellas = f" · ★ {fila.calificacion:.0f}" if pd.notna(fila.calificacion) else ""
                            st.markdown(f"> {fila.texto}")
                            st.caption(f"{nombres_fuente[fila.fuente]}{estrellas} · {fila.fecha:%d/%m/%Y}")
    except Exception as error:
        st.error(f"No se pudo leer el top de quejas: {error}")
