"""Servicio de verificación de identidades por cédula y extracción de métodos de pago.
Cumple estrictamente con las regulaciones de protección de datos y KYC/AML.
Implementa una arquitectura de verificación legítima con proveedores certificados y fallback en cascada:
1. Base de Datos / Caché Local de Contrapartes Verificadas (0 ms)
2. Proveedor KYC Verifik (api.verifik.co)
3. Proveedor KYC Didit (api.didit.me)
4. Servicio XML Oficial SENIAT
5. Consulta Ciudadana Oficial CNE
"""

import logging
import os
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
    """Extrae la nacionalidad (V o E) y el número de cédula desde un texto o estructura de datos bancarios."""
    if isinstance(details, dict):
        for key in ("identification", "idNumber", "cedula", "ci", "account", "memo", "fields"):
            val = details.get(key)
            if val and isinstance(val, (str, dict)):
                extracted = extract_cedula_from_payment_details(val)
                if extracted:
                    return extracted
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
    source: str  # CACHE, VERIFIK, DIDIT, SENIAT, CNE, NONE
    is_valid: bool
    error_message: str | None = None


class IdentityService:
    """Servicio con proveedores autorizados de KYC y fallback en cascada para consulta de identidad."""

    VERIFIK_URL = "https://api.verifik.co/v2/ve/cedula"
    DIDIT_URL = "https://api.didit.me/v1/identity/lookup"
    SENIAT_URL = "http://contribuyente.seniat.gob.ve/getContribuyente/getrif"
    CNE_URL = "http://www.cne.gob.ve/web/registro_electoral/ce.php"

    def __init__(
        self,
        db: Session | None = None,
        http_client: httpx.Client | None = None,
        verifik_api_key: str | None = None,
        didit_api_key: str | None = None,
    ):
        self.db = db
        self.verifik_api_key = verifik_api_key or os.getenv("VERIFIK_API_KEY")
        self.didit_api_key = didit_api_key or os.getenv("DIDIT_API_KEY")
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
        """Método 1: Búsqueda en base de datos local / caché de contrapartes verificadas (0 ms)."""
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
        """Guarda una identidad legítimamente verificada en la caché local."""
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

    def _lookup_verifik(self, nationality: str, cedula: str) -> str | None:
        """Método 2: Verificación mediante proveedor regulado Verifik (verifik.co)."""
        if not self.verifik_api_key:
            return None
        try:
            headers = {"Authorization": f"jwt {self.verifik_api_key}"}
            params = {"documentNumber": cedula, "documentType": nationality.upper()}
            resp = self._client.get(self.VERIFIK_URL, headers=headers, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                data = payload.get("data", {})
                if isinstance(data, dict):
                    if data.get("fullName"):
                        return str(data["fullName"]).strip().upper()
                    fn = data.get("firstName", "")
                    ln = data.get("lastName", "")
                    composed = f"{fn} {ln}".strip().upper()
                    if composed:
                        return composed
        except (httpx.RequestError, ValueError, KeyError) as e:
            logger.warning(f"Error en consulta Verifik KYC para {nationality}-{cedula}: {e}")
        return None

    def _lookup_didit(self, nationality: str, cedula: str) -> str | None:
        """Método 3: Verificación mediante protocolo descentralizado Didit (didit.me)."""
        if not self.didit_api_key:
            return None
        try:
            headers = {"Authorization": f"Bearer {self.didit_api_key}"}
            params = {"id_number": f"{nationality.upper()}{cedula}", "country": "VE"}
            resp = self._client.get(self.DIDIT_URL, headers=headers, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("full_name"):
                    return str(payload["full_name"]).strip().upper()
                data = payload.get("data", {})
                if isinstance(data, dict) and data.get("full_name"):
                    return str(data["full_name"]).strip().upper()
        except (httpx.RequestError, ValueError, KeyError) as e:
            logger.warning(f"Error en consulta Didit KYC para {nationality}-{cedula}: {e}")
        return None

    def _lookup_seniat(self, nationality: str, cedula: str) -> str | None:
        """Método 4: Consulta al endpoint XML oficial del SENIAT."""
        nat = nationality.upper()
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
        """Método 5: Scraping del portal de Registro Electoral del CNE."""
        params = {"nacionalidad": nationality.upper(), "cedula": cedula}
        try:
            resp = self._client.get(self.CNE_URL, params=params)
            if resp.status_code == 200:
                html = resp.text
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

                general_match = re.search(
                    r"(?:Datos del Elector|Nombre Completo)[:\s]*</td>\s*<td[^>]*>([^<]+)</td>",
                    html,
                    re.IGNORECASE,
                )
                if general_match and general_match.group(1).strip():
                    return general_match.group(1).strip().upper()
        except (httpx.RequestError, ValueError, OSError) as e:
            logger.warning(f"Fallo en consulta CNE para {nationality}-{cedula}: {e}")
        return None

    def lookup(self, nationality: str = "V", cedula: str = "") -> IdentityInfo:
        """Ejecuta la consulta con verificación legal y fallback en cascada.
        (Caché Local -> Verifik KYC -> Didit KYC -> SENIAT XML -> CNE Oficial)
        """
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

        # 1. Caché Local en BD de contrapartes legítimas (0 ms)
        from_cache = self.lookup_cache(clean_nat, clean_cedula)
        if from_cache:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} encontrada en caché local de contrapartes.")
            return from_cache

        # 2. Verifik KYC API (Proveedor regulado LATAM)
        name_verifik = self._lookup_verifik(clean_nat, clean_cedula)
        if name_verifik:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} verificada exitosamente vía Verifik KYC.")
            self.save_to_cache(clean_nat, clean_cedula, name_verifik, source="VERIFIK")
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name=name_verifik,
                source="VERIFIK",
                is_valid=True,
            )

        # 3. Didit KYC API (Protocolo descentralizado de identidad)
        name_didit = self._lookup_didit(clean_nat, clean_cedula)
        if name_didit:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} verificada exitosamente vía Didit KYC.")
            self.save_to_cache(clean_nat, clean_cedula, name_didit, source="DIDIT")
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name=name_didit,
                source="DIDIT",
                is_valid=True,
            )

        # 4. SENIAT XML API Oficial
        name_seniat = self._lookup_seniat(clean_nat, clean_cedula)
        if name_seniat:
            logger.info(f"Identidad {clean_nat}-{clean_cedula} resuelta vía portal fiscal SENIAT.")
            self.save_to_cache(clean_nat, clean_cedula, name_seniat, source="SENIAT")
            return IdentityInfo(
                nationality=clean_nat,
                cedula=clean_cedula,
                full_name=name_seniat,
                source="SENIAT",
                is_valid=True,
            )

        # 5. CNE Consulta Ciudadana
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

        # Si todos los métodos fallan
        logger.warning(f"Identidad {clean_nat}-{clean_cedula} no pudo verificarse en ningún proveedor.")
        return IdentityInfo(
            nationality=clean_nat,
            cedula=clean_cedula,
            full_name="",
            source="NONE",
            is_valid=False,
            error_message="No se pudo verificar la identidad a través de Verifik, Didit, SENIAT ni CNE.",
        )
