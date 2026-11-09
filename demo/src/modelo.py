"""HU-005: PCA + DBSCAN sobre las declaraciones analizadas y persistencia de resultados.

Variables (4), todas estandarizadas dentro de cada ejercicio para que los importes en pesos
corrientes de distintos años sean comparables:
  x1 = log(1 + bienes finales)   x2 = log(1 + deudas finales)   x3 = log(1 + ingresos netos)
  x4 = log(1 + bienes finales) - log(1 + bienes iniciales)      (variación patrimonial relativa)
PCA con todas las declaraciones; DBSCAN dentro de cada ejercicio (por memoria y para comparar con pares del mismo año).
Score de anomalía = distancia, en el espacio de componentes principales, al punto núcleo de DBSCAN más cercano
(es ruido si esa distancia supera eps). Los objetos ajustados (PCA, estadísticos y puntos núcleo) se guardan para
puntuar declaraciones nuevas sin reajustar (src/puntuar.py).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

from src.utils.config import cargar_config
from src.utils.log import get_logger, paso, registrar_conteos

VARIABLES = ["x1_bienes", "x2_deudas", "x3_ingresos", "x4_variacion"]
SQL_BASE = """
SELECT f.id_hecho, t.ejercicio_fiscal AS anio, f.total_bienes_inicio, f.total_bienes_final,
       f.total_deudas_final, f.total_ingreso_neto_c1234
FROM oro.fact_patrimonio f JOIN oro.dim_tiempo t ON t.id_tiempo = f.id_tiempo
WHERE f.es_analizada = 1
ORDER BY f.id_hecho
"""


def _l1p(s: pd.Series) -> pd.Series:
    return np.log1p(s.astype("float64").clip(lower=0))


def variables_crudas(df: pd.DataFrame) -> pd.DataFrame:
    """Las 4 variables sin estandarizar (NaN si falta algún importe)."""
    return pd.DataFrame({
        "x1_bienes": _l1p(df["total_bienes_final"]),
        "x2_deudas": _l1p(df["total_deudas_final"]),
        "x3_ingresos": _l1p(df["total_ingreso_neto_c1234"]),
        "x4_variacion": _l1p(df["total_bienes_final"]) - _l1p(df["total_bienes_inicio"]),
    }, index=df.index)


def estadisticos_ejercicio(df: pd.DataFrame) -> dict:
    """Media y desvío de cada variable por ejercicio (los que se usan para estandarizar y, luego, para puntuar)."""
    X = variables_crudas(df)
    g = X.groupby(df["anio"])
    return {int(a): {"media": g.mean().loc[a].to_numpy(), "desvio": g.std(ddof=0).loc[a].to_numpy()} for a in g.groups}


def estandarizar_con(X: pd.DataFrame, media: np.ndarray, desvio: np.ndarray) -> np.ndarray:
    """Estandariza con estadísticos dados (desvío cero -> 0)."""
    d = np.where(np.asarray(desvio) == 0, np.nan, desvio)
    Z = (X.to_numpy(dtype="float64") - media) / d
    return np.where(np.isnan(Z) & ~np.isnan(X.to_numpy(dtype="float64")), 0.0, Z)


def construir_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve las 4 variables estandarizadas por ejercicio (NaN si falta algún importe)."""
    X = variables_crudas(df)
    g = X.groupby(df["anio"])
    media, desvio = g.transform("mean"), g.transform("std", ddof=0)
    Z = (X - media) / desvio.replace(0, np.nan)
    return Z.mask(X.notna() & Z.isna(), 0.0)          # desvío cero -> 0


def vecindario_medio(Z: np.ndarray, eps: float, n: int = 1500, semilla: int = 42) -> float:
    """Tamaño medio del vecindario (puntos a distancia <= eps) estimado con una muestra de consultas."""
    rng = np.random.default_rng(semilla)
    q = Z[rng.choice(len(Z), min(n, len(Z)), replace=False)]
    vec = NearestNeighbors(radius=eps).fit(Z).radius_neighbors(q, return_distance=False)
    return float(np.mean([len(v) for v in vec]))


def memoria_estimada_gb(Z: np.ndarray, eps: float) -> float:
    """DBSCAN guarda los vecindarios (8 bytes por vecino): con eps grande la memoria se dispara."""
    return len(Z) * vecindario_medio(Z, eps) * 8 / 1e9


