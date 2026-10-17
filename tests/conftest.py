"""Configuración global y fixtures compartidas de pytest."""

import os

import pytest


@pytest.fixture(autouse=True)
def setup_test_master_key(monkeypatch):
    """Asegura que MASTER_ENCRYPTION_KEY esté presente en entornos CI sin config/.env."""
    if not os.environ.get("MASTER_ENCRYPTION_KEY"):
        monkeypatch.setenv(
            "MASTER_ENCRYPTION_KEY",
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
