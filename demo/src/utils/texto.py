"""Funciones puras de normalización de texto."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")


def _vacio(s) -> bool:
    return s is None or (isinstance(s, float) and s != s) or str(s).strip() == ""


def normalizar_nombre(s) -> str | None:
    """Espacios colapsados y mayúsculas; conserva los acentos."""
    if _vacio(s):
        return None
    return _ESPACIOS.sub(" ", str(s).strip()).upper()


def normalizar_texto(s) -> str | None:
    """Espacios colapsados, mayúsculas y sin acentos (para cargo)."""
    base = normalizar_nombre(s)
    if base is None:
        return None
    nfkd = unicodedata.normalize("NFKD", base)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_sector(s) -> str:
    v = normalizar_texto(s)
    return v if v in ("PUBLICO", "PRIVADO") else "SIN DATO"


def normalizar_tipo(s, validos=("Anual", "Inicial", "Baja")) -> str:
    v = normalizar_texto(s)
    for t in validos:
        if v == normalizar_texto(t):
            return t
    return "SIN DATO"


def pseudonimo(cuit, sal: str) -> str:
    """Identificador 'F-XXXXXXXXXX' (igual al de las vistas SQL de demostración)."""
    h = hashlib.sha256((sal + str(int(cuit))).encode("ascii")).hexdigest().upper()
    return "F-" + h[:10]
