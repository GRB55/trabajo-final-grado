"""HU-006: exporta casos señalados y controles comparables para la revisión cualitativa (con seudónimos)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.config import carpeta, cargar_config
from src.utils.log import get_logger, paso


def seleccionar(df: pd.DataFrame, n_top: int, n_control: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """df: salida de resultados.vw_demo_ranking. Control: mismo ejercicio y ámbito, no señalado, bienes más cercanos."""
    df = df.copy()
    df["_b"] = np.log1p(df["total_bienes_final"].astype(float).clip(lower=0))
    casos = df.sort_values("score_anomalia", ascending=False).head(n_top).copy()
    candidatos = df[~df["es_ruido"].astype(bool)]
    ctrl = []
    for _, c in casos.iterrows():
        pool = candidatos[(candidatos["ejercicio"] == c["ejercicio"]) & (candidatos["ambito"] == c["ambito"])]
        if pool.empty:
            continue
        ctrl.append(pool.iloc[(pool["_b"] - c["_b"]).abs().argsort()[:1]].assign(caso_comparado=c["seudonimo"]))
    controles = (pd.concat(ctrl).drop_duplicates("id_hecho").head(n_control) if ctrl else df.head(0))
    return casos.drop(columns="_b"), controles.drop(columns="_b", errors="ignore")


def main(cfg: dict | None = None) -> None:
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn, paso(logger, "revision"):
        df = db.leer_df(conn, "SELECT * FROM resultados.vw_demo_ranking")
    casos, controles = seleccionar(df, cfg["revision"]["n_top"], cfg["revision"]["n_control"])
    for t in (casos, controles):
        t["criterio_aplicado"], t["conclusion"] = "", ""
    resumen = (df.assign(señalado=df["id_hecho"].isin(casos["id_hecho"]))
                 .groupby("organismo")["señalado"].agg(["sum", "size"]).rename(columns={"sum": "casos_top", "size": "total"})
                 .sort_values("casos_top", ascending=False).head(30))
    instrucciones = pd.DataFrame({"instrucciones": [
        "Revisar cada caso señalado junto con su control comparable (mismo ejercicio y ámbito).",
        "Completar 'criterio_aplicado' y 'conclusion'. Un score alto es una señal estadística, no una determinación.",
        "Trabajar solo con seudónimos; no cruzar con nombres fuera del entorno autorizado."]})
    destino = carpeta(cfg, "salidas") / "revision_cualitativa.xlsx"
    with pd.ExcelWriter(destino) as w:
        casos.to_excel(w, sheet_name="casos", index=False)
        controles.to_excel(w, sheet_name="controles", index=False)
        resumen.to_excel(w, sheet_name="distribucion_organismo")
        instrucciones.to_excel(w, sheet_name="instrucciones", index=False)
    logger.info("Revisión exportada a %s", destino)


if __name__ == "__main__":
    main()