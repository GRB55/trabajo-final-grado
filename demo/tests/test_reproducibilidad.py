import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from src.evaluacion import estabilidad_temporal, metricas_internas  # noqa: E402
from src.modelo import ajustar, construir_variables  # noqa: E402


def _base(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    anio = rng.choice([2018, 2019, 2020, 2021], n)
    bf = np.exp(rng.normal(13, 1, n)); bi = bf * np.exp(rng.normal(0, 0.1, n))
    return pd.DataFrame({"anio": anio, "total_bienes_final": bf, "total_bienes_inicio": bi,
                         "total_deudas_final": bf * 0.1, "total_ingreso_neto_c1234": np.exp(rng.normal(12, 0.5, n))})


def _cfg(cfg):
    cfg = {**cfg, "modelo": {**cfg["modelo"], "dbscan": {"eps": 0.5, "min_samples": 8}}}
    return cfg


def test_variables_estandarizadas_por_ejercicio():
    X = construir_variables(_base())
    assert X.notna().all().all()
    medias = X.groupby(_base()["anio"]).mean().abs().to_numpy().max()
    assert medias < 1e-9


def test_misma_semilla_mismo_resultado(cfg):
    c = _cfg(cfg)
    X = construir_variables(_base()).to_numpy()
    an = _base()["anio"].to_numpy()
    a, b = ajustar(X, an, c), ajustar(X, an, c)
    assert np.array_equal(a["labels"], b["labels"]) and np.allclose(a["score"], b["score"])
    assert (a["score"][a["es_ruido"]].min() if a["es_ruido"].any() else 1) >= 0


def test_silhouette_no_aplicable_con_un_cluster(cfg):
    c = _cfg(cfg)
    X = construir_variables(_base()).to_numpy()
    r = ajustar(X, _base()["anio"].to_numpy(), c)
    m = metricas_internas(r["Z"], np.zeros(len(r["Z"]), dtype=int), r["pca"], c)
    assert m["silhouette"] is None


def test_estabilidad_temporal(cfg):
    df = _base(); X = construir_variables(df).to_numpy()
    t = estabilidad_temporal(X, df["anio"].to_numpy(), 3, 2019)
    assert t["disponible"] and 0 < t["varianza_explicada_periodo_posterior"] <= 1
