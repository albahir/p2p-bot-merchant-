"""Validación de permisos y verificación de IP en startup.
Comportamiento Fail-closed: si la IP no coincide con la lista blanca, el sistema aborta.
"""

import logging
from typing import List
from config.settings import Settings
from src.security.audit_logger import AuditLogger

logger = logging.getLogger("permissions")


class StartupPermissionValidator:
    """Validador de entorno y seguridad previa a la ejecución de órdenes."""

    def __init__(self, settings: Settings, audit_logger: AuditLogger):
        self.settings = settings
        self.audit = audit_logger

    def verify_ip_whitelist(self, current_ip: str) -> bool:
        """Verifica que la IP del servidor se encuentre en la lista blanca permitida.
        
        Fail-closed: si la IP no está autorizada, levanta PermissionError e impide el arranque.
        """
        whitelist: List[str] = self.settings.ip_whitelist

        # Si 0.0.0.0 está en whitelist, se permite en entorno dev
        if "0.0.0.0" in whitelist or current_ip in whitelist:
            self.audit.log(
                event_type="IP_CHECK",
                key_identifier="SERVER_HOST",
                ip_address=current_ip,
                status="SUCCESS"
            )
            logger.info(f"IP {current_ip} validada contra la whitelist con éxito.")
            return True

        self.audit.log(
            event_type="IP_CHECK",
            key_identifier="SERVER_HOST",
            ip_address=current_ip,
            status="FAILED"
        )
        raise PermissionError(
            f"FAIL-CLOSED: La IP del servidor '{current_ip}' no está en la whitelist autorizada: {whitelist}."
        )
