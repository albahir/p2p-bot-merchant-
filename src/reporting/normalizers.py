"""Módulo de normalización, sanitización y resiliencia de datos bancarios y contables.
Estandariza bancos venezolanos, cédulas, teléfonos, referencias y montos con tolerancia a comas y puntos.
"""

import re
from typing import Any


def normalize_text(text: str | None) -> str:
    """Elimina espacios redundantes, tildes y convierte a mayúsculas para evitar descalces en comparaciones."""
    if not text:
        return ""
    s = str(text).strip().upper()
    replacements = (
        ("Á", "A"),
        ("É", "E"),
        ("Í", "I"),
        ("Ó", "O"),
        ("Ú", "U"),
        ("Ü", "U"),
        ("Ñ", "N"),
    )
    for orig, rep in replacements:
        s = s.replace(orig, rep)
    # Colapsar múltiples espacios contiguos en uno solo
    return re.sub(r"\s+", " ", s).strip()


def normalize_bank_name(raw_name: str | None) -> str:
    """Estandariza nombres de entidades bancarias venezolanas a su forma oficial."""
    t = normalize_text(raw_name)
    if not t:
        return "BANCO DESCONOCIDO"

    if "BANESCO" in t:
        return "BANESCO"
    if "VENEZUELA" in t or "BDV" in t:
        return "BANCO DE VENEZUELA"
    if "MERCANTIL" in t:
        return "MERCANTIL"
    if "PROVINCIAL" in t or "BBVA" in t:
        return "PROVINCIAL"
    if "BANCAMIGA" in t:
        return "BANCAMIGA"
    if "BNC" in t or "NACIONAL DE CREDITO" in t:
        return "BNC"
    if "BANCARIBE" in t:
        return "BANCARIBE"

    return t


def normalize_cedula(raw_cedula: str | None) -> str:
    """Estandariza cédulas y RIFs venezolanos al formato oficial 'LETRA-DIGITOS' (ej. V-19456789)."""
    if not raw_cedula:
        return "S/C"

    s = str(raw_cedula).strip().upper()
    prefix = "V"
    if s.startswith(("J", "E", "G", "P")):
        prefix = s[0]

    digits = re.sub(r"\D", "", s)
    if not digits:
        return "S/C"

    return f"{prefix}-{digits}"


def normalize_phone(raw_phone: str | None) -> str:
    """Estandariza números telefónicos venezolanos al formato '04XX-XXXXXXX'."""
    if not raw_phone:
        return "N/A"

    digits = re.sub(r"\D", "", str(raw_phone))
    if digits.startswith("58") and len(digits) >= 12:
        digits = "0" + digits[2:]
    elif not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits

    if len(digits) == 11 and digits.startswith("04"):
        return f"{digits[:4]}-{digits[4:]}"

    return digits if len(digits) >= 7 else "N/A"


def normalize_reference(raw_ref: str | None) -> str:
    """Extrae la secuencia numérica representativa de una referencia bancaria eliminando etiquetas textuales."""
    if not raw_ref:
        return "S/R"

    s = str(raw_ref).strip()
    digits = re.sub(r"\D", "", s)
    return digits if digits else s


def parse_monetary_amount(raw_val: Any) -> float:
    """Parsea montos monetarios con soporte robusto para formatos venezolanos (1.500,50) e internacionales (1,500.50)."""
    if raw_val is None:
        return 0.0

    if isinstance(raw_val, (int, float)):
        return round(float(raw_val), 2)

    s = str(raw_val).strip().upper()
    # Conservar únicamente dígitos, comas y puntos
    s = re.sub(r"[^0-9,\.]", "", s)
    if not s:
        return 0.0

    # Caso 1: Contiene tanto coma como punto (ej. 1.500,50 vs 1,500.50)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Coma es el separador decimal (ej. 1.500,50 o 1.500.000,00)
            s = s.replace(".", "").replace(",", ".")
        else:
            # Punto es el separador decimal (ej. 1,500.50 o 1,500,000.00)
            s = s.replace(",", "")
    elif "," in s:
        # Solo comas: si hay una sola coma con 1 o 2 decimales, es decimal
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            # Separador de miles
            s = s.replace(",", "")
    elif "." in s:
        # Solo puntos: si hay un solo punto con 1 o 2 decimales, es decimal
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            pass  # Ya es decimal estándar
        else:
            # Separador de miles
            s = s.replace(".", "")

    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0
