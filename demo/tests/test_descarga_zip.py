import logging
import zipfile

import pandas as pd

from src.descarga import extraer_zip

LOG = logging.getLogger("t")


def _cfg(tmp_path, anios):
    return {"proyecto": {"ejercicios": anios},
            "rutas": {"raw": str(tmp_path / "raw")},
            "fuente": {"patron_archivo": "declaraciones-juradas-{anio}.csv", "separador": ";",
                       "codificacion": "utf-8-sig"}}


def test_zip_un_csv_por_anio_ignora_anios_fuera_del_proyecto(tmp_path):
    cfg = _cfg(tmp_path, [2015, 2016])
    (tmp_path / "raw").mkdir()
    zp = tmp_path / "f.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for a in (2012, 2015, 2016):
            z.writestr(f"datos/declaraciones-juradas-{a}.csv", "anio;x\n%d;1\n" % a)
    assert extraer_zip(cfg, zp, LOG) == [2015, 2016]
    assert not (tmp_path / "raw" / "declaraciones-juradas-2012.csv").exists()
    assert (tmp_path / "raw" / "declaraciones-juradas-2016.csv").read_text().startswith("anio;x")


def test_zip_un_solo_csv_se_reparte_por_anio(tmp_path):
    cfg = _cfg(tmp_path, [2015, 2016])
    (tmp_path / "raw").mkdir()
    zp = tmp_path / "f.zip"
    contenido = "anio;x\n2012;9\n2015;1\n2015;2\n2016;3\n"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("todo.csv", contenido)
    assert extraer_zip(cfg, zp, LOG) == [2015, 2016]
    d15 = pd.read_csv(tmp_path / "raw" / "declaraciones-juradas-2015.csv", sep=";", encoding="utf-8-sig")
    assert list(d15["x"]) == [1, 2]


def test_zip_ambiguo_da_error_claro(tmp_path):
    import pytest
    cfg = _cfg(tmp_path, [2015, 2016])
    (tmp_path / "raw").mkdir()
    zp = tmp_path / "f.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a.csv", "anio;x\n"); z.writestr("b.csv", "anio;x\n")
    with pytest.raises(RuntimeError, match="Archivos del ZIP"):
        extraer_zip(cfg, zp, LOG)
