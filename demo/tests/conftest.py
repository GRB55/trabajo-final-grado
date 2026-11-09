import os

import pytest

from src.utils.config import cargar_config, ruta_csv


@pytest.fixture(scope="session")
def cfg():
    return cargar_config()


@pytest.fixture(scope="session")
def hay_datos(cfg):
    return all(ruta_csv(cfg, a).exists() for a in cfg["proyecto"]["ejercicios"])


def pytest_configure(config):
    config.addinivalue_line("markers", "integracion: requiere los CSV (DDJJ_RAW) o SQL Server")
