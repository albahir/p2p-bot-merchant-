"""Auditoría de eventos de seguridad con encadenamiento de hash SHA-256 (append-only).
Cumple con la Constitución: no registra secretos, garantiza trazabilidad total.
"""

import hashlib
import logging
from datetime import UTC, datetime

from src.data.database import SessionLocal
from src.data.models import SecurityEvent
from src.data.repositories import SecurityRepository

logger = logging.getLogger("security_audit")


class AuditLogger:
    """Registrador de auditoría inmutable en base de datos."""

    def __init__(self, db_session_factory=SessionLocal):
        self.session_factory = db_session_factory

    def log(
        self,
        event_type: str,
        key_identifier: str,
        ip_address: str,
        status: str,
        details: str | None = None
    ) -> SecurityEvent:
        """Registra un evento de seguridad calculando el hash encadenado SHA-256."""
        now = datetime.now(UTC)
        db = self.session_factory()
        try:
            repo = SecurityRepository(db)
            last_event = repo.get_last_event()
            prev_hash = last_event.event_hash if last_event else "GENESIS_HASH"

            # Construir payload para calcular hash SHA-256
            raw_payload = f"{prev_hash}|{now.isoformat()}|{event_type}|{key_identifier}|{ip_address}|{status}"
            event_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

            event = SecurityEvent(
                timestamp=now,
                event_type=event_type,
                key_identifier=key_identifier,
                ip_address=ip_address,
                status=status,
                prev_hash=prev_hash,
                event_hash=event_hash
            )
            saved_event = repo.log_event(event)
            logger.info(
                f"AUDIT: event={event_type} key={key_identifier} ip={ip_address} status={status} hash={event_hash[:8]}..."
            )
            return saved_event
        finally:
            db.close()
