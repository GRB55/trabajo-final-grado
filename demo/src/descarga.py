"""Descarga de los 10 CSV de declaraciones juradas y manifiesto con SHA-256."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import zipfile
from datetime import datetime

import pandas as pd
import requests

from src.utils.config import cargar_config, carpeta, ruta_csv
from src.utils.log import get_logger, paso


def sha256(ruta) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _bajar(url: str, destino, logger, etiqueta: str) -> None:
    for intento in range(1, 4):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for bloque in r.iter_content(1 << 20):
                        f.write(bloque)
            return
        except requests.RequestException as e:
            logger.warning("Intento %s/3 fallido para %s: %s", intento, etiqueta, e)
            if intento == 3:
                raise
            time.sleep(2 * intento)


def extraer_zip(cfg: dict, ruta_zip, logger) -> list[int]:
    """Extrae del ZIP un CSV por ejercicio y lo deja como declaraciones-juradas-<año>.csv.

    Acepta dos formas: un CSV por año (el año figura en el nombre) o un único CSV con
    todos los años, que se reparte por la columna 'anio'. Los años fuera de
    proyecto.ejercicios (por ejemplo 2012-2014) se ignoran.
    """
    fu = cfg["fuente"]
    anios = cfg["proyecto"]["ejercicios"]
    with zipfile.ZipFile(ruta_zip) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv") and not n.endswith("/")]
        logger.info("El ZIP contiene %s CSV: %s", len(csvs), ", ".join(csvs))
        por_anio = {}
        for a in anios:
            cand = [n for n in csvs if re.search(rf"(?<!\d){a}(?!\d)", n.rsplit("/", 1)[-1])]
            if len(cand) == 1:
                por_anio[a] = cand[0]
        if len(por_anio) == len(anios):
            for a, n in por_anio.items():
                with z.open(n) as o, open(ruta_csv(cfg, a), "wb") as f:
                    for bloque in iter(lambda: o.read(1 << 20), b""):
                        f.write(bloque)
            return list(por_anio)
        if len(csvs) == 1:                      # un único CSV con todos los ejercicios
            escritos = set()
            with z.open(csvs[0]) as o:
                for trozo in pd.read_csv(o, sep=fu["separador"], encoding=fu["codificacion"],
                                         dtype=str, chunksize=100_000):
                    for a, g in trozo.groupby("anio"):
                        if int(a) not in anios:
                            continue
                        destino = ruta_csv(cfg, int(a))
                        nuevo = int(a) not in escritos
                        g.to_csv(destino, sep=fu["separador"], index=False, mode="w" if nuevo else "a",
                                 header=nuevo, encoding=fu["codificacion"] if nuevo else "utf-8")
                        escritos.add(int(a))
            return sorted(escritos)
    raise RuntimeError("No se pudo asignar un CSV a cada ejercicio. Archivos del ZIP: " + ", ".join(csvs)
                       + ". Renombrarlos a declaraciones-juradas-<año>.csv dentro de data/raw.")


def preparar_desde_zip(cfg: dict, forzar: bool, logger) -> None:
    """Si fuente.zip_url está completa, baja el ZIP y extrae los CSV que falten."""
    url = cfg["fuente"].get("zip_url") or ""
    if not url:
        return
    faltan = [a for a in cfg["proyecto"]["ejercicios"] if forzar or not ruta_csv(cfg, a).exists()]
    if not faltan:
        return
    ruta_zip = carpeta(cfg, "raw") / "_fuente.zip"
    if ruta_zip.exists() and not zipfile.is_zipfile(ruta_zip):
        logger.warning("%s no es un ZIP válido; se descarga de nuevo.", ruta_zip.name)
        ruta_zip.unlink()
    if forzar or not ruta_zip.exists():
        _bajar(url, ruta_zip, logger, "ZIP completo")
    if not zipfile.is_zipfile(ruta_zip):
        inicio = ruta_zip.read_bytes()[:200]
        ruta_zip.unlink()
        raise RuntimeError("La URL no devolvió un ZIP (empieza con %r). Copiar el enlace con clic derecho en "
                           "'Descargar' del recurso, o bajar el ZIP desde el navegador y descomprimirlo en data/raw." % inicio)
    extraer_zip(cfg, ruta_zip, logger)


def descargar(cfg: dict, anio: int, forzar: bool, logger) -> dict:
    destino = ruta_csv(cfg, anio)
    if destino.exists() and not forzar:
        logger.info("Ya existe %s (se omite; usar --forzar para descargar de nuevo)", destino.name)
    else:
        url = cfg["fuente"]["urls"].get(anio) or ""
        if not url:
            raise RuntimeError(f"Falta el CSV del ejercicio {anio}: completar fuente.zip_url (o fuente.urls) en config.yaml.")
        _bajar(url, destino, logger, str(anio))
    if destino.stat().st_size == 0:
        raise RuntimeError(f"El archivo {destino.name} está vacío.")
    fu = cfg["fuente"]
    cols = pd.read_csv(destino, sep=fu["separador"], nrows=0, encoding=fu["codificacion"]).columns
    if len(cols) != fu["columnas_esperadas"]:
        raise RuntimeError(f"{destino.name}: {len(cols)} columnas (se esperaban {fu['columnas_esperadas']}).")
    return {"archivo": destino.name, "bytes": destino.stat().st_size, "sha256": sha256(destino),
            "fecha": datetime.now().isoformat(timespec="seconds")}


def main(cfg: dict | None = None, forzar: bool = False) -> None:
    cfg = cfg or cargar_config()
    logger = get_logger(cfg)
    manifiesto = {}
    preparar_desde_zip(cfg, forzar, logger)
    for anio in cfg["proyecto"]["ejercicios"]:
        with paso(logger, "descarga", anio):
            manifiesto[str(anio)] = descargar(cfg, anio, forzar, logger)
    destino = carpeta(cfg, "raw") / "MANIFEST.json"
    destino.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Manifiesto escrito en %s", destino)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    main(forzar=ap.parse_args().forzar)