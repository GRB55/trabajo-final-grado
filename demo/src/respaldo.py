"""Respaldos cifrados (AES-256): completo (semanal) y diferencial (diario), con verificación, copia y retención.

Uso:  python -m src.respaldo --tipo completo|diferencial|verificar
Requiere haber ejecutado una vez la configuración de sql/09_respaldo.sql (certificado).
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from src.utils.config import cargar_config, carpeta
from src.utils.log import get_logger, paso


def _ejecutar(conn, sql: str) -> None:
    cur = conn.cursor()
    cur.execute(sql)
    while cur.nextset():
        pass


def respaldar(cfg: dict, tipo: str, logger) -> Path:
    from src.utils import db
    base = cfg["bd"]["base"]
    cert = cfg["respaldo"]["certificado"]
    local = carpeta(cfg, "respaldo_local")
    local.mkdir(parents=True, exist_ok=True)
    archivo = local / f"{base}_{'completo' if tipo == 'completo' else 'dif'}_{datetime.now():%Y%m%d_%H%M}.bak"
    opciones = "DIFFERENTIAL, " if tipo == "diferencial" else ""
    conn = db.conectar(cfg, autocommit=True)       # BACKUP no puede ir dentro de una transacción
    try:
        _ejecutar(conn, f"BACKUP DATABASE [{base}] TO DISK = N'{archivo}' WITH {opciones}INIT, CHECKSUM, COMPRESSION, "
                        f"MAXTRANSFERSIZE = 131072, ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = {cert})")
        _ejecutar(conn, f"RESTORE VERIFYONLY FROM DISK = N'{archivo}' WITH CHECKSUM")
    finally:
        conn.close()
    logger.info("Respaldo %s verificado: %s", tipo, archivo.name)
    for clave in ("respaldo_externo", "respaldo_nube"):
        destino = carpeta(cfg, clave)
        if destino.exists():
            shutil.copy2(archivo, destino / archivo.name)
            logger.info("Copiado a %s", destino)
        else:
            logger.warning("No existe %s: la copia (regla 3-2-1) no se realizó.", destino)
    return archivo


def aplicar_retencion(cfg: dict, logger) -> None:
    reglas = {"completo": cfg["respaldo"]["retener_completos"], "dif": cfg["respaldo"]["retener_diferenciales"]}
    for clave in ("respaldo_local", "respaldo_externo", "respaldo_nube"):
        carpeta_ = carpeta(cfg, clave)
        if not carpeta_.exists():
            continue
        for marca, n in reglas.items():
            archivos = sorted(carpeta_.glob(f"*_{marca}_*.bak"))
            for viejo in archivos[:-n] if len(archivos) > n else []:
                viejo.unlink()
                logger.info("Retención: eliminado %s de %s", viejo.name, carpeta_)


def verificar_ultimo(cfg: dict, logger) -> None:
    from src.utils import db
    archivos = sorted(carpeta(cfg, "respaldo_local").glob("*.bak"))
    if not archivos:
        raise FileNotFoundError("No hay respaldos locales.")
    conn = db.conectar(cfg, autocommit=True)
    try:
        _ejecutar(conn, f"RESTORE VERIFYONLY FROM DISK = N'{archivos[-1]}' WITH CHECKSUM")
    finally:
        conn.close()
    logger.info("Verificación OK: %s", archivos[-1].name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tipo", choices=["completo", "diferencial", "verificar"], required=True)
    a = ap.parse_args()
    cfg = cargar_config()
    log = get_logger(cfg)
    with paso(log, f"respaldo {a.tipo}"):
        if a.tipo == "verificar":
            verificar_ultimo(cfg, log)
        else:
            respaldar(cfg, a.tipo, log)
            aplicar_retencion(cfg, log)
