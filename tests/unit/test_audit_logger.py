"""Tests unitarios para AuditLogger (encadenamiento de hash SHA-256 append-only)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.database import Base
from src.security.audit_logger import AuditLogger
from src.data.models import SecurityEvent

@pytest.fixture
def test_db_session():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return session_factory

def test_audit_hash_chaining(test_db_session):
    audit = AuditLogger(db_session_factory=test_db_session)

    ev1 = audit.log(event_type="LOGIN", key_identifier="user1", ip_address="127.0.0.1", status="SUCCESS")
    assert ev1.prev_hash == "GENESIS_HASH"
    assert len(ev1.event_hash) == 64

    ev2 = audit.log(event_type="READ_KEY", key_identifier="binance", ip_address="127.0.0.1", status="SUCCESS")
    assert ev2.prev_hash == ev1.event_hash

    ev3 = audit.log(event_type="LOGOUT", key_identifier="user1", ip_address="127.0.0.1", status="SUCCESS")
    assert ev3.prev_hash == ev2.event_hash
