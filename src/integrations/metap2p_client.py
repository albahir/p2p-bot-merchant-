"""Cliente para la API de MetaP2P (https://api.metap2p.io/api).
Permite autenticación y consulta de cédulas de identidad venezolanas.
"""

import logging
import os
import re
from typing import Any

import httpx

from src.security.identity_service import IdentityInfo

logger = logging.getLogger("metap2p_client")


class MetaP2PClient:
    """Cliente oficial para la API REST de MetaP2P con auto-renovación de Bearer Token."""

    BASE_URL = "https://api.metap2p.io/api"

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        key_manager: Any = None,
        timeout: float = 10.0
    ):
        self._key_manager = key_manager
        self.email = email or os.getenv("METAP2P_EMAIL", "")
        self.password = password or os.getenv("METAP2P_PASSWORD", "")
        self.timeout = timeout
        self._access_token: str | None = None
        self._http = httpx.Client(timeout=timeout)

        # Cargar credenciales desde ApiKeyManager (AES-256-GCM) si están configuradas
        if self._key_manager and (not self.email or not self.password):
            self._load_credentials_from_vault()

    def _load_credentials_from_vault(self) -> None:
        """Carga de forma segura credenciales de MetaP2P desde el almacén de secretos."""
        if not self._key_manager:
            return
        try:
            stored_email = self._key_manager.get_secret("metap2p_email")
            stored_pwd = self._key_manager.get_secret("metap2p_password")
            if stored_email:
                self.email = stored_email
            if stored_pwd:
                self.password = stored_pwd
        except (KeyError, ValueError) as e:
            logger.debug(f"No se pudieron cargar credenciales de MetaP2P del vault: {e}")

    def is_configured(self) -> bool:
        """Indica si las credenciales de MetaP2P están disponibles."""
        return bool(self.email and self.email.strip() and self.password and self.password.strip())

    def login(self) -> bool:
        """Inicia sesión en MetaP2P y obtiene el access_token."""
        if not self.is_configured() or not self.email or not self.password:
            logger.warning("METAP2P: Credenciales no configuradas (email o password ausentes).")
            return False

        url = f"{self.BASE_URL}/login"
        payload = {
            "email": self.email.strip(),
            "password": self.password.strip()
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "es"
        }

        try:
            res = self._http.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                self._access_token = data.get("access_token")
                logger.info("METAP2P: Autenticación exitosa. Token obtenido.")
                return True
            else:
                logger.error(f"METAP2P: Fallo de login (HTTP {res.status_code}): {res.text}")
                return False
        except (httpx.RequestError, ValueError, KeyError) as e:
            logger.error(f"METAP2P: Error de conexión durante login: {e}")
            return False

    def search_dni(self, dni: str) -> IdentityInfo:
        """Consulta una cédula en la API de MetaP2P."""
        # Limpiar caracteres no numéricos o prefijos (ej. V-18234567 -> 18234567)
        clean_num = re.sub(r"[^\d]", "", str(dni)).strip()
        if not clean_num:
            return IdentityInfo(
                nationality="V",
                cedula=str(dni),
                full_name="",
                is_valid=False,
                error_message="Formato de cédula inválido",
                source="METAP2P"
            )

        # Autenticar si no hay token
        if not self._access_token and not self.login():
            return IdentityInfo(
                nationality="V",
                cedula=clean_num,
                full_name="",
                is_valid=False,
                error_message="Fallo de autenticación con MetaP2P",
                source="METAP2P"
            )

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "es"
        }
        url = f"{self.BASE_URL}/dni/search?dni={clean_num}"

        try:
            res = self._http.get(url, headers=headers)

            # Si el token expiró (401), reintentar login una vez
            if res.status_code == 401:
                logger.info("METAP2P: Token expirado (401). Renovando sesión...")
                if self.login():
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    res = self._http.get(url, headers=headers)
                else:
                    return IdentityInfo(
                        nationality="V",
                        cedula=clean_num,
                        full_name="",
                        is_valid=False,
                        error_message="No se pudo renovar la sesión en MetaP2P",
                        source="METAP2P"
                    )

            if res.status_code == 200:
                data = res.json()
                full_name = str(data.get("full_name", "")).strip().upper()
                prefix = str(data.get("dni_prefix", "V")).upper()
                dni_num = str(data.get("dni_number", clean_num)).strip()
                if full_name:
                    return IdentityInfo(
                        nationality=prefix,
                        cedula=dni_num,
                        full_name=full_name,
                        is_valid=True,
                        source="METAP2P"
                    )

            if res.status_code == 400:
                err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                err_code = err_data.get("error", "")
                if err_code == "RECORD_NOT_FOUND":
                    return IdentityInfo(
                        nationality="V",
                        cedula=clean_num,
                        full_name="",
                        is_valid=False,
                        error_message="Cédula no encontrada en los registros de MetaP2P",
                        source="METAP2P"
                    )

            return IdentityInfo(
                nationality="V",
                cedula=clean_num,
                full_name="",
                is_valid=False,
                error_message=f"Error en consulta MetaP2P (HTTP {res.status_code})",
                source="METAP2P"
            )

        except (httpx.RequestError, ValueError, KeyError, OSError) as e:
            logger.warning(f"METAP2P: Error de red consultando cédula {clean_num}: {e}")
            return IdentityInfo(
                nationality="V",
                cedula=clean_num,
                full_name="",
                is_valid=False,
                error_message=f"Excepción de red MetaP2P: {e}",
                source="METAP2P"
            )

    def close(self) -> None:
        """Cierra el cliente HTTP."""
        self._http.close()
