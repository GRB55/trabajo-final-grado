"""HU-002: bronce -> plata. Conversión de tipos, normalización y marca de declaraciones analizadas."""
from __future__ import annotations

import argparse
import math

import pandas as pd

from src.utils.config import cargar_config, carpeta
from src.utils.log import get_logger, paso, registrar_conteos
from src.utils.numeros import a_entero, a_fecha_aaaamm, a_importe, mascara_nulos
from src.utils.texto import normalizar_nombre, normalizar_sector, normalizar_texto, normalizar_tipo

COLUMNAS_TECNICAS_BRONCE = ["id_fila", "archivo_origen", "ejercicio_archivo", "fecha_carga"]
DERIVADAS = ["funcionario_normalizado", "cargo_normalizado", "sector_normalizado", "tipo_dj", "es_analizada"]


def clasificar_columnas(cols: list[str], cfg: dict) -> dict[str, str]:
    """entero_grande | entero | fecha | importe | texto (según config.limpieza)."""
    lc = cfg["limpieza"]
    inicio = cols.index(lc["primer_importe"])
    tipos = {}
    for i, c in enumerate(cols):
        if c in ("dj_id", "cuit"):
            tipos[c] = "entero_grande"
        elif c in lc["columnas_enteras"]:
            tipos[c] = "entero"
        elif c == lc["columna_fecha_aaaamm"]:
            tipos[c] = "fecha"
        elif i >= inicio:
            tipos[c] = "importe"
        else:
            tipos[c] = "texto"
    return tipos


