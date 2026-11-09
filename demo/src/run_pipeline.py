"""Punto de entrada único del pipeline.

  python -m src.run_pipeline --paso instalar      # crea esquemas y tablas (una vez)
  python -m src.run_pipeline --paso todo          # descarga -> ingesta -> limpieza -> oro -> modelo -> evaluacion
  python -m src.run_pipeline --paso puntuar [--anio 2025]   # puntúa declaraciones nuevas sin reajustar
  python -m src.run_pipeline --paso vistas|seguridad|revision
"""
from __future__ import annotations

import argparse
import os
import sys

from src import carga_oro, descarga, evaluacion, ingesta, limpieza, modelo, puntuar, revision_cualitativa
from src.utils import db
from src.utils.config import RAIZ, carpeta, cargar_config
from src.utils.log import get_logger, paso

PASOS = ["instalar", "descarga", "ingesta", "limpieza", "oro", "modelo", "evaluacion", "puntuar", "revision", "vistas", "seguridad", "todo"]
FLUJO_COMPLETO = ["descarga", "ingesta", "limpieza", "oro", "modelo", "evaluacion"]


def _sql(archivo: str) -> str:
    return str(RAIZ / "sql" / archivo)


def instalar(cfg: dict) -> None:
    with db.conectar(cfg) as conn:
        for f in ["00_esquemas.sql", "01_bronce_ddl.sql", "02_plata_ddl.sql", "03_oro_ddl.sql", "06_resultados_ddl.sql"]:
            db.ejecutar_script(conn, _sql(f))
        conn.commit()


def vistas(cfg: dict) -> None:
    sal = os.getenv("SAL_SEUDONIMO", "")
    if not sal or not sal.isascii():
        raise RuntimeError("Definir SAL_SEUDONIMO (ASCII) en .env antes de crear las vistas.")
    with db.conectar(cfg) as conn:
        db.ejecutar_script(conn, _sql("07_vistas.sql"), {"__SAL__": sal.replace("'", "''")})
        conn.commit()


def seguridad(cfg: dict) -> None:
    clave = os.getenv("BI_READER_PASSWORD", "")
    if not clave:
        raise RuntimeError("Definir BI_READER_PASSWORD en .env.")
    auditoria = carpeta(cfg, "auditoria")
    auditoria.mkdir(parents=True, exist_ok=True)
    with db.conectar(cfg, autocommit=True) as conn:
        db.ejecutar_script(conn, _sql("08_seguridad.sql"), {
            "__BASE__": cfg["bd"]["base"], "__BI_PASSWORD__": clave.replace("'", "''"),
            "__RUTA_AUDITORIA__": str(auditoria)})


def ejecutar(nombre: str, cfg: dict, anios, reiniciar: bool, forzar: bool) -> None:
    if nombre == "instalar": instalar(cfg)
    elif nombre == "descarga": descarga.main(cfg, forzar)
    elif nombre == "ingesta": ingesta.main(cfg, anios)
    elif nombre == "limpieza": limpieza.main(cfg, anios)
    elif nombre == "oro": carga_oro.main(cfg, anios, reiniciar)
    elif nombre == "modelo": modelo.main(cfg)
    elif nombre == "evaluacion": evaluacion.evaluar(cfg)
    elif nombre == "puntuar": puntuar.main(cfg, anios)
    elif nombre == "revision": revision_cualitativa.main(cfg)
    elif nombre == "vistas": vistas(cfg)
    elif nombre == "seguridad": seguridad(cfg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paso", choices=PASOS, required=True)
    ap.add_argument("--anio", type=int, nargs="*")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--reiniciar", action="store_true", help="borra resultados del modelo al recargar oro")
    a = ap.parse_args()
    cfg = cargar_config()
    logger = get_logger(cfg)
    try:
        for nombre in (FLUJO_COMPLETO if a.paso == "todo" else [a.paso]):
            with paso(logger, f"PIPELINE {nombre}"):
                ejecutar(nombre, cfg, a.anio, a.reiniciar or a.paso == "todo", a.forzar)
    except Exception as e:
        logger.error("Pipeline detenido: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
