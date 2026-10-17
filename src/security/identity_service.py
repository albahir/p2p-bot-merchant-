"""Servicio de verificación de identidades por cédula y extracción de métodos de pago.
Implementa una arquitectura de triple método con fallback en cascada:
1. Base de Datos / Caché Local SQLite (0 ms)
2. Servicio XML Oficial SENIAT
3. Scraping del Registro Electoral CNE
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.models import IdentityCache

logger = logging.getLogger("identity_service")

# Expresiones regulares para extracción de cédulas venezolanas
CEDULA_PATTERNS = [
    re.compile(r"(?i)\b([VE])[-.\s]?([0-9]{6,9})\b"),
    re.compile(r"(?i)(?:ci|c\.i|cedula|identificacion)[:\s]*([VE])?[-.\s]?([0-9]{6,9})\b"),
]


def extract_cedula_from_payment_details(details: str | dict[str, Any]) -> tuple[str, str] | None:
    """Extrae la nacionalidad (V o E) y el número de cédula desde un texto o estructura de datos."""
    if isinstance(details, dict):
        # Buscar en campos bancarios comunes
        for key in ("identification", "idNumber", "cedula", "ci", "account", "memo", "fields"):
            val = details.get(key)
            if val and isinstance(val, str) or val and isinstance(val, dict):
                extracted = extract_cedula_from_payment_details(val)
                if extracted:
                    return extracted
        # También buscar en la representación general si no se encontró en campos clave
        return extract_cedula_from_payment_details(str(details))

    text = str(details).strip()
    # Eliminar puntos entre dígitos (ej. 19.876.543 -> 19876543)
    normalized_text = re.sub(r"(?<=\d)\.(?=\d)", "", text)
    for pattern in CEDULA_PATTERNS:
        match = pattern.search(normalized_text)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[0] and groups[1]:
                nat = groups[0].upper()
                clean_num = re.sub(r"\D", "", groups[1])
                if 6 <= len(clean_num) <= 9:
                    return (nat, clean_num)
            elif len(groups) == 2 and groups[1]:
                nat = groups[0].upper() if groups[0] else "V"
                clean_num = re.sub(r"\D", "", groups[1])
                if 6 <= len(clean_num) <= 9:
                    return (nat, clean_num)
            elif len(groups) == 1 and groups[0]:
                clean_num = re.sub(r"\D", "", groups[0])
                if 6 <= len(clean_num) <= 9:
                    return ("V", clean_num)

    return None


@dataclass
class IdentityInfo:
    nationality: str
    cedula: str
    full_name: str
    source: str  # CACHE, SENIAT, CNE, NONE
    is_valid: bool
    error_message: str | None = None


class IdentityService:
    """Servicio con triple fallback en cascada para consulta de nombres a partir de cédula."""

    SENIAT_URL = "http://contribuyente.seniat.gob.ve/getContribuyente/getrif"
    CNE_URL = "http://www.cne.gob.ve/web/registro_electoral/ce.php"

    def __init__(self, db: Session | None = None, http_client: httpx.Client | None = None):
        self.db = db
        self._client = http_client or httpx.Client(
            timeout=8.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )

    def lookup_cache(self, nationality: str, cedula: str) -> IdentityInfo | None:
        """Método 1: Búsqueda en base de datos local / caché (0 ms)."""
        if not self.db:
            return None
        try:
            cached = (
                self.db.query(IdentityCache)
                .filter(IdentityCache.nationality == nationality.upper(), IdentityCache.cedula == cedula)
                .first()
            )
            if cached:
                return IdentityInfo(
                    nationality=str(cached.nationality),
                    cedula=str(cached.cedula),
                    full_name=str(cached.full_name),
                    source="CACHE",
                    is_valid=True,
                )
        except SQLAlchemyError as e:
            logger.warning(f"Error consultando caché de identidades: {e}")
        return None

    def save_to_cache(self, nationality: str, cedula: str, full_name: str, source: str) -> None:
        """Guarda un registro exitoso en la caché local para consultas instantáneas futuras."""
        if not self.db:
            return
        try:
            record = (
                self.db.query(IdentityCache)
                .filter(IdentityCache.nationality == nationality.upper(), IdentityCache.cedula == cedula)
                .first()
            )
            if not record:
                record = IdentityCache(
                    nationality=nationality.upper(),
                    cedula=cedula,
                    full_name=full_name.strip().upper(),
                    source=source,
                )
                self.db.add(record)
            else:
                record.full_name = full_name.strip().upper()  # type: ignore[assignment]
                record.source = source  # type: ignore[assignment]
            self.db.commit()
        except SQLAlchemyError as e:
            logger.warning(f"No se pudo persistir en caché de identidades: {e}")
            self.db.rollback()

    def _lookup_seniat(self, nationality: str, cedula: str) -> str | None:
        """Método 2: Consulta al endpoint XML oficial del SENIAT."""
        nat = nationality.upper()
        # El SENIAT típicamente usa formato V123456780 o el RIF completo
        for check_digit in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ""):
            rif = f"{nat}{cedula}{check_digit}"
            try:
                resp = self._client.get(f"{self.SENIAT_URL}?rif={rif}")
                if resp.status_code == 200 and "<rif:Nombre>" in resp.text:
                    root = ET.fromstring(resp.text)
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1]
                        if tag == "Nombre" and elem.text:
                            return elem.text.strip().upper()
            except (httpx.RequestError, ET.ParseError, ValueError, OSError):
                continue
        return None

    def _lookup_cne(self, nationality: str, cedula: str) -> str | None:
        """Método 3: Scraping del portal de Registro Electoral del CNE."""
        params = {"nacionalidad": nationality.upper(), "cedula": cedula}
        try:
            resp = self._client.get(self.CNE_URL, params=params)
            if resp.status_code == 200:
                html = resp.text
                # Extraer partes de nombres y apellidos mediante expresiones regulares tolerantes
                p_nombre = re.search(r"Primer Nombre:\s*</td>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE)
                s_nombre = re.search(r"Segundo Nombre:\s*</td>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE)
                p_apellido = re.search(r"Primer Apellido:\s*</td>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE)
                s_apellido = re.search(r"Segundo Apellido:\s*</td>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE)

                names: list[str] = []
                if p_nombre and p_nombre.group(1).strip():
                    names.append(p_nombre.group(1).strip())
                if s_nombre and s_nombre.group(1).strip():
                    names.append(s_nombre.group(1).strip())
                if p_apellido and p_apellido.group(1).strip():
                    names.append(p_apellido.group(1).strip())
                if s_apellido and s_apellido.group(1).strip():
                    names.append(s_apellido.group(1).strip())

                if names:
                    return " ".join(names).upper()

                # Fallback alternativo para formatos simplificados de tabla del CNE
                general_match = re.search(r"(?:Datos del Elector|Nombre Completo)[:\s]*</td>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE)
                if general_match and general_match.group(1).strip():
                    return general_match.group(1).strip().upper()
        except (httpx.RequestError, ValueError, OSError) as e:
            logger.warning(f"Fallo en consulta CNE para {nationality}-{cedula}: {e}")
        return None

    def lookup(self, nationality: str = "V", cedula: str = "") -> IdentityInfo:
        """Ejecuta la consulta con triple fallback en cascada (Caché -> SENIAT -> CNE)."""
        clean_nat = nationality.strip().upper() or "V"
        clean_cedula = re.sub(r"\D", "", cedula)

        if not clean_cedula or len(clean_cedula) < 5:
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name="",
                source="NONE",
                is_valid=False,
                error_message="Número de cédula inválido.",
            )

        # 1. Caché Local (0 ms)
        from_cache = self.lookup_cache(clean_nat, clean_cedula)
        if from_cache:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} encontrada en caché local.")
            return from_cache

        # 2. SENIAT XML
        name_seniat = self._lookup_seniat(clean_nat, clean_cedula)
        if name_seniat:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} resuelta vía SENIAT.")
            self.save_to_cache(clean_nat, clean_cedula, name_seniat, source="SENIAT")
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name=name_seniat,
                source="SENIAT",
                is_valid=True,
            )

        # 3. CNE Scraping
        name_cne = self._lookup_cne(clean_nat, clean_cedula)
        if name_cne:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} resuelta vía CNE.")
            self.save_to_cache(clean_nat, clean_cedula, name_cne, source="CNE")
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name=name_cne,
                source="CNE",
                is_valid=True,
            )

        # Si los 3 métodos fallan
        logger.warning(f"Identidad {clean_nat}-{clean_cedula} no pudo resolverse en ninguna fuente.")
        return IdentityInfo(
            nationality=clean_nat,
            cedula=clean_cedula,
            full_name="",
            source="NONE",
            is_valid=False,
            error_message="No se pudo verificar la identidad en SENIAT ni CNE.",
        )