def limpiar_ejercicio(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Devuelve (plata, invalidos, estadisticas). 'df' son las 57 columnas de origen como texto."""
    cols = list(df.columns)
    tipos = clasificar_columnas(cols, cfg)
    lc = cfg["limpieza"]
    df = df.reset_index(drop=True)
    out = pd.DataFrame(index=df.index)
    registro = []

    def anotar(col, serie, motivo):
        m = motivo.notna()
        if m.any():
            registro.append(pd.DataFrame({"dj_id": out["dj_id"][m] if "dj_id" in out else df["dj_id"][m],
                                          "columna": col, "valor_original": serie[m], "motivo": motivo[m]}))

    for c in cols:
        t, s = tipos[c], df[c]
        if t in ("entero", "entero_grande"):
            out[c], mot = a_entero(s)
            anotar(c, s, mot)
        elif t == "importe":
            out[c], mot = a_importe(s)
            anotar(c, s, mot)
        elif t == "fecha":
            out[c], mot = a_fecha_aaaamm(s)
            anotar(c, s, mot)
        else:
            na = mascara_nulos(s)
            out[c] = s.astype(object).where(~na, None).map(lambda x: x.strip() if isinstance(x, str) else x)
    for c in ("organismo", "actividad_principal_ambito"):
        out[c] = out[c].where(out[c].notna(), "SIN DATO")

    out["funcionario_normalizado"] = out["funcionario_apellido_nombre"].map(normalizar_nombre).map(
        lambda x: x[:lc["longitud_max_funcionario"]] if isinstance(x, str) else None)
    cargo = out["cargo"].map(normalizar_texto)
    truncados = int((cargo.dropna().str.len() > lc["longitud_max_cargo"]).sum())
    out["cargo_normalizado"] = cargo.map(lambda x: x[:lc["longitud_max_cargo"]] if isinstance(x, str) else "SIN DATO")
    out["sector_normalizado"] = out["sector"].map(normalizar_sector)
    validos = tuple(lc["tipos_validos"])
    out["tipo_dj"] = out["tipo_declaracion_jurada_descripcion"].map(lambda x: normalizar_tipo(x, validos))

    # es_analizada: solo declaraciones anuales; ante duplicados (cuit, anio, tipo) gana la de mayor
    # rectificativa y, si empatan, la de mayor dj_id.
    anual = out["tipo_dj"].eq("Anual")
    cand = out[anual].assign(_r=out.loc[anual, "rectificativa"].astype("float64").fillna(-1),
                             _i=out.loc[anual, "dj_id"].astype("float64"))
    elegidas = cand.sort_values(["_r", "_i"], ascending=False).drop_duplicates(["cuit", "anio", "tipo_dj"], keep="first")
    out["es_analizada"] = out.index.isin(elegidas.index)

    if out["dj_id"].isna().any() or out["dj_id"].duplicated().any():
        raise ValueError("dj_id nulo o duplicado: no se puede continuar.")
    inval = (pd.concat(registro, ignore_index=True) if registro
             else pd.DataFrame(columns=["dj_id", "columna", "valor_original", "motivo"]))
    stats = {"filas": len(out), "analizadas": int(out["es_analizada"].sum()), "cargos_truncados": truncados,
             "invalidos_por_columna": inval.groupby("columna").size().to_dict() if len(inval) else {}}
    return out, inval, stats


def columnas_origen(conn) -> list[str]:
    from src.utils import db
    df = db.leer_df(conn, "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                          "WHERE TABLE_SCHEMA = 'bronce' AND TABLE_NAME = 'declaraciones' ORDER BY ORDINAL_POSITION")
    return [c for c in df["COLUMN_NAME"] if c not in COLUMNAS_TECNICAS_BRONCE]


def conciliar(conn, anio: int, plata: pd.DataFrame, importes: list[str]) -> None:
    """Compara conteo y sumas de importes entre pandas y la base."""
    from src.utils import db
    suma = ", ".join(f"SUM(CAST([{c}] AS FLOAT))" for c in importes)
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*), {suma} FROM plata.declaraciones WHERE anio = ?", anio)
    fila = cur.fetchone()
    if fila[0] != len(plata):
        raise ValueError(f"Conciliación {anio}: {fila[0]} filas en la base vs {len(plata)} procesadas.")
    for c, v in zip(importes, fila[1:]):
        esperado = float(plata[c].sum())
        if not math.isclose(float(v or 0.0), esperado, rel_tol=1e-9, abs_tol=0.5):
            raise ValueError(f"Conciliación {anio}: suma de {c} difiere ({v} vs {esperado}).")


def cargar_ejercicio(conn, cfg: dict, anio: int, logger) -> dict:
    from src.utils import db
    cols = columnas_origen(conn)
    lista = ", ".join(f"[{c}]" for c in cols)
    bronce = db.leer_df(conn, f"SELECT {lista} FROM bronce.declaraciones WHERE ejercicio_archivo = ?", [anio])
    plata, inval, stats = limpiar_ejercicio(bronce, cfg)
    if not (plata["anio"].dropna() == anio).all():
        raise ValueError(f"Ejercicio {anio}: hay filas con 'anio' distinto del ejercicio del archivo.")
    destino = carpeta(cfg, "salidas") / f"invalidos_{anio}.csv"
    inval.to_csv(destino, index=False, encoding="utf-8-sig")
    try:
        conn.cursor().execute("DELETE FROM plata.declaraciones WHERE anio = ?", anio)
        db.insertar_df(conn, "plata.declaraciones", plata, cfg["bd"]["lote_insercion"])
        importes = [c for c, t in clasificar_columnas(cols, cfg).items() if t == "importe"]
        conciliar(conn, anio, plata, importes)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    logger.info("Plata %s: %s filas, %s analizadas, invalidos=%s, cargos truncados=%s",
                anio, stats["filas"], stats["analizadas"], stats["invalidos_por_columna"], stats["cargos_truncados"])
    registrar_conteos(logger, "limpieza", anio, len(bronce), len(plata), len(inval))
    return stats


def main(cfg: dict | None = None, anios: list[int] | None = None) -> None:
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn:
        for anio in (anios or cfg["proyecto"]["ejercicios"]):
            with paso(logger, "limpieza", anio):
                cargar_ejercicio(conn, cfg, anio, logger)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, nargs="*")
    main(anios=ap.parse_args().anio)
