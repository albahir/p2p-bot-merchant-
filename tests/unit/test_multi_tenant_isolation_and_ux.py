"""Pruebas unitarias TDD para SPEC-022:
1. Aislamiento estricto de datos confidenciales por usuario (Admin NO ve órdenes ni saldos de Traders).
2. Conexión independiente de API de Binance para cada Trader y para el Admin.
3. Visibilidad para el Admin del estado integral del usuario (Telegram, API Binance, Google Sheets).
4. Flujo de conciliación manual ultrarrápida (POST /api/accounting/vouchers/manual) cuando falla el OCR.
5. Alerta de cobertura de riesgo cambiario por Spread Intrabanco Negativo.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_db, get_settings
from src.api.main import create_app
from src.api.security import create_access_token
from src.core.rate_alert_service import RateAlertService
from src.core.spread_monitor import BankRateQuote
from src.data.database import Base
from src.data.models import Order
from src.integrations.telegram_notifier import TelegramNotifier
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app_client(test_db):
    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
        TELEGRAM_BOT_TOKEN="123456789:AAH_TEST_TOKEN_SPEC022",
        TELEGRAM_ALLOWED_USER_IDS="100001",
    )
    app = create_app(skip_lifespan=True, settings=test_settings)
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app, base_url="http://127.0.0.1")


def _token_for(user_id: int, username: str, role: str) -> str:
    return create_access_token(
        {"sub": str(user_id), "username": username, "role": role},
        secret_key=TEST_SECRET,
    )


def test_multi_tenant_data_confidentiality_between_admin_and_traders(app_client, test_db):
    """Garantiza que el ADMIN no pueda ver órdenes, saldos, libro diario ni cierres de un TRADER,
    y que cada operador (incluido el ADMIN) opere sobre su propio espacio confidencial.
    """
    auth_svc = AuthService(db_session=test_db)
    admin = auth_svc.ensure_default_admin(
        default_username="admin_chief",
        default_password="AdminPass123!",
        admin_telegram_id="100001",
    )
    trader = auth_svc.user_repo.create_user(
        username="trader_privado",
        password_hash=auth_svc.hash_password("TraderPass123!"),
        role="TRADER",
        telegram_id="200002",
    )

    admin_headers = {"Authorization": f"Bearer {_token_for(int(admin.id), str(admin.username), 'ADMIN')}"}
    trader_headers = {"Authorization": f"Bearer {_token_for(int(trader.id), str(trader.username), 'TRADER')}"}

    # 1. El Trader posee una orden privada y registra un comprobante manual
    now = datetime(2026, 11, 10, 14, 0, 0, tzinfo=UTC)
    trader_order = Order(
        user_id=int(trader.id),
        order_number="ORD-TRADER-SECRET-001",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=4500.0,
        crypto_amount=100.0,
        unit_price=45.0,
        bcv_rate=40.0,
        order_status="COMPLETED",
        counterparty_name="Cliente Secreto Trader",
        created_at=now,
    )
    test_db.add(trader_order)
    test_db.commit()

    # El Trader registra un pago manual vinculado a su orden
    res_manual = app_client.post(
        "/api/accounting/vouchers/manual",
        headers=trader_headers,
        json={
            "bank_name": "Banesco",
            "reference_number": "7788990011",
            "amount_ves": 4500.0,
            "movement_type": "DEBIT",
            "payment_method": "PAGO_MOVIL",
            "order_number": "ORD-TRADER-SECRET-001",
        },
    )
    assert res_manual.status_code == 200
    assert res_manual.json()["verification_status"] == "MATCHED"

    # El Trader sella su cierre mensual 2026-11
    res_close = app_client.post(
        "/api/fiscal/reconcile",
        headers=trader_headers,
        json={
            "period": "2026-11",
            "initial_balance": 500.0,
            "actual_final_balance": 600.0,
            "cost_method": "FIFO",
        },
    )
    assert res_close.status_code == 200

    # 2. Verificar que el Trader ve sus propios datos
    trader_orders = app_client.get("/api/orders", headers=trader_headers).json()
    assert trader_orders["total"] == 1
    assert trader_orders["items"][0]["order_number"] == "ORD-TRADER-SECRET-001"

    trader_bal = app_client.get(
        "/api/accounting/balances/live?year=2026&month=11",
        headers=trader_headers,
    ).json()
    assert trader_bal["inflow_usdt"] == 100.0
    assert trader_bal["total_outflows_ves"] == 4513.5  # 4500.0 + 0.30% comisión Pago Móvil (13.5 Bs)

    trader_journal = app_client.get("/api/accounting/journal", headers=trader_headers).json()
    assert len(trader_journal) >= 2

    trader_snap = app_client.get("/api/fiscal/snapshot?period=2026-11", headers=trader_headers).json()
    assert trader_snap["is_closed"] is True

    # 3. Verificar que el ADMIN NO ve absolutamente nada de las órdenes ni saldos del Trader
    admin_orders = app_client.get("/api/orders", headers=admin_headers).json()
    assert admin_orders["total"] == 0
    assert admin_orders["items"] == []

    admin_bal = app_client.get(
        "/api/accounting/balances/live?year=2026&month=11",
        headers=admin_headers,
    ).json()
    assert admin_bal["inflow_usdt"] == 0.0
    assert admin_bal["total_outflows_ves"] == 0.0
    assert all(b["bank_name"] != "Banesco" and b["outflows_ves"] == 0.0 for b in admin_bal["bank_breakdown"])

    admin_journal = app_client.get("/api/accounting/journal", headers=admin_headers).json()
    assert admin_journal == []

    admin_snap = app_client.get("/api/fiscal/snapshot?period=2026-11", headers=admin_headers).json()
    assert admin_snap["is_closed"] is False

    # 4. El ADMIN registra su propia orden para probar su sistema y solo él la ve
    admin_own_order = Order(
        user_id=int(admin.id),
        order_number="ORD-ADMIN-EVAL-999",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=2300.0,
        crypto_amount=50.0,
        unit_price=46.0,
        bcv_rate=40.0,
        order_status="COMPLETED",
        counterparty_name="Contraparte Admin",
        created_at=now,
    )
    test_db.add(admin_own_order)
    test_db.commit()

    admin_orders_after = app_client.get("/api/orders", headers=admin_headers).json()
    assert admin_orders_after["total"] == 1
    assert admin_orders_after["items"][0]["order_number"] == "ORD-ADMIN-EVAL-999"

    # El Trader sigue viendo únicamente su orden
    trader_orders_after = app_client.get("/api/orders", headers=trader_headers).json()
    assert trader_orders_after["total"] == 1
    assert trader_orders_after["items"][0]["order_number"] == "ORD-TRADER-SECRET-001"


def test_isolated_binance_api_keys_per_user_and_admin_status_visibility(app_client, test_db):
    """Cada operador (TRADER y ADMIN) puede conectar su propia API de Binance sin colisión,
    y el ADMIN ve en /api/users y en Telegram (/usuarios) el estado integral de cada usuario
    (Telegram, API Binance, Google Sheets) sin exponer claves ni saldos.
    """
    auth_svc = AuthService(db_session=test_db)
    admin = auth_svc.ensure_default_admin(
        default_username="admin_sup",
        default_password="AdminPass123!",
        admin_telegram_id="100001",
    )
    trader = auth_svc.user_repo.create_user(
        username="trader_ccs",
        password_hash=auth_svc.hash_password("TraderPass123!"),
        role="TRADER",
        telegram_id="200002",
    )
    trader.google_sheet_id = "1TraderPersonalSheetId999"  # type: ignore[assignment]
    test_db.commit()

    admin_headers = {"Authorization": f"Bearer {_token_for(int(admin.id), str(admin.username), 'ADMIN')}"}
    trader_headers = {"Authorization": f"Bearer {_token_for(int(trader.id), str(trader.username), 'TRADER')}"}

    # 1. El Trader guarda su propia API Key de Binance
    save_trader = app_client.post(
        "/api/settings/binance",
        headers=trader_headers,
        json={
            "api_key": "TRDRabcd1234567890efghTR99",
            "secret_key": "TraderSecretPayload1234567890!",
            "key_type": "HMAC",
        },
    )
    assert save_trader.status_code == 200
    assert save_trader.json()["is_configured"] is True
    assert "TRDR••••TR99" in save_trader.json()["api_key_masked"]

    # 2. El Admin consulta su propio estado de Binance -> inicialmente NO configurada (aislada del Trader)
    admin_binance_initial = app_client.get("/api/settings/binance", headers=admin_headers).json()
    assert admin_binance_initial["is_configured"] is False

    # 3. El Admin conecta su propia API Key para evaluar el sistema
    save_admin = app_client.post(
        "/api/settings/binance",
        headers=admin_headers,
        json={
            "api_key": "ADMNxyz9876543210abcdAD11",
            "secret_key": "-----BEGIN PRIVATE KEY-----\nAdminEd25519Key\n-----END PRIVATE KEY-----",
            "key_type": "Ed25519",
        },
    )
    assert save_admin.status_code == 200
    assert "ADMN••••AD11" in save_admin.json()["api_key_masked"]

    # El Trader sigue viendo su propia clave enmascarada
    trader_binance_check = app_client.get("/api/settings/binance", headers=trader_headers).json()
    assert "TRDR••••TR99" in trader_binance_check["api_key_masked"]

    # 4. El Admin consulta GET /api/users y ve el estatus de cada aspecto (Telegram, API, Sheets)
    users_res = app_client.get("/api/users", headers=admin_headers)
    assert users_res.status_code == 200
    users_list = users_res.json()
    by_username = {u["username"]: u for u in users_list}

    t_info = by_username["trader_ccs"]
    assert t_info["telegram_linked"] is True
    assert t_info["binance_api_configured"] is True
    assert t_info["binance_key_type"] == "HMAC"
    assert t_info["google_sheet_configured"] is True
    # Jamás expone la clave real del trader
    assert "TRDRabcd" not in users_res.text
    assert "TraderSecret" not in users_res.text

    a_info = by_username["admin_sup"]
    assert a_info["telegram_linked"] is True
    assert a_info["binance_api_configured"] is True
    assert a_info["binance_key_type"] == "Ed25519"
    assert a_info["google_sheet_configured"] is False

    # 5. En Telegram, el comando /usuarios ejecutado por Admin muestra el estatus de API, Sheets y Telegram
    notifier = TelegramNotifier(
        bot_token="123456789:AAH_TEST_TOKEN_SPEC022",
        default_chat_id="100001",
        allowed_user_ids=[100001],
        session_factory=lambda: test_db,
    )
    tg_users_msg = notifier.handle_command(user_id=100001, command="/usuarios")
    assert "trader_ccs" in tg_users_msg
    assert "API" in tg_users_msg
    assert "Sheets" in tg_users_msg


def test_negative_intrabank_spread_and_fx_risk_alert():
    """Verifica que RateAlertService emita alerta de cobertura cambiaria si el spread intrabanco se vuelve negativo."""
    service = RateAlertService(cooldown_seconds=0)
    quotes = [
        BankRateQuote(bank_name="Banesco", buy_rate=1025.0, sell_rate=1012.0, total_ads=40, source="live"),
        BankRateQuote(bank_name="Mercantil", buy_rate=1010.0, sell_rate=1015.0, total_ads=30, source="live"),
    ]
    risk_alert = service.check_negative_spread_risk(quotes, bcv_rate=885.0)
    assert risk_alert is not None
    assert "Banesco" in risk_alert
    assert "NEGATIVO" in risk_alert.upper() or "RIESGO" in risk_alert.upper()
