"""Carga y validación de la configuración (config.yaml + .env)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

RAIZ = Path(__file__).resolve().parents[2]
CLAVES_OBLIGATORIAS = ["proyecto", "rutas", "fuente", "bd", "limpieza", "modelo", "evaluacion", "revision", "respaldo"]


class ConfigError(Exception):
    """Configuración incompleta o inconsistente."""


def cargar_config(ruta: str | Path | None = None) -> dict:
    if load_dotenv:
        load_dotenv(RAIZ / ".env")
    ruta = Path(ruta) if ruta else RAIZ / "config" / "config.yaml"
    with open(ruta, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    faltan = [k for k in CLAVES_OBLIGATORIAS if k not in cfg]
    if faltan:
        raise ConfigError(f"Faltan secciones en config.yaml: {faltan}")
    if sorted(cfg["proyecto"]["ejercicios"]) != sorted(int(k) for k in cfg["fuente"]["registros_esperados"]):
        raise ConfigError("'ejercicios' no coincide con las claves de 'registros_esperados'.")
    if os.getenv("DDJJ_RAW"):          # permite apuntar a otra carpeta (tests)
        cfg["rutas"]["raw"] = os.environ["DDJJ_RAW"]
    for clave in ("raw", "salidas", "logs"):
        carpeta(cfg, clave).mkdir(parents=True, exist_ok=True)
    return cfg


def carpeta(cfg: dict, clave: str) -> Path:
    p = Path(cfg["rutas"][clave])
    return p if p.is_absolute() else RAIZ / p


def ruta_csv(cfg: dict, anio: int) -> Path:
    return carpeta(cfg, "raw") / cfg["fuente"]["patron_archivo"].format(anio=anio)