def ajustar(X: np.ndarray, anios: np.ndarray, cfg: dict) -> dict:
    """PCA sobre todas las declaraciones y DBSCAN dentro de cada ejercicio.

    DBSCAN guarda los vecindarios en memoria: sobre ~450.000 puntos juntos no entra en un equipo común, y
    además cada declaración debe compararse con sus pares del mismo año (las variables ya están
    estandarizadas por ejercicio). Los clusters se numeran de forma única entre ejercicios.
    """
    m = cfg["modelo"]
    eps, ms = m["dbscan"]["eps"], m["dbscan"]["min_samples"]
    if eps is None or ms is None:
        raise ValueError("Falta definir modelo.dbscan.eps y min_samples en config.yaml "
                         "(ver notebooks/02_seleccion_parametros.ipynb).")
    pca = PCA(n_components=m["varianza_minima"], svd_solver="full")
    Z = pca.fit_transform(X)
    limite = m.get("max_memoria_gb", 8)
    labels = np.full(len(X), -1, dtype=np.int64)
    score = np.zeros(len(X))
    por_ejercicio, desplazamiento = {}, 0
    nucleos, etiquetas_nucleo = {}, {}
    for a in np.unique(anios):
        idx = np.where(anios == a)[0]
        Za = Z[idx]
        estimada = memoria_estimada_gb(Za, eps)
        if estimada > limite:
            raise MemoryError(f"Ejercicio {a}: eps={eps} implicaría unos {estimada:.1f} GB (límite {limite} GB): "
                              "reducir eps o aumentar modelo.max_memoria_gb.")
        db = DBSCAN(eps=eps, min_samples=ms, n_jobs=-1).fit(Za)
        if len(db.components_) == 0:
            raise ValueError(f"Ejercicio {a}: DBSCAN no encontró puntos núcleo; parámetros inválidos.")
        score[idx] = NearestNeighbors(n_neighbors=1).fit(db.components_).kneighbors(Za)[0].ravel()
        lab = db.labels_.astype(np.int64)
        n_cl = int(lab.max()) + 1 if lab.max() >= 0 else 0
        lab[lab >= 0] += desplazamiento
        nucleos[int(a)] = db.components_.astype("float32")
        etiquetas_nucleo[int(a)] = lab[db.core_sample_indices_].astype("int64")
        labels[idx] = lab
        por_ejercicio[int(a)] = {"n": int(len(idx)), "proporcion_ruido": float((db.labels_ == -1).mean()), "clusters": n_cl}
        desplazamiento += n_cl
    return {"pca": pca, "Z": Z, "labels": labels, "es_ruido": labels == -1, "score": score, "por_ejercicio": por_ejercicio,
            "nucleos": nucleos, "etiquetas_nucleo": etiquetas_nucleo, "eps": float(eps), "min_samples": int(ms)}


def preparar(conn, cfg: dict):
    """Lee oro y devuelve (df_evaluable, X_evaluable, n_total)."""
    from src.utils import db
    df = db.leer_df(conn, SQL_BASE)
    X = construir_variables(df)
    ok = X.notna().all(axis=1)
    return df[ok].reset_index(drop=True), X[ok].to_numpy(), len(df)


def version_codigo() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "sin-git"


def persistir(conn, cfg: dict, df: pd.DataFrame, res: dict, n_total: int) -> int:
    from src.utils import db
    pca, labels = res["pca"], res["labels"]
    ahora = datetime.now()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO resultados.ejecucion_modelo (estado, eps, min_samples, n_componentes, varianza_explicada, "
        "varianza_por_componente, proporcion_ruido, n_evaluadas, n_no_evaluadas, semilla, version_codigo, estabilidad_json) "
        "OUTPUT INSERTED.id_ejecucion VALUES ('en_curso', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        float(cfg["modelo"]["dbscan"]["eps"]), int(cfg["modelo"]["dbscan"]["min_samples"]), int(pca.n_components_),
        float(pca.explained_variance_ratio_.sum()), json.dumps([round(float(v), 6) for v in pca.explained_variance_ratio_]),
        float(res["es_ruido"].mean()), len(df), n_total - len(df), cfg["proyecto"]["semilla"], version_codigo(),
        json.dumps({"por_ejercicio": res["por_ejercicio"]}))
    id_ej = int(cur.fetchone()[0])
    filas = pd.DataFrame({
        "id_ejecucion": id_ej, "id_hecho": df["id_hecho"].astype("int64"),
        "componentes_pca": [json.dumps([round(float(v), 4) for v in z]) for z in res["Z"]],
        "cluster_dbscan": labels.astype("int16"), "es_ruido": res["es_ruido"],
        "score_anomalia": res["score"].astype("float64"), "fecha_ejecucion": ahora})
    db.insertar_df(conn, "resultados.resultado_modelo", filas, cfg["bd"]["lote_insercion"])
    cur.execute("UPDATE resultados.ejecucion_modelo SET estado = 'ok' WHERE id_ejecucion = ?", id_ej)
    return id_ej


def main(cfg: dict | None = None) -> int:
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn:
        with paso(logger, "modelo"):
            df, X, n_total = preparar(conn, cfg)
            logger.info("Evaluables: %s de %s declaraciones analizadas", len(df), n_total)
            res = ajustar(X, df["anio"].to_numpy(), cfg)
            logger.info("PCA: %s componentes (%.1f %% de varianza); ruido: %.3f %%",
                        res["pca"].n_components_, 100 * res["pca"].explained_variance_ratio_.sum(),
                        100 * res["es_ruido"].mean())
            try:
                id_ej = persistir(conn, cfg, df, res, n_total)
                from src.puntuar import guardar_artefacto
                ruta = guardar_artefacto(res, df, cfg, id_ej)
                conn.cursor().execute("UPDATE resultados.ejecucion_modelo SET ruta_modelo = ? WHERE id_ejecucion = ?", str(ruta), id_ej)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            registrar_conteos(logger, "modelo", "todos", n_total, len(df), n_total - len(df))
            logger.info("Ejecución %s registrada", id_ej)
            return id_ej


if __name__ == "__main__":
    main()
