"""HU-003 y HU-004: plata -> oro (esquema estrella e indicadores) con controles de integridad."""
from __future__ import annotations

import argparse

from src.utils.config import RAIZ, cargar_config
from src.utils.log import get_logger, paso

SQL = RAIZ / "sql"
SQL_NOMBRES = """
UPDATE d SET apellido_nombre = x.funcionario_normalizado
FROM oro.dim_funcionario d
JOIN (SELECT cuit, funcionario_normalizado,
             ROW_NUMBER() OVER (PARTITION BY cuit ORDER BY anio DESC, dj_id DESC) AS rn
      FROM plata.declaraciones) x ON x.cuit = d.cuit AND x.rn = 1
WHERE ISNULL(d.apellido_nombre, '') <> ISNULL(x.funcionario_normalizado, '');
"""


def controles_oro(conn, cfg: dict, logger) -> dict:
    from src.utils import db
    c = {}
    c["filas_fact"] = db.contar(conn, "oro.fact_patrimonio")
    c["filas_plata_en_oro"] = int(db.escalar(
        conn, "SELECT COUNT(*) FROM plata.declaraciones WHERE anio IN (SELECT ejercicio_fiscal FROM oro.dim_tiempo)"))
    c["funcionarios_oro"] = db.contar(conn, "oro.dim_funcionario")
    c["funcionarios_plata"] = int(db.escalar(
        conn, "SELECT COUNT(DISTINCT cuit) FROM plata.declaraciones WHERE anio IN (SELECT ejercicio_fiscal FROM oro.dim_tiempo)"))
    c["ejercicios"] = db.contar(conn, "oro.dim_tiempo")
    c["analizadas_oro"] = db.contar(conn, "oro.fact_patrimonio", "es_analizada = 1")
    c["analizadas_plata"] = int(db.escalar(
        conn, "SELECT COUNT(*) FROM plata.declaraciones WHERE es_analizada = 1 "
              "AND anio IN (SELECT ejercicio_fiscal FROM oro.dim_tiempo)"))
    c["indicador_sin_ingresos_nulo_con_ingreso"] = db.contar(
        conn, "oro.fact_patrimonio", "sin_ingresos_declarados IS NULL AND total_ingreso_neto_c1234 IS NOT NULL")
    errores = []
    if c["filas_fact"] != c["filas_plata_en_oro"]:
        errores.append("la cantidad de hechos no coincide con plata")
    if c["funcionarios_oro"] != c["funcionarios_plata"]:
        errores.append("la dimensión de funcionarios no coincide con plata")
    if c["analizadas_oro"] != c["analizadas_plata"]:
        errores.append("las declaraciones analizadas no coinciden con plata")
    if c["indicador_sin_ingresos_nulo_con_ingreso"] != 0:
        errores.append("hay indicadores sin_ingresos_declarados nulos con ingreso informado")
    logger.info("CONTROLES ORO: %s", c)
    if errores:
        raise AssertionError("Controles de oro fallidos: " + "; ".join(errores))
    return c


def cargar_oro(conn, cfg: dict, anios: list[int], reiniciar: bool, logger) -> dict:
    from src.utils import db
    if reiniciar:
        logger.warning("--reiniciar: se borran los resultados del modelo (dependen de la tabla de hechos).")
        conn.cursor().execute("DELETE FROM resultados.resultado_modelo")
        conn.cursor().execute("UPDATE resultados.ejecucion_modelo SET estado = 'invalida' WHERE estado = 'ok'")
        conn.commit()
    for anio in anios:
        with paso(logger, "oro", anio):
            try:
                db.ejecutar_script(conn, SQL / "04_oro_carga.sql", {"__ANIO__": anio})
                db.ejecutar_script(conn, SQL / "05_oro_indicadores.sql", {"__ANIO__": anio})
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    conn.cursor().execute(SQL_NOMBRES)
    conn.commit()
    return controles_oro(conn, cfg, logger)


def main(cfg: dict | None = None, anios: list[int] | None = None, reiniciar: bool = False) -> None:
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn:
        cargar_oro(conn, cfg, anios or cfg["proyecto"]["ejercicios"], reiniciar, logger)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, nargs="*")
    ap.add_argument("--reiniciar", action="store_true")
    a = ap.parse_args()
    main(anios=a.anio, reiniciar=a.reiniciar)
