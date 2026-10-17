"""Modelos de datos SQLAlchemy para p2p-bot-merchant.
Incluye modelos para eventos de seguridad (auditoría append-only), secretos cifrados y órdenes de Binance.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from src.data.database import Base


class SecurityEvent(Base):
    """Tabla append-only para auditoría de eventos de seguridad con hash SHA-256."""
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    event_type = Column(String(50), nullable=False)  # READ, WRITE, ROTATE, IP_CHECK, FAILED_ACCESS
    key_identifier = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False)
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED
    prev_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)


class EncryptedSecret(Base):
    """Almacén de secretos cifrados en reposo con AES-256-GCM."""
    __tablename__ = "encrypted_secrets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key_name = Column(String(100), unique=True, index=True, nullable=False)
    nonce = Column(String(64), nullable=False)
    ciphertext = Column(Text, nullable=False)
    tag = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )


class Order(Base):
    """Histórico de órdenes de Binance P2P con campos para motor fiscal."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    trade_type = Column(String(10), nullable=False)  # BUY, SELL
    asset = Column(String(20), nullable=False)        # USDT, BTC
    fiat = Column(String(10), nullable=False)         # VES, USD
    fiat_amount = Column(Float, nullable=False)
    crypto_amount = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    fee_fiat = Column(Float, default=0.0, nullable=False)
    fee_crypto = Column(Float, default=0.0, nullable=False)
    bcv_rate = Column(Float, default=0.0, nullable=False)
    order_status = Column(String(30), nullable=False)  # COMPLETED, CANCELLED
    created_at = Column(DateTime, nullable=False)


class IdentityCache(Base):
    """Caché persistente de identidades consultadas (Cédula -> Nombre oficial)."""
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nationality = Column(String(2), nullable=False)  # V o E
    cedula = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    source = Column(String(50), nullable=False)  # SENIAT, CNE, MANUAL
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

