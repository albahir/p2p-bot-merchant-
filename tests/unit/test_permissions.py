"""Tests unitarios para Permissions y Whitelist de IP (Fail-Closed)."""

import pytest
from config.settings import Settings
from src.security.permissions import StartupPermissionValidator
from src.security.audit_logger import AuditLogger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.database import Base

TEST_MASTER_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

@pytest.fixture
def dummy_settings():
    return Settings(
        MASTER_ENCRYPTION_KEY=TEST_MASTER_KEY,
        SERVER_IP_WHITELIST="192.168.1.50,10.0.0.1"
    )

@pytest.fixture
def test_db_session():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return session_factory

def test_ip_in_whitelist_succeeds(dummy_settings, test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)
    validator = StartupPermissionValidator(dummy_settings, audit)
    assert validator.verify_ip_whitelist("192.168.1.50") is True

def test_ip_not_in_whitelist_fails_closed(dummy_settings, test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)
    validator = StartupPermissionValidator(dummy_settings, audit)
    with pytest.raises(PermissionError, match="FAIL-CLOSED"):
        validator.verify_ip_whitelist("203.0.113.199")
