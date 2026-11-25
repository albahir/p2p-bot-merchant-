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
    user_id = Column(Integer, index=True, nullable=True)  # Propietario confidencial de la orden
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
    user_id = Column(Integer, index=True, nullable=True)  # Propietario confidencial del movimiento
    movement_type = Column(String(20), nullable=False)  # DEPOSIT, WITHDRAWAL
    asset = Column(String(20), nullable=False)          # USDT, BTC, ETH
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0, nullable=False)
    network = Column(String(30), nullable=True)         # TRC20, BSC, MATIC
    txid = Column(String(128), unique=True, index=True, nullable=True)
    address = Column(String(128), nullable=True)
    note = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False)         # Success, Completed
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class BankVoucher(Base):
    """Comprobantes de pago en bolívares (Pago Móvil / Transferencias) extraídos por OCR o registrados."""
    __tablename__ = "bank_vouchers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True)  # Propietario confidencial del comprobante
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
    user_id = Column(Integer, index=True, nullable=True)  # Propietario confidencial del cierre
    period = Column(String(32), index=True, nullable=False)  # YYYY-MM
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


class AccountingPeriodBalance(Base):
    """Saldos iniciales (apertura) y arqueo final real por período mensual (YYYY-MM) y usuario."""
    __tablename__ = "accounting_period_balances"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True)
    period = Column(String(16), index=True, nullable=False)  # YYYY-MM
    cutoff_start_date = Column(Date, nullable=True)  # Fecha opcional de inicio de operaciones dentro del mes
    initial_usdt = Column(Float, default=0.0, nullable=False)
    initial_usdt_cost_ves = Column(Float, default=0.0, nullable=False)
    initial_banks_json = Column(Text, nullable=True)  # {"Banesco": 50000.0, ...}
    actual_final_usdt = Column(Float, nullable=True)
    actual_final_banks_json = Column(Text, nullable=True)  # {"Banesco": 62000.0, ...}
    is_closed = Column(Boolean, default=False, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    @property
    def initial_banks(self) -> dict[str, float]:
        import json

        if not self.initial_banks_json:
            return {}
        try:
            raw = json.loads(str(self.initial_banks_json))
            if isinstance(raw, dict):
                return {str(k): round(max(0.0, float(v or 0.0)), 2) for k, v in raw.items() if str(k).strip()}
        except (ValueError, TypeError):
            pass
        return {}

    @property
    def actual_final_banks(self) -> dict[str, float] | None:
        import json

        if not self.actual_final_banks_json:
            return None
        try:
            raw = json.loads(str(self.actual_final_banks_json))
            if isinstance(raw, dict):
                return {str(k): round(max(0.0, float(v or 0.0)), 2) for k, v in raw.items() if str(k).strip()}
        except (ValueError, TypeError):
            pass
        return None


class User(Base):
    """Usuario del sistema con control de acceso basado en roles (RBAC)."""
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=True)  # Nombre completo o razón comercial del operador
    tax_id = Column(String(30), nullable=True)  # Cédula de Identidad o RIF venezolano (V-/E-/J-/G-/P-)
    email = Column(String(150), unique=True, index=True, nullable=True)  # Correo de recuperación y contacto
    email_verified = Column(Boolean, default=False, nullable=False)  # Correo verificado mediante OTP SMTP
    telegram_id = Column(String(50), unique=True, index=True, nullable=True)
    role = Column(String(20), default="INVITADO", nullable=False)  # ADMIN, TRADER, INVITADO
    google_sheet_id = Column(String(100), nullable=True)  # ID de la hoja personal en Google Sheets
    google_refresh_token_enc = Column(Text, nullable=True)  # Refresh Token OAuth2 cifrado con AES-256-GCM
    google_auth_type = Column(String(30), default="SERVICE_ACCOUNT", nullable=False)  # SERVICE_ACCOUNT | OAUTH2
    preferred_banks_json = Column(Text, nullable=True)  # Lista JSON de bancos con los que opera el usuario
    bank_balances_json = Column(Text, nullable=True)  # Mapa JSON {banco: saldo_inicial_ves} del operador
    security_question = Column(String(200), nullable=True)  # Pregunta secreta de recuperación de perfil
    security_answer_hash = Column(String(255), nullable=True)  # Hash PBKDF2-HMAC-SHA256 de la respuesta secreta
    recovery_key_hash = Column(String(255), nullable=True)  # Hash PBKDF2 de Llave Maestra de respaldo (single-use)
    failed_recovery_attempts = Column(Integer, default=0, nullable=False)  # Contador anti-fuerza bruta
    recovery_locked_until = Column(DateTime, nullable=True)  # Bloqueo temporal tras 5 intentos fallidos
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    @property
    def has_security_question(self) -> bool:
        return bool(self.security_question and self.security_answer_hash)

    @property
    def has_recovery_key(self) -> bool:
        return bool(self.recovery_key_hash)

    @property
    def preferred_banks(self) -> list[str]:
        import json

        raw = str(self.preferred_banks_json or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(b).strip() for b in parsed if str(b).strip()]
        except (ValueError, TypeError):
            pass
        return []

    @property
    def bank_initial_balances(self) -> dict[str, float]:
        import json

        raw = str(self.bank_balances_json or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                out: dict[str, float] = {}
                for k, v in parsed.items():
                    key_str = str(k).strip()
                    if not key_str:
                        continue
                    try:
                        out[key_str] = round(float(v), 2)
                    except (ValueError, TypeError):
                        continue
                return out
        except (ValueError, TypeError):
            pass
        return {}


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
    user_id = Column(Integer, index=True, nullable=True)  # Propietario confidencial del asiento
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


class SystemState(Base):
    """Estado operativo ligero compartido entre el motor 24/7, el Bot de Telegram y la API Web."""
    __tablename__ = "system_state"

    key = Column(String(64), primary_key=True, index=True, nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class MarketSnapshot(Base):
    """Instantánea periódica de microestructura Binance P2P y brecha BCV (SPEC-025)."""
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True, nullable=False)
    bcv_rate = Column(Float, default=0.0, nullable=False)
    p2p_buy_best = Column(Float, default=0.0, nullable=False)
    p2p_buy_avg20 = Column(Float, default=0.0, nullable=False)
    p2p_sell_best = Column(Float, default=0.0, nullable=False)
    p2p_sell_avg20 = Column(Float, default=0.0, nullable=False)
    p2p_mid = Column(Float, default=0.0, nullable=False)
    brecha_pct = Column(Float, default=0.0, nullable=False)
    spread_ves = Column(Float, default=0.0, nullable=False)
    vol_buy_usdt = Column(Float, default=0.0, nullable=False)
    vol_sell_usdt = Column(Float, default=0.0, nullable=False)
    depth_json = Column(Text, nullable=True)  # Tramos Top 5/10/20 + top1 + matriz por banco/ticket


class MarketHourlyRollup(Base):
    """Consolidado OHLC horario jerárquico para velas de 1h, 4h, 1D y banda probabilística (SPEC-025)."""
    __tablename__ = "market_hourly_rollups"

    hora_utc = Column(DateTime, primary_key=True, index=True, nullable=False)
    buy_open = Column(Float, nullable=False)
    buy_high = Column(Float, nullable=False)
    buy_low = Column(Float, nullable=False)
    buy_close = Column(Float, nullable=False)
    sell_open = Column(Float, nullable=False)
    sell_high = Column(Float, nullable=False)
    sell_low = Column(Float, nullable=False)
    sell_close = Column(Float, nullable=False)
    bcv_close = Column(Float, default=0.0, nullable=False)
    brecha_close = Column(Float, default=0.0, nullable=False)
    vol_buy_sum = Column(Float, default=0.0, nullable=False)
    vol_sell_sum = Column(Float, default=0.0, nullable=False)
    samples_count = Column(Integer, default=1, nullable=False)
    bank_matrix_json = Column(Text, nullable=True)  # Por banco: o, p, pc (sostenido), x, u, d




