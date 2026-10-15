"""Tests unitarios para ApiKeyManager (AES-256-GCM y Cero Secretos)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger

TEST_MASTER_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 64 hex chars = 32 bytes

@pytest.fixture
def test_db_session():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return session_factory

def test_encrypt_and_decrypt_secret(test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)
    manager = ApiKeyManager(master_key=TEST_MASTER_KEY, audit_logger=audit, db_session_factory=test_db_session)

    secret_value = "my_super_secret_binance_key_999"
    manager.store_secret("binance_api_key", secret_value)

    retrieved = manager.get_secret("binance_api_key")
    assert retrieved == secret_value

def test_invalid_master_key_fails_closed():
    with pytest.raises(ValueError, match="FAIL-CLOSED"):
        ApiKeyManager(master_key="too_short_key")

def test_tampered_secret_fails_closed(test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)
    manager = ApiKeyManager(master_key=TEST_MASTER_KEY, audit_logger=audit, db_session_factory=test_db_session)

    manager.store_secret("tamper_test", "original_secret")

    # Modificar directamente en la DB el ciphertext para simular manipulación
    db = test_db_session()
    from src.data.models import EncryptedSecret
    record = db.query(EncryptedSecret).filter_by(key_name="tamper_test").first()
    # Invertir el último caracter hex
    record.ciphertext = record.ciphertext[:-2] + ("00" if record.ciphertext[-2:] != "00" else "ff")
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="FAIL-CLOSED"):
        manager.get_secret("tamper_test")

def test_secrets_never_appear_in_audit_events(test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)
    manager = ApiKeyManager(master_key=TEST_MASTER_KEY, audit_logger=audit, db_session_factory=test_db_session)

    super_secret = "confidential_never_in_logs_777"
    manager.store_secret("secret_check", super_secret)

    db = test_db_session()
    from src.data.models import SecurityEvent
    events = db.query(SecurityEvent).all()
    db.close()

    for ev in events:
        assert super_secret not in ev.key_identifier
        assert super_secret not in ev.event_type
        assert super_secret not in ev.event_hash
