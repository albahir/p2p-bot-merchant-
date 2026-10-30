"""Configuración global y fixtures compartidas de pytest."""

import os

import pytest

# Garantizar variables de entorno requeridas a nivel de módulo durante la fase de recolección de pytest en CI
os.environ.setdefault(
    "MASTER_ENCRYPTION_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:fake_token_for_tests")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def setup_test_master_key(monkeypatch):
    """Asegura que MASTER_ENCRYPTION_KEY esté presente en entornos CI sin config/.env."""
    monkeypatch.setenv(
        "MASTER_ENCRYPTION_KEY",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
