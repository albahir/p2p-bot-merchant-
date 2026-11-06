import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / "config" / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./p2p_bot.db")

# Ajuste para SQLite en multithreading si aplica
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
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


    # Migración ligera para evolución de esquema en SQLite (orders)
    for col_def in [
        "counterparty_name VARCHAR(100)",
        "completed_at DATETIME",
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




