"""HU-006: métricas internas y análisis de estabilidad (temporal y muestral) del modelo."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors

from src.utils.config import carpeta, cargar_config
from src.utils.log import get_logger, paso


def metricas_internas(Z: np.ndarray, labels: np.ndarray, pca: PCA, cfg: dict) -> dict:
    rng = np.random.default_rng(cfg["proyecto"]["semilla"])
    fuera_ruido = np.where(labels != -1)[0]
    n_clusters = len(set(labels[fuera_ruido]))
    sil = None                                     # None = no aplicable (menos de 2 clusters)
    if n_clusters >= 2:
        idx = rng.choice(fuera_ruido, size=min(len(fuera_ruido), cfg["modelo"]["silhouette_muestra"]), replace=False)
        sil = float(silhouette_score(Z[idx], labels[idx]))
    return {"varianza_explicada": float(pca.explained_variance_ratio_.sum()),
            "proporcion_ruido": float((labels == -1).mean()), "n_clusters": int(n_clusters), "silhouette": sil}


def estabilidad_temporal(X: np.ndarray, anios: np.ndarray, k: int, corte: int) -> dict:
    """PCA con los ejercicios <= corte, proyectado sobre los posteriores."""
    temprano, tardio = X[anios <= corte], X[anios > corte]
    if len(temprano) == 0 or len(tardio) == 0:
        return {"disponible": False}
    p1 = PCA(n_components=k, svd_solver="full").fit(temprano)
    p2 = PCA(n_components=k, svd_solver="full").fit(tardio)
    var_proy = float(np.var(p1.transform(tardio), axis=0).sum() / np.var(tardio, axis=0).sum())
    cos = [abs(float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))) for a, b in zip(p1.components_, p2.components_)]
    return {"disponible": True, "varianza_explicada_periodo_posterior": var_proy,
            "similitud_coseno_componentes": [round(c, 4) for c in cos],
            "varianza_explicada_periodo_inicial": float(p1.explained_variance_ratio_.sum()),
            "varianza_explicada_ajuste_propio_posterior": float(p2.explained_variance_ratio_.sum())}


def _top_k(score: np.ndarray, k: int) -> set:
    return set(np.argpartition(-score, k - 1)[:k]) if 0 < k < len(score) else set()


def _puntuar(Z: np.ndarray, cfg: dict):
    m = cfg["modelo"]
    db = DBSCAN(eps=m["dbscan"]["eps"], min_samples=m["dbscan"]["min_samples"], n_jobs=-1).fit(Z)
    if len(db.components_) == 0:
        return None, db
    return NearestNeighbors(n_neighbors=1).fit(db.components_).kneighbors(Z)[0].ravel(), db


def estabilidad_muestral(Z: np.ndarray, anios: np.ndarray, cfg: dict) -> dict:
    """Por ejercicio: Jaccard entre los K casos de mayor score de la corrida de referencia y los de submuestras."""
    from src.modelo import memoria_estimada_gb
    ev = cfg["evaluacion"]
    rng = np.random.default_rng(cfg["proyecto"]["semilla"])
    anios_eval = ev.get("ejercicios_estabilidad") or sorted(int(a) for a in np.unique(anios))
    detalle = {}
    for a in anios_eval:
        Za = Z[anios == a]
        if len(Za) > ev["max_puntos"]:
            Za = Za[rng.choice(len(Za), ev["max_puntos"], replace=False)]
        if memoria_estimada_gb(Za, cfg["modelo"]["dbscan"]["eps"]) > cfg["modelo"].get("max_memoria_gb", 8):
            detalle[int(a)] = {"disponible": False, "motivo": "memoria"}
            continue
        ref, db = _puntuar(Za, cfg)
        k = int((db.labels_ == -1).sum())
        top_ref = _top_k(ref, k) if ref is not None else set()
        if not top_ref:
            detalle[int(a)] = {"disponible": False, "motivo": "sin ruido o sin núcleos"}
            continue
        jac = []
        for _ in range(ev["n_submuestras"]):
            idx = rng.choice(len(Za), int(len(Za) * ev["fraccion"]), replace=False)
            d = DBSCAN(eps=cfg["modelo"]["dbscan"]["eps"], min_samples=cfg["modelo"]["dbscan"]["min_samples"], n_jobs=-1).fit(Za[idx])
            if len(d.components_) == 0:
                jac.append(0.0)
                continue
            s = NearestNeighbors(n_neighbors=1).fit(d.components_).kneighbors(Za)[0].ravel()
            top = _top_k(s, k)
            jac.append(len(top & top_ref) / len(top | top_ref))
        detalle[int(a)] = {"disponible": True, "k": k, "jaccard_media": float(np.mean(jac)), "jaccard_minimo": float(np.min(jac))}
    medias = [v["jaccard_media"] for v in detalle.values() if v.get("disponible")]
    return {"disponible": bool(medias), "jaccard_media_global": float(np.mean(medias)) if medias else None,
            "jaccard_minimo_global": min(v["jaccard_minimo"] for v in detalle.values() if v.get("disponible")) if medias else None,
            "por_ejercicio": detalle}


def sensibilidad_parametros(X: np.ndarray, anios: np.ndarray, ejercicio: int, epsilons, min_samples_lista,
                            cfg: dict, n_muestra: int = 60000) -> pd.DataFrame:
    """Proporción de ruido y clusters para cada par (eps, min_samples) sobre un ejercicio (como se ajusta el modelo)."""
    from src.modelo import memoria_estimada_gb
    rng = np.random.default_rng(cfg["proyecto"]["semilla"])
    Z = PCA(n_components=cfg["modelo"]["varianza_minima"], svd_solver="full").fit(X).transform(X[anios == ejercicio])
    if len(Z) > n_muestra:
        Z = Z[rng.choice(len(Z), n_muestra, replace=False)]
    limite = cfg["modelo"].get("max_memoria_gb", 8)
    filas = []
    for ms in min_samples_lista:
        for eps in epsilons:
            if memoria_estimada_gb(Z, eps) > limite:
                filas.append({"eps": eps, "min_samples": ms, "proporcion_ruido": None, "n_clusters": None, "omitido": "memoria"})
                continue
            lab = DBSCAN(eps=eps, min_samples=ms, n_jobs=-1).fit_predict(Z)
            filas.append({"eps": eps, "min_samples": ms, "proporcion_ruido": float((lab == -1).mean()),
                          "n_clusters": int(len(set(lab[lab != -1]))), "omitido": ""})
    return pd.DataFrame(filas)


def concordancia_puntuacion(df: pd.DataFrame, res_completo: dict, cfg: dict, anio_prueba: int) -> dict:
    """Prueba de la capacidad de puntuar sin reajustar.

    Se ajusta el modelo solo con los ejercicios anteriores a `anio_prueba`, se puntúa ese ejercicio como si fuera nuevo
    (estadísticos y núcleos del último ejercicio ajustado) y se compara con el resultado del ajuste completo, que sí
    incluyó al ejercicio. Mide qué tan parecidos son el ranking y los casos señalados.
    """
    from scipy.stats import spearmanr
    from src.modelo import ajustar, construir_variables
    from src.puntuar import armar_artefacto, puntuar_df
    previo = df[df["anio"] < anio_prueba]
    prueba = df[df["anio"] == anio_prueba]
    if previo.empty or prueba.empty:
        return {"omitido": "sin ejercicios previos o sin ejercicio de prueba"}
    res = ajustar(construir_variables(previo).to_numpy(), previo["anio"].to_numpy(), cfg)
    r = puntuar_df(prueba, armar_artefacto(res, previo))
    mascara = (df["anio"] == anio_prueba).to_numpy()
    s_aj, ruido_aj = res_completo["score"][mascara], res_completo["es_ruido"][mascara]
    s_pu, ruido_pu = r["score"], r["es_ruido"]
    k = max(1, int(round(0.01 * len(s_pu))))
    a, b = set(np.argsort(-s_aj)[:k]), set(np.argsort(-s_pu)[:k])
    return {"ejercicio_prueba": int(anio_prueba), "n": int(len(s_pu)), "k_top": k,
            "ruido_puntuado": float(ruido_pu.mean()), "ruido_reajustado": float(ruido_aj.mean()),
            "acuerdo_ruido": float((ruido_pu == ruido_aj).mean()),
            "jaccard_top": float(len(a & b) / len(a | b)),
            "spearman_scores": float(spearmanr(s_aj, s_pu)[0])}


def evaluar(cfg: dict | None = None) -> dict:
    from src.modelo import ajustar, preparar
    from src.utils import db
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    with db.conectar(cfg) as conn, paso(logger, "evaluacion"):
        df, X, _ = preparar(conn, cfg)
        id_ej = int(db.escalar(conn, "SELECT MAX(id_ejecucion) FROM resultados.ejecucion_modelo WHERE estado = 'ok' AND tipo = 'ajuste'"))
        ids = db.leer_df(conn, "SELECT id_hecho FROM resultados.resultado_modelo WHERE id_ejecucion = ?", [id_ej])
        usar = df["id_hecho"].isin(ids["id_hecho"]).to_numpy()          # solo lo que entró al ajuste (no las puntuaciones)
        df, X = df[usar].reset_index(drop=True), X[usar]
        res = ajustar(X, df["anio"].to_numpy(), cfg)
        etiquetas = db.leer_df(conn, "SELECT id_hecho, cluster_dbscan FROM resultados.resultado_modelo WHERE id_ejecucion = ?", [id_ej])
        alineado = df[["id_hecho"]].merge(etiquetas, on="id_hecho", how="left")["cluster_dbscan"].to_numpy()
        if not np.array_equal(alineado, res["labels"]):
            logger.warning("La recomputación difiere de lo persistido: revisar reproducibilidad (semilla/orden).")
        metricas = metricas_internas(res["Z"], res["labels"], res["pca"], cfg)
        temporal = estabilidad_temporal(X, df["anio"].to_numpy(), int(res["pca"].n_components_), cfg["evaluacion"]["corte_temporal"])
        muestral = estabilidad_muestral(res["Z"], df["anio"].to_numpy(), cfg)
        puntuacion = concordancia_puntuacion(df, res, cfg, int(df["anio"].max()))
        informe = {"id_ejecucion": id_ej, "por_ejercicio": res["por_ejercicio"], "metricas": metricas, "estabilidad_temporal": temporal,
                   "estabilidad_muestral": muestral, "concordancia_puntuacion": puntuacion}
        conn.cursor().execute("UPDATE resultados.ejecucion_modelo SET silhouette = ?, estabilidad_json = ? WHERE id_ejecucion = ?",
                              metricas["silhouette"], json.dumps(informe, ensure_ascii=False), id_ej)
        conn.commit()
    md = [f"# Evaluación del modelo (ejecución {id_ej})", "", "## Métricas internas",
          f"- Varianza explicada acumulada: {metricas['varianza_explicada']:.3f}",
          f"- Proporción de ruido: {metricas['proporcion_ruido']:.4%}",
          f"- Clusters (sin ruido): {metricas['n_clusters']}",
          f"- Silhouette: {'no aplicable (menos de 2 clusters)' if metricas['silhouette'] is None else round(metricas['silhouette'], 4)}",
          "", "## Estabilidad temporal", f"```json\n{json.dumps(temporal, indent=2)}\n```",
          "", "## Estabilidad muestral", f"```json\n{json.dumps(muestral, indent=2)}\n```",
          "", "## Puntuación de un ejercicio nuevo sin reajustar", f"```json\n{json.dumps(puntuacion, indent=2)}\n```"]
    (carpeta(cfg, "salidas") / "informe_evaluacion.md").write_text("\n".join(md), encoding="utf-8")
    return informe


if __name__ == "__main__":
    evaluar()
