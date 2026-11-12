""" Suites de Great Expectations de la capa raw: 
    Lista de reglas donde varía su severidad.

    Crítica: dato incumple contrato. Se detiene el flujo.
    Advertencia: dato es extraño pero se puede utilizar. Solo se registra.
"""

from datetime import datetime, timedelta, timezone
import great_expectations as gx
import pandas as pd

from quality.reglas import (advertencia, campos_contrato, columnas_fecha, critica, fuentes_permitidas, 
                            idioma_esperado, margen_reloj_minutos, obligatorios, pais_esperado, patron_autor_hash, solo_google_play, solo_news, version_contrato_actual,)

E = gx.expectations

def preparar_tabla(registros: list[dict]) -> pd.DataFrame:
     """ onvierte los registros de un archivo raw en una tabla para validar."""
     tabla = pd.DataFrame(registros)
     for columna in campos_contrato:
          if columna not in tabla.columns and columna not in obligatorios:
               tabla[columna] = None
     for columna in columnas_fecha:
          if columna in tabla.columns:
              tabla[columna] = pd.to_datetime(tabla[columna], utc = True, errors = "coerce", format = "ISO8601")
     return tabla

def suite_raw(fuente: str) -> gx.ExpectationSuite:
     """ Reglas para cada archivo raw de la fuente indicada """
     if fuente not in fuentes_permitidas:
          raise ValueError(f"fuente desconocida: {fuente}")
     
     ahora = datetime.now(timezone.utc) + timedelta(minutes=margen_reloj_minutos)
     reglas = [
        # Críticas: estructura del contrato
        E.ExpectTableColumnsToMatchSet(column_set=campos_contrato, exact_match=True, severity=critica),
        *[E.ExpectColumnValuesToNotBeNull(column=c, severity=critica) for c in obligatorios],
        # Críticas: valores
        E.ExpectColumnValuesToBeInSet(column="fuente", value_set=[fuente], severity=critica),
        E.ExpectColumnValuesToBeUnique(column="id_registro", severity=critica),
        E.ExpectColumnValuesToMatchRegex(column="id_registro", regex=rf"^{fuente}:.+$", severity=critica),
        E.ExpectColumnValueLengthsToBeBetween(column="texto", min_value=1, severity=critica),
        E.ExpectColumnValuesToMatchRegex(column="autor_hash", regex=patron_autor_hash, severity=critica),
        E.ExpectColumnMaxToBeBetween(column="fecha_publicacion", max_value=ahora, severity=critica),
        E.ExpectColumnValuesToBeBetween(column="likes", min_value=0, severity=critica),
        # Advertencias
        E.ExpectTableRowCountToBeBetween(min_value=1, severity=advertencia),
        E.ExpectColumnValuesToBeInSet(column="idioma", value_set=[idioma_esperado], severity=advertencia),
        E.ExpectColumnValuesToBeInSet(column="pais", value_set=[pais_esperado], severity=advertencia),
        E.ExpectColumnValuesToBeInSet(
            column="version_contrato", value_set=[version_contrato_actual], severity=advertencia
        ),
     ]

     # Reglas que dependen de la fuente
     if fuente == "google_play":
          reglas.append(E.ExpectColumnValuesToBeBetween(column="calificacion", min_value=1, max_value=5, severity=critica))
          reglas.append(E.ExpectColumnValuesToNotBeNull(column = "calificacion", mostly=0.95, severity = advertencia))
     else:
          reglas += [E.ExpectColumnValuesToBeNull(column =c, severity = critica) for c in solo_google_play]
     if fuente != "news":
        reglas += [E.ExpectColumnValuesToBeNull(column=c, severity=critica) for c in solo_news]
     
     return gx.ExpectationSuite(name = f"raw_{fuente}", expectations = reglas)

