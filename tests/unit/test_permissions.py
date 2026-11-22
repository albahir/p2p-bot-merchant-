"""Tests unitarios para Permissions, Whitelist de IP y Detección de IP Pública (Fail-Closed)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from src.data.database import Base
from src.security.audit_logger import AuditLogger
from src.security.permissions import StartupPermissionValidator, detect_public_ip

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


def test_detect_public_ip_returns_valid_ipv4():
    mock_resp = MagicMock(status_code=200, text="109.205.178.33\n")
    mock_resp.raise_for_status = MagicMock()
    with patch("src.security.permissions.httpx.Client") as mock_client_cls:
        client_inst = mock_client_cls.return_value.__enter__.return_value
        client_inst.get.return_value = mock_resp

        detected = detect_public_ip(timeout=2.0)

    assert detected == "109.205.178.33"


def test_detect_public_ip_fallbacks_on_error_and_ignores_invalid_body():
    bad_html = MagicMock(status_code=200, text="<html>Bad Gateway</html>")
    bad_html.raise_for_status = MagicMock()
    good_resp = MagicMock(status_code=200, text="109.205.178.33")
    good_resp.raise_for_status = MagicMock()

    with patch("src.security.permissions.httpx.Client") as mock_client_cls:
        client_inst = mock_client_cls.return_value.__enter__.return_value
        client_inst.get.side_effect = [
            httpx.ConnectTimeout("timeout"),
            bad_html,
            good_resp,
        ]

        detected = detect_public_ip(timeout=2.0)

    assert detected == "109.205.178.33"


def test_detect_public_ip_returns_none_when_offline():
    with patch("src.security.permissions.httpx.Client") as mock_client_cls:
        client_inst = mock_client_cls.return_value.__enter__.return_value
        client_inst.get.side_effect = httpx.ConnectError("offline")

        detected = detect_public_ip(timeout=1.0)

    assert detected is None


def test_verify_runtime_ip_production_strict_checks_public_ip(test_db_session):
    prod_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_MASTER_KEY,
        SERVER_IP_WHITELIST="109.205.178.33",
        ENVIRONMENT="production",
    )
    audit = AuditLogger(db_session_factory=test_db_session)
    validator = StartupPermissionValidator(prod_settings, audit)

    with patch("src.security.permissions.detect_public_ip", return_value="109.205.178.33"):
        verified_ip, public_ip = validator.verify_runtime_ip()

    assert verified_ip == "109.205.178.33"
    assert public_ip == "109.205.178.33"


def test_verify_runtime_ip_production_fails_closed_on_mismatch_or_offline(test_db_session):
    prod_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_MASTER_KEY,
        SERVER_IP_WHITELIST="109.205.178.33",
        ENVIRONMENT="production",
    )
    audit = AuditLogger(db_session_factory=test_db_session)
    validator = StartupPermissionValidator(prod_settings, audit)

    with (
        patch("src.security.permissions.detect_public_ip", return_value="198.51.100.42"),
        pytest.raises(PermissionError, match="FAIL-CLOSED"),
    ):
        validator.verify_runtime_ip()

    with (
        patch("src.security.permissions.detect_public_ip", return_value=None),
        pytest.raises(PermissionError, match="FAIL-CLOSED"),
    ):
        validator.verify_runtime_ip()


def test_verify_runtime_ip_development_allows_local_fallback_while_reporting_public_ip(test_db_session):
    dev_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_MASTER_KEY,
        SERVER_IP_WHITELIST="127.0.0.1",
        ENVIRONMENT="development",
    )
    audit = AuditLogger(db_session_factory=test_db_session)
    validator = StartupPermissionValidator(dev_settings, audit)

    with patch("src.security.permissions.detect_public_ip", return_value="190.120.10.5"):
        verified_ip, public_ip = validator.verify_runtime_ip()

    assert verified_ip == "127.0.0.1"
    assert public_ip == "190.120.10.5"
