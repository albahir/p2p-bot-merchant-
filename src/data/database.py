"""Conexión y sesión de base de datos SQLAlchemy."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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

Base = declarative_base()


def get_db():
    """Generador de sesión para dependencias o contextos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
