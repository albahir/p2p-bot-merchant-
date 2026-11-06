import logging
import os
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / "config" / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    pass


def normalize_database_url(raw_url: str) -> str:
    """Normaliza esquemas postgres:// heredados (Render, Neon, Heroku) a postgresql:// para SQLAlchemy 2.0."""
    cleaned = (raw_url or "").strip()
    if cleaned.startswith("postgres://"):
        return "postgresql://" + cleaned[len("postgres://") :]
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


    # Migración ligera para evolución de esquema en SQLite / PostgreSQL (orders)
    for col_def in [
        "counterparty_name VARCHAR(100)",
        "completed_at TIMESTAMP",
        "payment_method VARCHAR(50)",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col_def}"))
                conn.commit()
        except SQLAlchemyError as err:
            logging.getLogger("database").debug("Verificación de columna orders %s: %s", col_def, err)

    # Migración ligera para campos de Google Sheets en app_users
    for col_def in [
        "google_sheet_id VARCHAR(100)",
        "google_refresh_token_enc TEXT",
        "google_auth_type VARCHAR(30) DEFAULT 'SERVICE_ACCOUNT'",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE app_users ADD COLUMN {col_def}"))
                conn.commit()
        except SQLAlchemyError as err:
            logging.getLogger("database").debug("Verificación de columna %s: %s", col_def, err)

    # Migración ligera para campos de OCR y conciliación bancaria en bank_vouchers
    for col_def in [
        "destination_bank VARCHAR(100)",
        "bank_fee_ves FLOAT DEFAULT 0.0",
        "total_debited_ves FLOAT DEFAULT 0.0",
        "sender_phone VARCHAR(30)",
        "concept VARCHAR(255)",
        "movement_type VARCHAR(20) DEFAULT 'DEBIT'",
        "reconciliation_score FLOAT DEFAULT 0.0",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE bank_vouchers ADD COLUMN {col_def}"))
                conn.commit()
        except SQLAlchemyError as err:
            logging.getLogger("database").debug("Verificación de columna bank_vouchers %s: %s", col_def, err)


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
                password_hash=AuthService.hash_password(f"env_{admin_id}"),
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
                password_hash=AuthService.hash_password(f"env_{trader_id}"),
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




