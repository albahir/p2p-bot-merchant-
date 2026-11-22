"""Validación de permisos, detección de IP pública y verificación en startup.
Comportamiento Fail-closed: si la IP no coincide con la lista blanca, el sistema aborta.
"""

from __future__ import annotations

import ipaddress
import logging

import httpx

from config.settings import Settings
from src.security.audit_logger import AuditLogger

logger = logging.getLogger("permissions")

PUBLIC_IP_PROVIDERS: tuple[str, ...] = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://checkip.amazonaws.com",
)


def detect_public_ip(timeout: float = 4.0) -> str | None:
    """Detecta la IP pública saliente del servidor consultando proveedores HTTPS confiables."""
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for url in PUBLIC_IP_PROVIDERS:
            try:
                response = client.get(url)
                response.raise_for_status()
                candidate = response.text.strip()
                ip_obj = ipaddress.ip_address(candidate)
                return str(ip_obj)
            except (httpx.HTTPError, OSError, ValueError) as exc:
                logger.debug("No se pudo obtener IP pública desde %s: %s", url, exc)
    return None


class StartupPermissionValidator:
    """Validador de entorno y seguridad previa a la ejecución de órdenes."""

    def __init__(self, settings: Settings, audit_logger: AuditLogger):
        self.settings = settings
        self.audit = audit_logger

    def verify_ip_whitelist(self, current_ip: str) -> bool:
        """Verifica que la IP del servidor se encuentre en la lista blanca permitida.

        Fail-closed: si la IP no está autorizada, levanta PermissionError e impide el arranque.
        """
        whitelist: list[str] = self.settings.ip_whitelist

        # Si 0.0.0.0 está en whitelist, se permite en entorno dev
        if "0.0.0.0" in whitelist or current_ip in whitelist:
            self.audit.log(
                event_type="IP_CHECK",
                key_identifier="SERVER_HOST",
                ip_address=current_ip,
                status="SUCCESS",
            )
            logger.info(f"IP {current_ip} validada contra la whitelist con éxito.")
            return True

        self.audit.log(
            event_type="IP_CHECK",
            key_identifier="SERVER_HOST",
            ip_address=current_ip,
            status="FAILED",
        )
        raise PermissionError(
            f"FAIL-CLOSED: La IP del servidor '{current_ip}' no está en la whitelist autorizada: {whitelist}."
        )

    def verify_runtime_ip(self) -> tuple[str, str | None]:
        """Detecta la IP pública saliente y valida la whitelist según el entorno activo.

        Retorna `(ip_verificada, ip_publica_detectada)`.
        En `production`, exige detectar la IP pública saliente real y que esté autorizada.
        En `development`/`staging`, permite fallback local `127.0.0.1` reportando igualmente la IP pública.
        """
        whitelist = self.settings.ip_whitelist
        public_ip = detect_public_ip()
        is_prod = self.settings.ENVIRONMENT.strip().lower() == "production"

        if "0.0.0.0" in whitelist:
            target = public_ip or "127.0.0.1"
            self.verify_ip_whitelist(target)
            return target, public_ip

        if is_prod:
            if not public_ip:
                self.audit.log(
                    event_type="IP_CHECK",
                    key_identifier="SERVER_HOST",
                    ip_address="UNKNOWN",
                    status="FAILED",
                )
                raise PermissionError(
                    "FAIL-CLOSED: No se pudo detectar la IP pública saliente del servidor en producción."
                )
            self.verify_ip_whitelist(public_ip)
            return public_ip, public_ip

        if public_ip and public_ip in whitelist:
            self.verify_ip_whitelist(public_ip)
            return public_ip, public_ip

        if "127.0.0.1" in whitelist:
            self.verify_ip_whitelist("127.0.0.1")
            return "127.0.0.1", public_ip

        target = public_ip or "127.0.0.1"
        self.verify_ip_whitelist(target)
        return target, public_ip
