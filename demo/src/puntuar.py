"""Puntuación de declaraciones nuevas sin reajustar el modelo (capacidad predictiva del prototipo).

DBSCAN de scikit-learn no tiene `predict`. Se usa la definición del propio algoritmo: una observación nueva pertenece
al cluster del punto núcleo más cercano si está a distancia <= eps de él; si no, es ruido. El score continuo es esa
distancia al punto núcleo más cercano (la misma definición que en el ajuste), de modo que el ranking es comparable.

Proceso: (1) estandarizar con los estadísticos del ejercicio de referencia; (2) proyectar con el PCA ajustado;
(3) distancia a los núcleos del ejercicio de referencia. La referencia es el propio ejercicio si estaba en el ajuste y,
si no (ejercicio nuevo), el último ejercicio ajustado: supuesto que no corrige la inflación entre años, por lo que
conviene reajustar el modelo completo cuando se publica un ejercicio nuevo.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from src.modelo import SQL_BASE, estadisticos_ejercicio, estandarizar_con, variables_crudas
from src.utils.config import cargar_config, carpeta
from src.utils.log import get_logger, paso


def armar_artefacto(res: dict, df: pd.DataFrame) -> dict:
    return {"pca": res["pca"], "estadisticos": estadisticos_ejercicio(df), "nucleos": res["nucleos"],
            "etiquetas_nucleo": res["etiquetas_nucleo"], "eps": res["eps"], "min_samples": res["min_samples"]}


def guardar_artefacto(res: dict, df: pd.DataFrame, cfg: dict, id_ejecucion: int) -> Path:
    ruta = carpeta(cfg, "salidas") / f"modelo_{id_ejecucion}.joblib"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(armar_artefacto(res, df), ruta)
    return ruta


def cargar_artefacto(ruta) -> dict:
    return joblib.load(ruta)


def referencia_para(art: dict, anio: int) -> int:
    return int(anio) if int(anio) in art["estadisticos"] else max(art["estadisticos"])


def puntuar_df(df: pd.DataFrame, art: dict, referencia: int | None = None) -> dict:
    """Puntúa las filas de `df` (con anio y los importes). Las filas con algún importe faltante quedan fuera (`ok` False)."""
    X = variables_crudas(df)
    ok = X.notna().all(axis=1).to_numpy()
    n = len(df)
    score, ruido = np.full(n, np.nan), np.zeros(n, dtype=bool)
    cluster, Zout = np.full(n, -1, dtype=np.int64), np.full((n, art["pca"].n_components_), np.nan)
    anios = df["anio"].to_numpy()
    for a in np.unique(anios[ok]):
        ref = referencia if referencia is not None else referencia_para(art, a)
        idx = np.where(ok & (anios == a))[0]
        est = art["estadisticos"][ref]
        Z = art["pca"].transform(estandarizar_con(X.iloc[idx], est["media"], est["desvio"]))
        nn = NearestNeighbors(n_neighbors=1).fit(art["nucleos"][ref])
        d, j = nn.kneighbors(Z)
        d, j = d.ravel(), j.ravel()
        score[idx], Zout[idx] = d, Z
        ruido[idx] = d > art["eps"]
        cluster[idx] = np.where(d > art["eps"], -1, art["etiquetas_nucleo"][ref][j])
    return {"ok": ok, "Z": Zout, "score": score, "es_ruido": ruido, "cluster": cluster}


def main(cfg: dict | None = None, anios: list[int] | None = None, referencia: int | None = None) -> int | None:
    """Puntúa en la base las declaraciones analizadas que todavía no tienen resultado del ajuste vigente."""
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn, paso(logger, "puntuacion"):
        fila = db.leer_df(conn, "SELECT TOP 1 id_ejecucion, ruta_modelo FROM resultados.ejecucion_modelo "
                                "WHERE estado = 'ok' AND tipo = 'ajuste' ORDER BY id_ejecucion DESC")
        if fila.empty or not fila.loc[0, "ruta_modelo"]:
            raise RuntimeError("No hay un ajuste vigente con modelo guardado: ejecutar primero --paso modelo.")
        id_base, ruta = int(fila.loc[0, "id_ejecucion"]), fila.loc[0, "ruta_modelo"]
        art = cargar_artefacto(ruta)
        df = db.leer_df(conn, SQL_BASE)
        ya = db.leer_df(conn, "SELECT r.id_hecho FROM resultados.resultado_modelo r JOIN resultados.ejecucion_modelo e "
                              "ON e.id_ejecucion = r.id_ejecucion WHERE e.estado = 'ok' AND (e.id_ejecucion = ? OR e.id_ejecucion_base = ?)",
                        [id_base, id_base])
        df = df[~df["id_hecho"].isin(ya["id_hecho"])]
        if anios:
            df = df[df["anio"].isin(anios)]
        df = df.reset_index(drop=True)
        if df.empty:
            logger.info("No hay declaraciones nuevas para puntuar.")
            return None
        r = puntuar_df(df, art, referencia)
        ok = r["ok"]
        logger.info("Declaraciones nuevas: %s; puntuadas: %s; sin importes completos: %s", len(df), int(ok.sum()), int((~ok).sum()))
        if not ok.any():
            return None
        cur = conn.cursor()
        try:
            refs = sorted({referencia_para(art, a) if referencia is None else referencia for a in df.loc[ok, "anio"].unique()})
            cur.execute("INSERT INTO resultados.ejecucion_modelo (estado, tipo, id_ejecucion_base, eps, min_samples, n_componentes, "
                        "proporcion_ruido, n_evaluadas, n_no_evaluadas, semilla, estabilidad_json) "
                        "OUTPUT INSERTED.id_ejecucion VALUES ('en_curso', 'puntuacion', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        id_base, art["eps"], art["min_samples"], int(art["pca"].n_components_), float(r["es_ruido"][ok].mean()),
                        int(ok.sum()), int((~ok).sum()), cfg["proyecto"]["semilla"],
                        json.dumps({"ejercicios_referencia": refs, "ejercicios_puntuados": sorted(int(a) for a in df.loc[ok, "anio"].unique())}))
            id_ej = int(cur.fetchone()[0])
            filas = pd.DataFrame({
                "id_ejecucion": id_ej, "id_hecho": df.loc[ok, "id_hecho"].astype("int64").to_numpy(),
                "componentes_pca": [json.dumps([round(float(v), 4) for v in z]) for z in r["Z"][ok]],
                "cluster_dbscan": r["cluster"][ok].astype("int16"), "es_ruido": r["es_ruido"][ok],
                "score_anomalia": r["score"][ok].astype("float64"), "fecha_ejecucion": datetime.now()})
            db.insertar_df(conn, "resultados.resultado_modelo", filas, cfg["bd"]["lote_insercion"])
            cur.execute("UPDATE resultados.ejecucion_modelo SET estado = 'ok' WHERE id_ejecucion = ?", id_ej)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        logger.info("Puntuación registrada (ejecución %s, base %s)", id_ej, id_base)
        return id_ej


if __name__ == "__main__":
    main()
