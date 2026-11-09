"""Pruebas de integridad sobre SQL Server (se omiten si no hay conexión)."""
import pytest

pyodbc = pytest.importorskip("pyodbc")


@pytest.fixture
def conn(cfg):
    from src.utils import db
    try:
        c = db.conectar(cfg)
    except Exception as e:
        pytest.skip(f"Sin conexión a SQL Server: {e}")
    yield c
    c.close()


@pytest.mark.integracion
def test_controles_de_oro(conn, cfg):
    import logging

    from src.carga_oro import controles_oro
    c = controles_oro(conn, cfg, logging.getLogger("test"))
    assert c["filas_fact"] == c["filas_plata_en_oro"]
    assert c["ejercicios"] == len(cfg["proyecto"]["ejercicios"])


@pytest.mark.integracion
def test_conteos_de_bronce(conn, cfg):
    from src.utils import db
    for anio, n in cfg["fuente"]["registros_esperados"].items():
        assert db.contar(conn, "bronce.declaraciones", "ejercicio_archivo = ?", [anio]) == n
