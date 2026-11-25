import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / "config" / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    pass


def normalize_database_url(raw_url: str) -> str:
    """Normaliza esquemas postgres:// heredados (Render, Neon, Heroku) a postgresql+psycopg2:// para SQLAlchemy 2.0."""
    cleaned = (raw_url or "").strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg2://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql://") :]
    return cleaned or "sqlite:///./p2p_bot.db"


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./p2p_bot.db"))

# Ajuste para SQLite en multithreading y reconexión resiliente para PostgreSQL (Neon Serverless)
_IS_SQLITE = DATABASE_URL.startswith("sqlite")
connect_args: dict[str, Any] = (
    {"check_same_thread": False}
    if _IS_SQLITE
    else {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

engine_kwargs: dict[str, Any] = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if not _IS_SQLITE:
    engine_kwargs["pool_recycle"] = 240
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


def get_db():
    """Generador de sesión con reintento breve ante cold-start o cierre transitorio en Neon."""
    db = SessionLocal()
    try:
        if not _IS_SQLITE:
            for attempt in range(3):
                try:
                    db.connection()
                    break
                except OperationalError:
                    db.close()
                    if attempt == 2:
                        raise
                    time.sleep(0.8 * (attempt + 1))
                    db = SessionLocal()
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea todas las tablas definidas en los modelos si no existen en la base de datos."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import Base as ModelsBase

    ModelsBase.metadata.create_all(bind=engine)

    migrations: dict[str, list[tuple[str, str]]] = {
        "orders": [
            ("user_id", "INTEGER"),
            ("counterparty_name", "VARCHAR(100)"),
            ("completed_at", "TIMESTAMP"),
            ("payment_method", "VARCHAR(50)"),
        ],
        "wallet_movements": [
            ("user_id", "INTEGER"),
            ("note", "VARCHAR(255)"),
        ],
        "accounting_period_balances": [
            ("cutoff_start_date", "DATE"),
        ],
        "app_users": [
            ("full_name", "VARCHAR(120)"),
            ("tax_id", "VARCHAR(30)"),
            ("email", "VARCHAR(150)"),
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("google_sheet_id", "VARCHAR(100)"),
            ("google_refresh_token_enc", "TEXT"),
            ("google_auth_type", "VARCHAR(30) DEFAULT 'SERVICE_ACCOUNT'"),
            ("preferred_banks_json", "TEXT"),
            ("bank_balances_json", "TEXT"),
            ("security_question", "VARCHAR(200)"),
            ("security_answer_hash", "VARCHAR(255)"),
            ("recovery_key_hash", "VARCHAR(255)"),
            ("failed_recovery_attempts", "INTEGER DEFAULT 0"),
            ("recovery_locked_until", "TIMESTAMP"),
        ],
        "bank_vouchers": [
            ("user_id", "INTEGER"),
            ("destination_bank", "VARCHAR(100)"),
            ("bank_fee_ves", "FLOAT DEFAULT 0.0"),
            ("total_debited_ves", "FLOAT DEFAULT 0.0"),
            ("sender_phone", "VARCHAR(30)"),
            ("concept", "VARCHAR(255)"),
            ("movement_type", "VARCHAR(20) DEFAULT 'DEBIT'"),
            ("reconciliation_score", "FLOAT DEFAULT 0.0"),
        ],
        "journal_entries": [
            ("user_id", "INTEGER"),
        ],
        "fiscal_period_snapshots": [
            ("user_id", "INTEGER"),
        ],
    }

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except SQLAlchemyError:
        existing_tables = set()
        inspector = None

    for table_name, cols in migrations.items():
        existing_cols: set[str] = set()
        if inspector is not None and table_name in existing_tables:
            try:
                existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            except SQLAlchemyError:
                existing_cols = set()

        for col_name, col_type in cols:
            if col_name in existing_cols:
                continue
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
            except SQLAlchemyError as err:
                logging.getLogger("database").debug(
                    "Verificación de columna %s.%s: %s", table_name, col_name, err
                )

    # Endurecimiento relacional no destructivo para PostgreSQL (FKs + UNIQUE por usuario sin borrar usuarios)
    if not _IS_SQLITE:
        pg_constraints = [
            (
                "fk_orders_user_id",
                (
                    "ALTER TABLE orders ADD CONSTRAINT fk_orders_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "fk_bank_vouchers_user_id",
                (
                    "ALTER TABLE bank_vouchers ADD CONSTRAINT fk_bank_vouchers_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "fk_wallet_movements_user_id",
                (
                    "ALTER TABLE wallet_movements ADD CONSTRAINT fk_wallet_movements_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "fk_journal_entries_user_id",
                (
                    "ALTER TABLE journal_entries ADD CONSTRAINT fk_journal_entries_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "fk_journal_entries_voucher_id",
                (
                    "ALTER TABLE journal_entries ADD CONSTRAINT fk_journal_entries_voucher_id "
                    "FOREIGN KEY (voucher_id) REFERENCES bank_vouchers(id) ON DELETE SET NULL NOT VALID"
                ),
            ),
            (
                "fk_fiscal_snapshots_user_id",
                (
                    "ALTER TABLE fiscal_period_snapshots ADD CONSTRAINT fk_fiscal_snapshots_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "fk_accounting_period_user_id",
                (
                    "ALTER TABLE accounting_period_balances ADD CONSTRAINT fk_accounting_period_user_id "
                    "FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE RESTRICT NOT VALID"
                ),
            ),
            (
                "uq_orders_user_order_number",
                "ALTER TABLE orders ADD CONSTRAINT uq_orders_user_order_number UNIQUE (user_id, order_number)",
            ),
            (
                "uq_wallet_movements_user_txid",
                "ALTER TABLE wallet_movements ADD CONSTRAINT uq_wallet_movements_user_txid UNIQUE (user_id, txid)",
            ),
            (
                "uq_fiscal_snapshot_user_period",
                "ALTER TABLE fiscal_period_snapshots ADD CONSTRAINT uq_fiscal_snapshot_user_period UNIQUE (user_id, period)",
            ),
            (
                "uq_accounting_period_user_period",
                "ALTER TABLE accounting_period_balances ADD CONSTRAINT uq_accounting_period_user_period UNIQUE (user_id, period)",
            ),
        ]
        # Reemplazar antiguos índices únicos globales por índices únicos compuestos (user_id, ...)
        for drop_sql in (
            "ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_order_number_key",
            "DROP INDEX IF EXISTS ix_orders_order_number",
            "CREATE INDEX IF NOT EXISTS ix_orders_order_number ON orders (order_number)",
            "ALTER TABLE wallet_movements DROP CONSTRAINT IF EXISTS wallet_movements_txid_key",
            "DROP INDEX IF EXISTS ix_wallet_movements_txid",
            "CREATE INDEX IF NOT EXISTS ix_wallet_movements_txid ON wallet_movements (txid)",
        ):
            try:
                with engine.connect() as conn:
                    conn.execute(text(drop_sql))
                    conn.commit()
            except SQLAlchemyError as err:
                logging.getLogger("database").debug("Migración índice PG: %s", err)

        for cname, ddl in pg_constraints:
            try:
                with engine.connect() as conn:
                    exists = conn.execute(
                        text("SELECT 1 FROM pg_constraint WHERE conname = :c"),
                        {"c": cname},
                    ).first()
                    if not exists:
                        conn.execute(text(ddl))
                        conn.commit()
            except SQLAlchemyError as err:
                logging.getLogger("database").debug("Constraint PG %s: %s", cname, err)

    # Sembrar historial oficial BCV local (60 fechas valor) de forma idempotente
    try:
        from src.reporting.bcv_history_service import BCVHistoryService

        seed_db = SessionLocal()
        try:
            BCVHistoryService(seed_db).seed_historical_rates_if_missing()
        finally:
            seed_db.close()
    except (SQLAlchemyError, OSError, ValueError, ImportError) as err:
        logging.getLogger("database").debug("Seed BCV histórico diferido: %s", err)


_RUNTIME_BOT_PAUSED: bool = False
_BOT_PAUSED_CACHE: dict[int, tuple[float, bool]] = {}
_BOT_PAUSED_CACHE_TTL_SECONDS: float = 15.0


def get_bot_paused_state(db: Session | None = None) -> bool:
    """Obtiene el estado persistente de pausa operativa compartido entre Telegram, API y Engine."""
    if db is not None:
        import time

        from sqlalchemy.exc import SQLAlchemyError

        from src.data.models import SystemState

        bind_id = id(db.get_bind())
        now_ts = time.monotonic()
        cached = _BOT_PAUSED_CACHE.get(bind_id)
        if cached is not None and (now_ts - cached[0]) < _BOT_PAUSED_CACHE_TTL_SECONDS:
            return cached[1]

        try:
            row = db.query(SystemState).filter(SystemState.key == "bot_is_paused").first()
            is_paused = str(row.value).lower() == "true" if row is not None else _RUNTIME_BOT_PAUSED
            _BOT_PAUSED_CACHE[bind_id] = (now_ts, is_paused)
            return is_paused
        except SQLAlchemyError:
            pass
    return _RUNTIME_BOT_PAUSED


def set_bot_paused_state(paused: bool, db: Session | None = None) -> None:
    """Persiste el estado de pausa operativa en base de datos y memoria."""
    import time

    global _RUNTIME_BOT_PAUSED
    _RUNTIME_BOT_PAUSED = bool(paused)
    if db is not None:
        from sqlalchemy.exc import SQLAlchemyError

        from src.data.models import SystemState

        bind_id = id(db.get_bind())
        _BOT_PAUSED_CACHE[bind_id] = (time.monotonic(), bool(paused))
        try:
            row = db.query(SystemState).filter(SystemState.key == "bot_is_paused").first()
            val_str = "true" if paused else "false"
            if row is not None:
                row.value = val_str  # type: ignore[assignment]
            else:
                db.add(SystemState(key="bot_is_paused", value=val_str))
            db.commit()
        except SQLAlchemyError:
            db.rollback()


def seed_env_operators(db: Session, settings: Any) -> dict[str, int]:
    """Sincroniza en BD al arrancar el motor todos los Admins y Traders declarados en variables de entorno."""
    from src.data.repositories import UserRepository
    from src.security.auth_service import AuthService

    repo = UserRepository(db)

    admin_ids: set[str] = {str(uid).strip() for uid in getattr(settings, "telegram_allowed_users", []) if str(uid).strip()}
    alert_chat = str(getattr(settings, "TELEGRAM_ALERT_CHAT_ID", "") or "").strip()
    if alert_chat.isdigit():
        admin_ids.add(alert_chat)

    trader_ids: set[str] = {
        str(uid).strip()
        for uid in getattr(settings, "telegram_trader_users", [])
        if str(uid).strip() and str(uid).strip() not in admin_ids
    }

    for admin_id in sorted(admin_ids):
        existing = repo.get_by_telegram_id(admin_id)
        if not existing:
            uname = "admin" if not repo.get_by_username("admin") else f"admin_{admin_id}"
            repo.create_user(
                username=uname,
                password_hash=AuthService.hash_password(secrets.token_urlsafe(32)),
                role="ADMIN",
                telegram_id=admin_id,
                is_active=True,
            )
        else:
            if str(existing.role).upper() != "ADMIN":
                repo.update_role(cast(int, existing.id), "ADMIN")
            if not existing.is_active:
                repo.set_active_status(cast(int, existing.id), True)

    for trader_id in sorted(trader_ids):
        existing = repo.get_by_telegram_id(trader_id)
        if not existing:
            uname = f"tg_{trader_id}"
            if repo.get_by_username(uname):
                uname = f"trader_{trader_id}"
            repo.create_user(
                username=uname,
                password_hash=AuthService.hash_password(secrets.token_urlsafe(32)),
                role="TRADER",
                telegram_id=trader_id,
                is_active=True,
            )
        else:
            if str(existing.role).upper() not in ("ADMIN", "TRADER"):
                repo.update_role(cast(int, existing.id), "TRADER")
            if not existing.is_active:
                repo.set_active_status(cast(int, existing.id), True)

    return {"admins": len(admin_ids), "traders": len(trader_ids)}




