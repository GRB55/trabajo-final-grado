"""Acceso a SQL Server mediante pyodbc (sin SQLAlchemy)."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import pyodbc


def conectar(cfg: dict, autocommit: bool = False) -> pyodbc.Connection:
    bd = cfg["bd"]
    driver = os.getenv("ODBC_DRIVER", bd["driver"])
    partes = [f"DRIVER={{{driver}}}",
              f"SERVER={os.getenv('DB_SERVER', bd['servidor'])}",
              f"DATABASE={os.getenv('DB_NAME', bd['base'])}"]
    if bd["autenticacion"] == "windows":
        partes.append("Trusted_Connection=yes")
    else:
        partes += [f"UID={os.getenv('DB_USER', '')}", f"PWD={os.getenv('DB_PASSWORD', '')}"]
    partes.append("Encrypt=yes")  # el ODBC 17 no cifra por defecto; el 18 sí
    if bd.get("trust_server_certificate"):
        partes.append("TrustServerCertificate=yes")
    return pyodbc.connect(";".join(partes), autocommit=autocommit)


def _lotes(sql: str) -> list[str]:
    """pyodbc no entiende GO: se parte el script en lotes."""
    return [l.strip() for l in re.split(r"(?im)^\s*GO\s*$", sql) if l.strip()]


def ejecutar_script(conn, ruta: str | Path, reemplazos: dict | None = None) -> None:
    sql = Path(ruta).read_text(encoding="utf-8")
    for k, v in (reemplazos or {}).items():
        sql = sql.replace(k, str(v))
    cur = conn.cursor()
    for lote in _lotes(sql):
        cur.execute(lote)
        while cur.nextset():
            pass


def leer_df(conn, sql: str, params: list | tuple | None = None) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(sql, params or [])
    columnas = [c[0] for c in cur.description]
    filas = [tuple(r) for r in cur.fetchall()]
    return pd.DataFrame.from_records(filas, columns=columnas)


def insertar_df(conn, tabla: str, df: pd.DataFrame, lote: int = 10000) -> int:
    """Inserta por lotes con fast_executemany. El commit lo hace quien llama."""
    if df.empty:
        return 0
    cols = list(df.columns)
    sql = f"INSERT INTO {tabla} ({', '.join('[' + c + ']' for c in cols)}) VALUES ({', '.join(['?'] * len(cols))})"
    cur = conn.cursor()
    cur.fast_executemany = True
    obj = df.astype(object).where(df.notna(), None)
    valores = obj.values.tolist()
    for i in range(0, len(valores), lote):
        cur.executemany(sql, valores[i:i + lote])
    return len(valores)


def escalar(conn, sql: str, params: list | tuple | None = None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    fila = cur.fetchone()
    return fila[0] if fila else None


def contar(conn, tabla: str, where: str | None = None, params: list | None = None) -> int:
    return int(escalar(conn, f"SELECT COUNT(*) FROM {tabla}" + (f" WHERE {where}" if where else ""), params))
