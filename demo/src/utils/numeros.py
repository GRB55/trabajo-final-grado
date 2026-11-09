"""Conversión estricta de importes, enteros y fechas AAAAMM.

Un valor es *inválido* si no es un token de nulo y no se puede convertir
(por ejemplo '.12000000.00'). Se replica el criterio de pandas.to_numeric
sobre los valores no nulos, que es el usado para las cifras del trabajo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NA_TOKENS = {"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND",
             "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"}
LIMITE_IMPORTE = 1e16   # DECIMAL(18,2)


def mascara_nulos(serie: pd.Series) -> pd.Series:
    s = serie.astype(object)
    return s.isna() | s.isin(NA_TOKENS)


def motivo_invalido(valor) -> str:
    v = str(valor)
    return "punto inicial" if v.startswith(".") else "formato"


def a_importe(serie: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Devuelve (importe float redondeado a 2 decimales, motivo de invalidez o None)."""
    s = serie.astype(object)
    na = mascara_nulos(s)
    conv = pd.to_numeric(s.mask(na), errors="coerce")
    invalido = (~na) & conv.isna()
    fuera = conv.notna() & (~np.isfinite(conv) | (conv.abs() >= LIMITE_IMPORTE))
    motivo = pd.Series([None] * len(s), index=s.index, dtype=object)
    motivo[invalido] = s[invalido].map(motivo_invalido)
    motivo[fuera] = "fuera de rango"
    conv = conv.mask(invalido | fuera).round(2)
    return conv, motivo


def a_entero(serie: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Devuelve (Int64, motivo de invalidez o None)."""
    s = serie.astype(object)
    na = mascara_nulos(s)
    conv = pd.to_numeric(s.mask(na), errors="coerce")
    no_entero = conv.notna() & ((conv % 1) != 0)
    invalido = ((~na) & conv.isna()) | no_entero
    motivo = pd.Series([None] * len(s), index=s.index, dtype=object)
    motivo[invalido] = "formato"
    return conv.mask(invalido).astype("Int64"), motivo


def a_fecha_aaaamm(serie: pd.Series) -> tuple[pd.Series, pd.Series]:
    """AAAAMM -> date (primer día del mes). Devuelve (fechas objeto, motivo)."""
    s = serie.astype(object)
    na = mascara_nulos(s)
    txt = s.mask(na).astype("string").str.strip()
    valido_fmt = txt.str.fullmatch(r"\d{6}").fillna(False)
    f = pd.to_datetime(txt.where(valido_fmt) + "01", format="%Y%m%d", errors="coerce")
    invalido = (~na) & f.isna()
    motivo = pd.Series([None] * len(s), index=s.index, dtype=object)
    motivo[invalido] = "formato"
    fechas = pd.Series([d.date() if pd.notna(d) else None for d in f], index=s.index, dtype=object)
    return fechas, motivo
