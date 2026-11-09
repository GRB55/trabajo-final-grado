"""Genera sql/01_bronce_ddl.sql y sql/02_plata_ddl.sql a partir de los CSV reales.

Uso:  python -m tools.generar_ddl
Los tamaños de texto salen de la longitud máxima observada en los diez archivos (+20 %).
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.limpieza import clasificar_columnas
from src.utils.config import RAIZ, cargar_config, ruta_csv


def leer_todo(cfg) -> pd.DataFrame:
    fu = cfg["fuente"]
    return pd.concat([pd.read_csv(ruta_csv(cfg, a), sep=fu["separador"], dtype=str, keep_default_na=False,
                                  na_filter=False, low_memory=False, encoding=fu["codificacion"])
                      for a in cfg["proyecto"]["ejercicios"]], ignore_index=True)


def tamano(maxlen: int, minimo: int = 20) -> str:
    n = max(minimo, math.ceil(maxlen * 1.2))
    return "NVARCHAR(MAX)" if n > 4000 else f"NVARCHAR({n})"


def main() -> None:
    cfg = cargar_config()
    df = leer_todo(cfg)
    cols = list(df.columns)
    largos = {c: int(df[c].str.len().max()) for c in cols}
    # Bronce
    b = ["IF OBJECT_ID('bronce.declaraciones') IS NULL", "CREATE TABLE bronce.declaraciones (",
         "  id_fila BIGINT IDENTITY(1,1) PRIMARY KEY,", "  archivo_origen VARCHAR(100) NOT NULL,",
         "  ejercicio_archivo SMALLINT NOT NULL,", "  fecha_carga DATETIME2 NOT NULL DEFAULT SYSDATETIME(),"]
    b += [f"  [{c}] {tamano(largos[c])} NULL," for c in cols]
    b[-1] = b[-1].rstrip(",")
    b += [");", "GO",
          "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_bronce_ejercicio' AND object_id = OBJECT_ID('bronce.declaraciones'))",
          "  CREATE INDEX ix_bronce_ejercicio ON bronce.declaraciones (ejercicio_archivo);", "GO"]
    (RAIZ / "sql" / "01_bronce_ddl.sql").write_text("-- Generado por tools/generar_ddl.py\n" + "\n".join(b) + "\n", encoding="utf-8")
    # Plata
    tipos = clasificar_columnas(cols, cfg)
    sql_tipo = {"entero_grande": "BIGINT", "entero": "SMALLINT", "importe": "DECIMAL(18,2)", "fecha": "DATE"}
    p = ["IF OBJECT_ID('plata.declaraciones') IS NULL", "CREATE TABLE plata.declaraciones ("]
    for c in cols:
        t = tipos[c]
        if t == "texto":
            n = max(50, math.ceil(largos[c] * 1.5))
            tp = f"NVARCHAR({n})" if n <= 4000 else "NVARCHAR(MAX)"
        else:
            tp = sql_tipo[t]
        nn = " NOT NULL PRIMARY KEY" if c == "dj_id" else " NULL"
        p.append(f"  [{c}] {tp}{nn},")
    p += ["  funcionario_normalizado NVARCHAR(200) NULL,", "  cargo_normalizado NVARCHAR(400) NOT NULL,",
          "  sector_normalizado VARCHAR(10) NOT NULL,", "  tipo_dj VARCHAR(10) NOT NULL,",
          "  es_analizada BIT NOT NULL DEFAULT 0", ");", "GO",
          "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_plata_cuit_anio' AND object_id = OBJECT_ID('plata.declaraciones'))",
          "  CREATE INDEX ix_plata_cuit_anio ON plata.declaraciones (cuit, anio);", "GO",
          "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_plata_anio_tipo' AND object_id = OBJECT_ID('plata.declaraciones'))",
          "  CREATE INDEX ix_plata_anio_tipo ON plata.declaraciones (anio, tipo_dj);", "GO"]
    (RAIZ / "sql" / "02_plata_ddl.sql").write_text("-- Generado por tools/generar_ddl.py\n" + "\n".join(p) + "\n", encoding="utf-8")
    print("DDL generados: sql/01_bronce_ddl.sql y sql/02_plata_ddl.sql")


if __name__ == "__main__":
    main()
