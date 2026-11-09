import pandas as pd
import pytest

from src.ingesta import leer_csv
from src.limpieza import clasificar_columnas, limpiar_ejercicio
from src.utils.config import ruta_csv


def _fila(dj, cuit, anio, tipo, rect, bf="100.00"):
    f = {"dj_id": str(dj), "cuit": str(cuit), "anio": str(anio), "tipo_declaracion_jurada_id": "1",
         "tipo_declaracion_jurada_descripcion": tipo, "rectificativa": str(rect),
         "funcionario_apellido_nombre": " Perez  Juan ", "sector": "PUBLICO", "organismo": "", "actividad_principal_ambito": "NA",
         "cargo": "Director  Nacional", "desde": "200812", "goza_de_licencia": "NO", "fecha_inicio_licencia": "",
         "horas_dedicacion": "40", "proveedor_contratista": "NO",
         "total_bienes_inicio": "50.00", "total_bienes_final": bf, "deudas_inicio": "0", "total_deudas_final": "0",
         "diferencia_valuacion": "50.00"}
    return f


def _df(filas):
    return pd.DataFrame(filas, dtype=str)


def test_clasificacion(cfg):
    cols = list(_df([_fila(1, 20, 2024, "Anual", 0)]).columns)
    t = clasificar_columnas(cols, cfg)
    assert t["dj_id"] == "entero_grande" and t["anio"] == "entero" and t["desde"] == "fecha"
    assert t["total_bienes_final"] == "importe" and t["cargo"] == "texto"


def test_desempate_y_solo_anuales(cfg):
    df = _df([_fila(1, 20, 2024, "Anual", 0), _fila(2, 20, 2024, "Anual", 1), _fila(3, 20, 2024, "Anual", 1),
              _fila(4, 20, 2024, "Inicial", 0), _fila(5, 21, 2024, "Anual", 0)])
    out, inval, st = limpiar_ejercicio(df, cfg)
    elegidas = set(out.loc[out["es_analizada"], "dj_id"])
    assert elegidas == {3, 5}                    # mayor rectificativa y, en empate, mayor dj_id; la inicial no se analiza
    assert out["organismo"].eq("SIN DATO").all() and out["actividad_principal_ambito"].eq("SIN DATO").all()
    assert out["cargo_normalizado"].iloc[0] == "DIRECTOR NACIONAL"
    assert str(out["desde"].iloc[0]) == "2008-12-01"


def test_dj_id_duplicado_falla(cfg):
    with pytest.raises(ValueError):
        limpiar_ejercicio(_df([_fila(1, 20, 2024, "Anual", 0), _fila(1, 21, 2024, "Anual", 0)]), cfg)


def test_importe_invalido_va_a_nulo_y_se_registra(cfg):
    df = _df([_fila(1, 20, 2024, "Anual", 0, bf=".12000000.00")])
    out, inval, st = limpiar_ejercicio(df, cfg)
    assert pd.isna(out["total_bienes_final"].iloc[0])
    assert inval.iloc[0]["columna"] == "total_bienes_final" and inval.iloc[0]["motivo"] == "punto inicial"


@pytest.mark.integracion
def test_invalidos_reales_igualan_el_documento(cfg, hay_datos):
    if not hay_datos:
        pytest.skip("No están los CSV (definir DDJJ_RAW o copiarlos a data/raw).")
    total = {}
    for a in cfg["proyecto"]["ejercicios"]:
        df = leer_csv(ruta_csv(cfg, a), cfg)
        out, inval, st = limpiar_ejercicio(df, cfg)
        assert len(out) == cfg["fuente"]["registros_esperados"][a]
        for c, n in st["invalidos_por_columna"].items():
            total[c] = total.get(c, 0) + n
    esperado = cfg["limpieza"]["invalidos_esperados"]
    obtenido = {c: total.get(c, 0) for c in esperado}
    assert obtenido == esperado, f"Difiere de la Tabla del diccionario: {obtenido}"
