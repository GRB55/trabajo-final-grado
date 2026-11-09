import pandas as pd

from src.utils.numeros import a_entero, a_fecha_aaaamm, a_importe
from src.utils.texto import normalizar_nombre, normalizar_sector, normalizar_texto, normalizar_tipo, pseudonimo


def test_normalizar_texto():
    assert normalizar_texto("  Director   General ") == "DIRECTOR GENERAL"
    assert normalizar_texto("Dirección Nacional") == "DIRECCION NACIONAL"
    assert normalizar_texto(None) is None and normalizar_texto("   ") is None


def test_normalizar_nombre_conserva_acentos():
    assert normalizar_nombre(" Pérez,  José ") == "PÉREZ, JOSÉ"


def test_sector_y_tipo():
    assert normalizar_sector("publico") == "PUBLICO"
    assert normalizar_sector("0") == "SIN DATO" and normalizar_sector("1") == "SIN DATO" and normalizar_sector(None) == "SIN DATO"
    assert normalizar_tipo("ANUAL") == "Anual" and normalizar_tipo("xx") == "SIN DATO" and normalizar_tipo(None) == "SIN DATO"


def test_importes_validos_e_invalidos():
    s = pd.Series(["1234.50", "0", "-5.00", ".12000000.00", "1,5", "abc", "inf", "1e5", "NA", "", None])
    v, mot = a_importe(s)
    assert v.iloc[0] == 1234.5 and v.iloc[1] == 0 and v.iloc[2] == -5
    invalidos = [i for i in range(len(s)) if mot.iloc[i] is not None]
    assert invalidos == [3, 4, 5, 6]                      # '.12..', '1,5', 'abc', 'inf'
    assert mot.iloc[3] == "punto inicial"
    assert pd.isna(v.iloc[8]) and pd.isna(v.iloc[9]) and pd.isna(v.iloc[10])   # nulos no son inválidos


def test_entero_y_fecha():
    v, mot = a_entero(pd.Series(["12", "x", "1.5", "NA"]))
    assert v.iloc[0] == 12 and mot.iloc[1] == "formato" and mot.iloc[2] == "formato" and mot.iloc[3] is None
    f, m = a_fecha_aaaamm(pd.Series(["200812", "200813", "abc", "", "2008121"]))
    assert str(f.iloc[0]) == "2008-12-01" and m.iloc[1] == "formato" and m.iloc[2] == "formato" and m.iloc[3] is None and m.iloc[4] == "formato"


def test_pseudonimo():
    a, b = pseudonimo(20123456789, "sal"), pseudonimo(20123456780, "sal")
    assert a == pseudonimo(20123456789, "sal") and a != b and len(a) == 12 and a.startswith("F-")
