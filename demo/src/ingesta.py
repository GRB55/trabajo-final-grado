"""HU-001: carga de los CSV, sin transformar, en bronce.declaraciones (idempotente)."""
from __future__ import annotations

import argparse

import pandas as pd

from src.utils.config import cargar_config, carpeta, ruta_csv
from src.utils.log import get_logger, paso, registrar_conteos


class EsquemaError(Exception):
    """El archivo no tiene la estructura esperada."""


def leer_csv(ruta, cfg: dict) -> pd.DataFrame:
    fu = cfg["fuente"]
    return pd.read_csv(ruta, sep=fu["separador"], dtype=str, keep_default_na=False, na_filter=False,
                       low_memory=False, encoding=fu["codificacion"])


def validar_esquema(columnas: list[str], referencia: list[str], anio: int, esperadas: int = 57) -> None:
    if len(columnas) != esperadas:
        raise EsquemaError(f"Ejercicio {anio}: {len(columnas)} columnas (se esperaban {esperadas}).")
    if list(columnas) != list(referencia):
        dif = [f"posición {i + 1}: '{a}' (esperada '{b}')"
               for i, (a, b) in enumerate(zip(columnas, referencia)) if a != b]
        raise EsquemaError(f"Ejercicio {anio}: la estructura difiere de la de referencia -> {dif[:5]}")


def cargar_ejercicio(conn, cfg: dict, anio: int, referencia: list[str], logger) -> int:
    from src.utils import db
    ruta = ruta_csv(cfg, anio)
    df = leer_csv(ruta, cfg)
    validar_esquema(list(df.columns), referencia, anio, cfg["fuente"]["columnas_esperadas"])
    df.insert(0, "ejercicio_archivo", anio)
    df.insert(0, "archivo_origen", ruta.name)
    try:
        conn.cursor().execute("DELETE FROM bronce.declaraciones WHERE ejercicio_archivo = ?", anio)
        n = db.insertar_df(conn, "bronce.declaraciones", df, cfg["bd"]["lote_insercion"])
        cargados = db.contar(conn, "bronce.declaraciones", "ejercicio_archivo = ?", [anio])
        esperado = cfg["fuente"]["registros_esperados"][anio]
        if cargados != esperado:
            raise EsquemaError(f"Ejercicio {anio}: cargados {cargados}, esperados {esperado}.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    registrar_conteos(logger, "ingesta", anio, len(df), cargados, 0)
    return cargados


def main(cfg: dict | None = None, anios: list[int] | None = None) -> None:
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    anios = anios or cfg["proyecto"]["ejercicios"]
    referencia = list(leer_csv(ruta_csv(cfg, cfg["proyecto"]["ejercicios"][0]), cfg).head(0).columns)
    with db.conectar(cfg) as conn:
        for anio in anios:
            with paso(logger, "ingesta", anio):
                cargar_ejercicio(conn, cfg, anio, referencia, logger)


def generar_diccionario_observado(cfg: dict | None = None):
    """Exporta por columna: nulos y ejemplos observados (insumo del Anexo de diccionario)."""
    cfg = cfg or cargar_config()
    df = pd.concat([leer_csv(ruta_csv(cfg, a), cfg) for a in cfg["proyecto"]["ejercicios"]], ignore_index=True)
    filas = []
    for c in df.columns:
        vacios = (df[c].str.strip() == "").mean()
        filas.append({"columna": c, "pct_vacios": round(vacios * 100, 2), "largo_max": int(df[c].str.len().max()),
                      "ejemplos": " | ".join(df[c][df[c] != ""].drop_duplicates().head(3))})
    out = pd.DataFrame(filas)
    out.to_csv(carpeta(cfg, "salidas") / "diccionario_observado.csv", index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, nargs="*")
    main(anios=ap.parse_args().anio)
