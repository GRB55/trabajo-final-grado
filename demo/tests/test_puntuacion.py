import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from src.evaluacion import concordancia_puntuacion  # noqa: E402
from src.modelo import ajustar, construir_variables  # noqa: E402
from src.puntuar import armar_artefacto, puntuar_df  # noqa: E402
from tests.test_reproducibilidad import _base, _cfg  # noqa: E402


def test_puntuar_el_conjunto_de_ajuste_reproduce_el_ajuste(cfg):
    c, df = _cfg(cfg), _base()
    res = ajustar(construir_variables(df).to_numpy(), df["anio"].to_numpy(), c)
    r = puntuar_df(df, armar_artefacto(res, df))
    assert np.allclose(r["score"], res["score"], atol=1e-5)
    assert np.array_equal(r["es_ruido"], res["es_ruido"])


def test_un_caso_extremo_nuevo_es_ruido_y_uno_tipico_no(cfg):
    c, df = _cfg(cfg), _base()
    res = ajustar(construir_variables(df).to_numpy(), df["anio"].to_numpy(), c)
    art = armar_artefacto(res, df)
    nuevo = pd.DataFrame({"anio": [2020, 2020], "total_bienes_final": [df.total_bienes_final.median(), 1e13],
                          "total_bienes_inicio": [df.total_bienes_final.median(), 1e5],
                          "total_deudas_final": [df.total_bienes_final.median() * 0.1, 0.0],
                          "total_ingreso_neto_c1234": [df.total_ingreso_neto_c1234.median(), 1e3]})
    r = puntuar_df(nuevo, art)
    assert not r["es_ruido"][0] and r["es_ruido"][1]
    assert r["score"][1] > r["score"][0]


def test_ejercicio_nuevo_usa_el_ultimo_como_referencia_y_sin_importes_queda_fuera(cfg):
    c, df = _cfg(cfg), _base()
    res = ajustar(construir_variables(df).to_numpy(), df["anio"].to_numpy(), c)
    nuevo = df.head(5).assign(anio=2030)
    nuevo.loc[nuevo.index[0], "total_bienes_final"] = np.nan
    r = puntuar_df(nuevo, armar_artefacto(res, df))
    assert (~r["ok"]).sum() == 1 and np.isnan(r["score"][0]) and np.isfinite(r["score"][1:]).all()


def test_concordancia_devuelve_metricas(cfg):
    c, df = _cfg(cfg), _base(n=6000)
    res = ajustar(construir_variables(df).to_numpy(), df["anio"].to_numpy(), c)
    m = concordancia_puntuacion(df, res, c, 2021)
    assert 0 <= m["jaccard_top"] <= 1 and m["acuerdo_ruido"] > 0.8 and m["spearman_scores"] > 0.5
