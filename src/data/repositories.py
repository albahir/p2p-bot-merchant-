"""Repositorios de datos siguiendo el patrón Repository para acceso seguro y desacoplado."""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from src.data.models import Order, SecurityEvent, EncryptedSecret


class OrderRepository:
    """Acceso a datos de órdenes para ingesta, motor fiscal y dashboard."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_order_number(self, order_number: str) -> Optional[Order]:
        return self.db.query(Order).filter(Order.order_number == order_number).first()

    def create(self, order: Order) -> Order:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def list_completed(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Order]:
        query = self.db.query(Order).filter(Order.order_status == "COMPLETED")
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        return query.order_by(Order.created_at.asc()).all()


class SecurityRepository:
    """Acceso a eventos de auditoría y almacenamiento de secretos."""

    def __init__(self, db: Session):
        self.db = db

    def get_last_event(self) -> Optional[SecurityEvent]:
        return self.db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).first()

    def log_event(self, event: SecurityEvent) -> SecurityEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_secret(self, key_name: str) -> Optional[EncryptedSecret]:
        return self.db.query(EncryptedSecret).filter(EncryptedSecret.key_name == key_name).first()

    def upsert_secret(self, key_name: str, nonce: str, ciphertext: str, tag: str) -> EncryptedSecret:
        secret = self.get_secret(key_name)
        if not secret:
            secret = EncryptedSecret(
                key_name=key_name,
                nonce=nonce,
                ciphertext=ciphertext,
                tag=tag
            )
            self.db.add(secret)
        else:
            secret.nonce = nonce
            secret.ciphertext = ciphertext
            secret.tag = tag
        self.db.commit()
        self.db.refresh(secret)
        return secret
