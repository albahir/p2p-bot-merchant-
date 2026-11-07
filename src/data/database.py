import logging
import os
import secrets
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine, inspect
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

# Ajuste para SQLite en multithreading y reconexión resiliente para PostgreSQL en la nube
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


def get_db():
    """Generador de sesión para dependencias o contextos."""
    db = SessionLocal()
    try:
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
            ("counterparty_name", "VARCHAR(100)"),
            ("completed_at", "TIMESTAMP"),
            ("payment_method", "VARCHAR(50)"),
        ],
        "app_users": [
            ("google_sheet_id", "VARCHAR(100)"),
            ("google_refresh_token_enc", "TEXT"),
            ("google_auth_type", "VARCHAR(30) DEFAULT 'SERVICE_ACCOUNT'"),
        ],
        "bank_vouchers": [
            ("destination_bank", "VARCHAR(100)"),
            ("bank_fee_ves", "FLOAT DEFAULT 0.0"),
            ("total_debited_ves", "FLOAT DEFAULT 0.0"),
            ("sender_phone", "VARCHAR(30)"),
            ("concept", "VARCHAR(255)"),
            ("movement_type", "VARCHAR(20) DEFAULT 'DEBIT'"),
            ("reconciliation_score", "FLOAT DEFAULT 0.0"),
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


_RUNTIME_BOT_PAUSED: bool = False


def get_bot_paused_state(db: Session | None = None) -> bool:
    """Obtiene el estado persistente de pausa operativa compartido entre Telegram, API y Engine."""
    if db is not None:
        from sqlalchemy.exc import SQLAlchemyError

        from src.data.models import SystemState

        try:
            row = db.query(SystemState).filter(SystemState.key == "bot_is_paused").first()
            if row is not None:
                return str(row.value).lower() == "true"
        except SQLAlchemyError:
            pass
    return _RUNTIME_BOT_PAUSED


def set_bot_paused_state(paused: bool, db: Session | None = None) -> None:
    """Persiste el estado de pausa operativa en base de datos y memoria."""
    global _RUNTIME_BOT_PAUSED
    _RUNTIME_BOT_PAUSED = bool(paused)
    if db is not None:
        from sqlalchemy.exc import SQLAlchemyError

        from src.data.models import SystemState

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




