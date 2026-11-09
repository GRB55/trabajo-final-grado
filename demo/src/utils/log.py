"""Logging a consola y a archivo, y registro de conteos por paso."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import date

from src.utils.config import carpeta


def get_logger(cfg: dict | None = None, nombre: str = "ddjj") -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(module)s | %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if cfg:
        fh = logging.FileHandler(carpeta(cfg, "logs") / f"pipeline_{date.today():%Y%m%d}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


@contextmanager
def paso(logger: logging.Logger, nombre: str, ejercicio: int | None = None):
    etiqueta = f"{nombre}" + (f" [{ejercicio}]" if ejercicio else "")
    t0 = time.time()
    logger.info("INICIO %s", etiqueta)
    try:
        yield
    except Exception:
        logger.exception("ERROR %s", etiqueta)
        raise
    logger.info("OK %s (%.1f s)", etiqueta, time.time() - t0)


def registrar_conteos(logger, paso_nombre: str, ejercicio, leidos, cargados, rechazados=0) -> None:
    logger.info("CONTEOS | paso=%s | ejercicio=%s | leidos=%s | cargados=%s | rechazados=%s",
                paso_nombre, ejercicio, leidos, cargados, rechazados)
