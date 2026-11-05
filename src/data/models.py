"""Modelos de datos SQLAlchemy para p2p-bot-merchant.
Incluye modelos para eventos de seguridad (auditoría append-only), secretos cifrados y órdenes de Binance.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text

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
    counterparty_name = Column(String(100), nullable=True)  # Nombre o apodo de la contraparte en Binance
    created_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)  # Momento exacto de finalización/liberación
    payment_method = Column(String(50), nullable=True)  # Método o banco reportado por Binance (ej. Banesco, Pago Móvil)



class IdentityCache(Base):
    """Caché persistente de identidades consultadas (Cédula -> Nombre oficial)."""
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nationality = Column(String(2), nullable=False)  # V o E
    cedula = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    source = Column(String(50), nullable=False)  # SENIAT, CNE, MANUAL
    queried_by = Column(String(50), nullable=True)  # Username o Telegram ID que originó la consulta
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class WalletMovement(Base):
    """Movimientos de entrada y salida on-chain de criptoactivos (Depósitos y Retiros)."""
    __tablename__ = "wallet_movements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    movement_type = Column(String(20), nullable=False)  # DEPOSIT, WITHDRAWAL
    asset = Column(String(20), nullable=False)          # USDT, BTC, ETH
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0, nullable=False)
    network = Column(String(30), nullable=True)         # TRC20, BSC, MATIC
    txid = Column(String(128), unique=True, index=True, nullable=True)
    address = Column(String(128), nullable=True)
    status = Column(String(30), nullable=False)         # Success, Completed
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class BankVoucher(Base):
    """Comprobantes de pago en bolívares (Pago Móvil / Transferencias) extraídos por OCR o registrados."""
    __tablename__ = "bank_vouchers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bank_name = Column(String(100), nullable=False)     # Banco de Venezuela, Banesco, etc.
    destination_bank = Column(String(100), nullable=True) # Banco receptor del pago
    reference_number = Column(String(50), index=True, nullable=False)
    amount_ves = Column(Float, nullable=False)          # Monto neto transferido
    bank_fee_ves = Column(Float, default=0.0, nullable=False) # Comisión bancaria cobrada
    total_debited_ves = Column(Float, default=0.0, nullable=False) # Total debitado de la cuenta (monto + comisión)
    sender_id = Column(String(20), nullable=True)       # Cédula V-12345678 o S/C
    sender_name = Column(String(255), nullable=True)
    sender_phone = Column(String(30), nullable=True)    # Teléfono del emisor/receptor
    concept = Column(String(255), nullable=True)        # Motivo o concepto del comprobante
    payment_method = Column(String(30), default="PAGO_MOVIL", nullable=False) # PAGO_MOVIL, TRANSFERENCIA
    movement_type = Column(String(20), default="DEBIT", nullable=False)       # DEBIT (compra), CREDIT (venta)
    associated_order_number = Column(String(50), nullable=True, index=True)
    verification_status = Column(String(30), default="UNMATCHED", nullable=False)  # MATCHED, UNMATCHED, PENDING
    reconciliation_score = Column(Float, default=0.0, nullable=False)          # Score de 0.0 a 100.0%
    voucher_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class FiscalPeriodSnapshot(Base):
    """Snapshots mensuales de balance e inventario para la reconciliación de 6 piezas."""
    __tablename__ = "fiscal_period_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    period = Column(String(7), unique=True, index=True, nullable=False)  # YYYY-MM
    initial_balance = Column(Float, default=0.0, nullable=False)
    inflows_deposits = Column(Float, default=0.0, nullable=False)
    inflows_p2p_buys = Column(Float, default=0.0, nullable=False)
    outflows_withdrawals = Column(Float, default=0.0, nullable=False)
    outflows_p2p_sells = Column(Float, default=0.0, nullable=False)
    volume_operated = Column(Float, default=0.0, nullable=False)
    total_fees = Column(Float, default=0.0, nullable=False)
    calculated_final_balance = Column(Float, nullable=False)
    actual_final_balance = Column(Float, nullable=False)
    discrepancy = Column(Float, default=0.0, nullable=False)
    gross_revenue_ves = Column(Float, default=0.0, nullable=False)
    acquisition_cost_ves = Column(Float, default=0.0, nullable=False)
    net_profit_ves = Column(Float, default=0.0, nullable=False)
    net_profit_usd = Column(Float, default=0.0, nullable=False)
    status = Column(String(30), default="BALANCED", nullable=False)  # BALANCED, DISCREPANCY
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class User(Base):
    """Usuario del sistema con control de acceso basado en roles (RBAC)."""
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    telegram_id = Column(String(50), unique=True, index=True, nullable=True)
    role = Column(String(20), default="INVITADO", nullable=False)  # ADMIN, TRADER, INVITADO
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class BCVRateHistory(Base):
    """Histórico de tasas oficiales publicadas por el BCV indexadas por Fecha Valor."""
    __tablename__ = "bcv_rates_history"

    fecha_valor = Column(Date, primary_key=True, index=True, nullable=False)
    usd_rate = Column(Float, nullable=False)
    eur_rate = Column(Float, default=0.0, nullable=False)
    source = Column(String(50), default="BCV_OFFICIAL", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class JournalEntry(Base):
    """Asiento contable del Libro Diario con partida doble inmutable y hash encadenado SHA-256."""
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entry_number = Column(Integer, index=True, nullable=False)
    date_time = Column(DateTime, index=True, nullable=False)
    account_code = Column(String(30), nullable=False)   # 1.1.01, 1.1.05, 5.2.01, etc.
    account_name = Column(String(100), nullable=False)
    debit = Column(Float, default=0.0, nullable=False)
    credit = Column(Float, default=0.0, nullable=False)
    reference = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    voucher_id = Column(Integer, nullable=True)
    order_number = Column(String(50), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), nullable=False)




