"""Tests de integración para rotación de credenciales (Paquete 001)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger

TEST_MASTER_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

def test_key_rotation_in_place():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    audit = AuditLogger(db_session_factory=session_factory)
    manager = ApiKeyManager(master_key=TEST_MASTER_KEY, audit_logger=audit, db_session_factory=session_factory)

    # 1. Guardar clave inicial
    manager.store_secret("binance_api_key", "old_key_111")
    assert manager.get_secret("binance_api_key") == "old_key_111"

    # 2. Rotar a nueva clave
    manager.store_secret("binance_api_key", "new_key_222")
    assert manager.get_secret("binance_api_key") == "new_key_222"
