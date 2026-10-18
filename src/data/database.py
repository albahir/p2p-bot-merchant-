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


    # Migración ligera para evolución de esquema en SQLite
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE orders ADD COLUMN counterparty_name VARCHAR(100)"))
            conn.commit()
    except SQLAlchemyError as err:
        logging.getLogger("database").debug("Verificación de columna counterparty_name: %s", err)


