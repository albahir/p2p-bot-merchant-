"""Pruebas unitarias de las rutas de Spreads, BCV y Órdenes."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_db, get_settings
from src.api.main import create_app
from src.api.security import create_access_token
from src.data.database import Base
from src.data.models import Order
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app_client(test_db):
    app = create_app(skip_lifespan=True)
    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
    )

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    return TestClient(app, base_url="http://127.0.0.1")


def get_auth_token(user_id: int, role: str) -> str:
    return create_access_token(
        data={"sub": str(user_id), "username": "test_user", "role": role},
        secret_key=TEST_SECRET,
    )


def test_get_bcv_rate(app_client):
    """Verifica que el endpoint /api/spreads/bcv devuelva los datos oficiales de tasa."""
    from src.core.spread_monitor import BankRateQuote
    now = datetime.now(UTC)
    mock_quotes = [
        BankRateQuote(bank_name="Banesco", buy_rate=1010.0, sell_rate=1005.0, updated_at=now),
    ]
    with patch("src.api.routes.spreads.BCVService") as MockBCV, \
         patch("src.api.routes.spreads.SpreadMonitor.fetch_live_quotes", return_value=mock_quotes):
        mock_instance = MockBCV.return_value
        mock_instance.fetch_full_rates.return_value = {
            "usd": 881.07,
            "eur": 991.16,
            "fecha_valor": "Lunes, 19 Octubre 2026",
        }
        res = app_client.get("/api/spreads/bcv")
        assert res.status_code == 200
        data = res.json()
        assert data["usd"] == 881.07
        assert data["eur"] == 991.16
        assert data["fecha_valor"] == "Lunes, 19 Octubre 2026"


def test_get_spread_matrix(app_client):
    """Verifica el cálculo de la matriz de arbitraje interbancario."""
    from src.core.spread_monitor import BankRateQuote
    now = datetime.now(UTC)
    mock_quotes = [
        BankRateQuote(bank_name="Banesco", buy_rate=1010.0, sell_rate=1005.0, updated_at=now),
        BankRateQuote(bank_name="Mercantil", buy_rate=1012.0, sell_rate=1008.0, updated_at=now),
    ]
    with patch("src.api.routes.spreads.SpreadMonitor.fetch_live_quotes", return_value=mock_quotes):
        res = app_client.get("/api/spreads/matrix?amount_usdt=100")
        assert res.status_code == 200
        data = res.json()
        assert "quotes" in data
        assert "bcv_official_usd" in data
        assert isinstance(data["quotes"], list)
        assert len(data["quotes"]) == 2


def test_orders_list_paginated_and_auth(app_client, test_db):
    """Verifica el listado paginado de órdenes y el requerimiento de autenticación."""
    # 1. Sin autenticación -> 401
    res_unauth = app_client.get("/api/orders")
    assert res_unauth.status_code == 401

    # 2. Crear usuario y órdenes en base de datos
    auth_svc = AuthService(db_session=test_db)
    user = auth_svc.ensure_default_admin(default_username="trader1")

    order = Order(
        order_number="ORDER12345",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=101000.0,
        crypto_amount=100.0,
        unit_price=1010.0,
        fee_fiat=0.0,
        fee_crypto=0.0,
        bcv_rate=880.0,
        order_status="COMPLETED",
        counterparty_name="CryptoMerchantVE",
        created_at=datetime.now(UTC),
    )
    test_db.add(order)
    test_db.commit()

    token = get_auth_token(int(user.id), "ADMIN")
    res = app_client.get("/api/orders", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["order_number"] == "ORDER12345"
    assert data["items"][0]["counterparty_name"] == "CryptoMerchantVE"


def test_orders_export_csv_and_excel(app_client, test_db):
    """Verifica descarga de exportaciones de órdenes en Excel y CSV."""
    auth_svc = AuthService(db_session=test_db)
    user = auth_svc.ensure_default_admin(default_username="trader2")
    token = get_auth_token(int(user.id), "ADMIN")

    # Exportar en CSV (semicolon)
    res_csv = app_client.get("/api/orders/export?format=csv_semicolon", headers={"Authorization": f"Bearer {token}"})
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]

    # Exportar en Excel (.xlsx)
    res_xlsx = app_client.get("/api/orders/export?format=xlsx", headers={"Authorization": f"Bearer {token}"})
    assert res_xlsx.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_xlsx.headers["content-type"]
