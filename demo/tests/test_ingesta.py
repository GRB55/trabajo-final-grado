import pytest

from src.ingesta import EsquemaError, leer_csv, validar_esquema
from src.utils.config import ruta_csv


def test_esquema_distinto_falla():
    with pytest.raises(EsquemaError):
        validar_esquema(["a", "b"], ["a", "c"], 2024, esperadas=2)
    with pytest.raises(EsquemaError):
        validar_esquema(["a"], ["a"], 2024, esperadas=57)


@pytest.mark.integracion
def test_archivos_reales_tienen_57_columnas_y_los_registros_esperados(cfg, hay_datos):
    if not hay_datos:
        pytest.skip("No están los CSV.")
    ref = None
    for a in cfg["proyecto"]["ejercicios"]:
        df = leer_csv(ruta_csv(cfg, a), cfg)
        ref = ref or list(df.columns)
        validar_esquema(list(df.columns), ref, a, cfg["fuente"]["columnas_esperadas"])
        assert len(df) == cfg["fuente"]["registros_esperados"][a]
