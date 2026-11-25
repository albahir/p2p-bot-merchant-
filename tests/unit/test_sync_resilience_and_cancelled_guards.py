"""Pruebas TDD para resiliencia de sincronización Binance API (límite 180d, orden inverso,
guardado incremental, auto-conciliación) y blindaje contra órdenes canceladas en todo el motor fiscal/contable.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.routes.accounting import (
    ManualVoucherRequest,
    MatchVoucherRequest,
    create_manual_voucher,
    match_voucher_with_order,
)
from src.api.routes.orders import list_orders, sync_binance_orders
from src.api.routes.settings import verify_binance_connection
from src.api.schemas.orders import SyncOrdersRequest
from src.core.binance_client import BinanceP2PClient
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.core.binance_schemas import BinanceOrderMatchItem
from src.data.database import Base
from src.data.models import BankVoucher, Order
from src.data.repositories import OrderRepository
from src.reporting.reconciliation_engine import P2PReconciliationEngine
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod
from src.security.api_key_manager import ApiKeyManager
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def trader_and_settings(db_session):
    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
    )
    auth_svc = AuthService(db_session=db_session)
    user = auth_svc.ensure_default_admin(default_username="sync_trader")
    return user, test_settings


def _make_item(
    order_number: str,
    trade_type: str = "BUY",
    status: str = "COMPLETED",
    amount: str = "100.0",
    total_price: str = "50000.0",
    unit_price: str = "500.0",
    create_time_ms: int | None = None,
    pay_method: str | None = "Banesco",
) -> BinanceOrderMatchItem:
    ts = create_time_ms or int(datetime.now(UTC).timestamp() * 1000)
    payload: dict[str, Any] = {
        "orderNumber": order_number,
        "advNo": f"ADV_{order_number}",
        "tradeType": trade_type,
        "asset": "USDT",
        "fiat": "VES",
        "fiatSymbol": "Bs",
        "amount": amount,
        "totalPrice": total_price,
        "unitPrice": unit_price,
        "orderStatus": status,
        "createTime": ts,
        "commission": "0.0",
        "takerCommission": "0.0",
        "counterPartNickName": "TraderDemo",
    }
    if pay_method is not None:
        payload["payMethodName"] = pay_method
    return BinanceOrderMatchItem.model_validate(payload)


def test_sync_orders_clamps_365_days_to_180_and_iterates_newest_first(db_session):
    """Pedir 365 días por API debe ajustarse al límite real de 180 días de Binance y consultar del más reciente al más antiguo."""
    captured_windows: list[tuple[int, int, int]] = []

    class SpyClient:
        def get_order_history(
            self,
            trade_type: str,
            start_timestamp: int,
            end_timestamp: int,
            page: int = 1,
            rows: int = 100,
        ):
            captured_windows.append((start_timestamp, end_timestamp, rows))
            return SimpleNamespace(data=[])

    syncer = BinanceHistorySyncer()
    res = syncer.sync_orders(
        client=SpyClient(),
        db=db_session,
        days=365,
        trade_type="BUY",
        include_exports=False,
    )

    assert res.success is True
    assert res.days_clamped is True
    assert res.effective_days == 180
    assert any("180" in w or "6 meses" in w for w in res.warnings)
    # 180 días en ventanas <= 30 días => exactamente 6 ventanas para BUY
    assert len(captured_windows) == 6
    # Debe usar rows=100 por defecto para reducir llamadas HTTP a la mitad
    assert all(r == 100 for _, _, r in captured_windows)
    # Debe ir de la ventana más reciente a la más antigua (end_timestamp estrictamente decreciente)
    ends = [w[1] for w in captured_windows]
    assert ends == sorted(ends, reverse=True)
    # No debe generar exportes pesados si include_exports=False
    assert res.csv_bytes is None
    assert res.excel_bytes is None


def test_sync_orders_preserves_recent_orders_when_older_window_rejected(db_session):
    """Si una ventana antigua falla por límite temporal de Binance, las ventanas recientes ya descargadas deben guardarse."""
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    call_idx = 0

    class PartialFailureClient:
        def get_order_history(
            self,
            trade_type: str,
            start_timestamp: int,
            end_timestamp: int,
            page: int = 1,
            rows: int = 100,
        ):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                return SimpleNamespace(
                    data=[
                        _make_item(
                            "ORD-RECENT-001",
                            trade_type="BUY",
                            status="COMPLETED",
                            create_time_ms=now_ms - 3600 * 1000,
                        )
                    ]
                )
            raise RuntimeError("Error Binance [083009]: Query time exceeds 6 months limit")

    syncer = BinanceHistorySyncer()
    res = syncer.sync_orders(
        client=PartialFailureClient(),
        db=db_session,
        days=180,
        trade_type="BUY",
        include_exports=False,
    )

    assert res.success is True
    assert res.orders_inserted == 1
    assert len(res.warnings) >= 1
    saved = OrderRepository(db_session).list_completed()
    assert [o.order_number for o in saved] == ["ORD-RECENT-001"]


def test_sync_orders_only_completed_skips_cancelled_and_updates_pending(db_session):
    """only_completed=True omite canceladas, excluye canceladas de volúmenes y actualiza PENDING->COMPLETED."""
    now_dt = datetime.now(UTC)
    existing_pending = Order(
        user_id=1,
        order_number="ORD-PEND-001",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=50000.0,
        crypto_amount=100.0,
        unit_price=500.0,
        fee_fiat=0.0,
        fee_crypto=0.0,
        bcv_rate=400.0,
        order_status="PENDING",
        counterparty_name="TraderDemo",
        created_at=now_dt - timedelta(hours=2),
    )
    db_session.add(existing_pending)
    db_session.commit()

    now_ms = int(now_dt.timestamp() * 1000)

    class MixedStatusClient:
        def get_order_history(self, trade_type, start_timestamp, end_timestamp, page=1, rows=100):
            if trade_type == "BUY" and page == 1:
                return SimpleNamespace(
                    data=[
                        _make_item("ORD-PEND-001", "BUY", "COMPLETED", "100.0", "50000.0", "500.0", now_ms - 7200 * 1000, "Banesco"),
                        _make_item("ORD-COMP-002", "BUY", "COMPLETED", "50.0", "25000.0", "500.0", now_ms - 3600 * 1000, "Mercantil"),
                        _make_item("ORD-CANC-003", "BUY", "CANCELLED", "200.0", "100000.0", "500.0", now_ms - 1800 * 1000, "Banesco"),
                        _make_item("ORD-CANC-004", "BUY", "CANCELLED_BY_SYSTEM", "300.0", "150000.0", "500.0", now_ms - 900 * 1000, "Banesco"),
                    ]
                )
            return SimpleNamespace(data=[])

    syncer = BinanceHistorySyncer()
    res = syncer.sync_orders(
        client=MixedStatusClient(),
        db=db_session,
        days=7,
        trade_type="BUY",
        user_id=1,
        only_completed=True,
        include_exports=False,
    )

    assert res.success is True
    assert res.orders_inserted == 1  # solo ORD-COMP-002
    assert res.orders_updated == 1  # ORD-PEND-001 pasó de PENDING a COMPLETED
    assert res.cancelled_skipped == 2  # 2 canceladas omitidas
    # Volumen solo refleja las 2 completadas (100 + 50 = 150 USDT), NUNCA las canceladas (500 USDT)
    assert res.total_volume_usdt == pytest.approx(150.0, abs=0.01)
    assert res.total_volume_fiat == pytest.approx(75000.0, abs=0.01)

    all_in_db = db_session.query(Order).filter(Order.user_id == 1).all()
    assert len(all_in_db) == 2
    by_num = {o.order_number: o for o in all_in_db}
    assert by_num["ORD-PEND-001"].order_status == "COMPLETED"
    assert by_num["ORD-PEND-001"].payment_method == "Banesco"
    assert by_num["ORD-COMP-002"].payment_method == "Mercantil"
    assert "ORD-CANC-003" not in by_num


def test_sync_orders_auto_reconciles_orphan_vouchers(db_session):
    """Tras sincronizar por API, los comprobantes huérfanos deben auto-conciliarse solo con órdenes COMPLETED."""
    now_dt = datetime.now(UTC)
    voucher = BankVoucher(
        user_id=1,
        bank_name="Banesco",
        reference_number="99887766",
        amount_ves=50000.0,
        bank_fee_ves=0.0,
        total_debited_ves=50000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        verification_status="UNMATCHED",
        voucher_date=now_dt - timedelta(minutes=10),
    )
    db_session.add(voucher)
    db_session.commit()

    now_ms = int(now_dt.timestamp() * 1000)

    class OneCompletedAndOneCancelledClient:
        def get_order_history(self, trade_type, start_timestamp, end_timestamp, page=1, rows=100):
            if trade_type == "BUY" and page == 1:
                return SimpleNamespace(
                    data=[
                        _make_item("ORD-CANC-MATCH", "BUY", "CANCELLED", "100.0", "50000.0", "500.0", now_ms - 600 * 1000, "Banesco"),
                        _make_item("ORD-OK-MATCH", "BUY", "COMPLETED", "100.0", "50000.0", "500.0", now_ms - 600 * 1000, "Banesco"),
                    ]
                )
            return SimpleNamespace(data=[])

    syncer = BinanceHistorySyncer()
    res = syncer.sync_orders(
        client=OneCompletedAndOneCancelledClient(),
        db=db_session,
        days=7,
        trade_type="BUY",
        user_id=1,
        only_completed=True,
        include_exports=False,
    )

    assert res.success is True
    assert res.reconciled_vouchers == 1
    db_session.refresh(voucher)
    assert voucher.verification_status == "MATCHED"
    assert voucher.associated_order_number == "ORD-OK-MATCH"


def test_binance_schema_tolerates_unknown_status_null_advno_and_pay_method():
    """BinanceOrderMatchItem no debe romper toda la sincronización por estados nuevos, advNo nulo o rol vacío."""
    raw = {
        "orderNumber": "20260101000999",
        "advNo": None,
        "tradeType": "SELL",
        "asset": "USDT",
        "fiat": "VES",
        "amount": "25.0",
        "totalPrice": "12500.0",
        "unitPrice": "500.0",
        "orderStatus": "EXPIRED",
        "createTime": 1760000000000,
        "advertisementRole": "",
        "payMethodName": "Pago Móvil",
    }
    item = BinanceOrderMatchItem.model_validate(raw)
    assert item.orderNumber == "20260101000999"
    assert item.advNo == ""
    assert item.orderStatus.value == "CANCELLED"
    assert item.advertisementRole is None
    assert item.payMethodName == "Pago Móvil"


def test_import_orders_file_respects_order_status_and_excludes_cancelled(db_session):
    """import_orders_file debe leer la columna Estado/Status y JAMÁS marcar filas canceladas como COMPLETED."""
    df = pd.DataFrame([
        {
            "Order Number": "CSV-OK-01",
            "Order Type": "BUY",
            "Asset": "USDT",
            "Fiat": "VES",
            "Total Price": 50000.0,
            "Quantity": 100.0,
            "Unit Price": 500.0,
            "Order Status": "Completed",
            "Payment Method": "Banesco",
            "Maker Fee": 0.1,
            "Counterparty": "UserA",
            "Created Time": "2026-11-10 10:00:00",
        },
        {
            "Order Number": "CSV-CANC-02",
            "Order Type": "BUY",
            "Asset": "USDT",
            "Fiat": "VES",
            "Total Price": 80000.0,
            "Quantity": 160.0,
            "Unit Price": 500.0,
            "Order Status": "Cancelled",
            "Payment Method": "Mercantil",
            "Maker Fee": 0.0,
            "Counterparty": "UserB",
            "Created Time": "2026-11-10 11:00:00",
        },
        {
            "Order Number": "CSV-CANC-03",
            "Order Type": "SELL",
            "Asset": "USDT",
            "Fiat": "VES",
            "Total Price": 90000.0,
            "Quantity": 180.0,
            "Unit Price": 500.0,
            "Order Status": "Cancelado por el sistema",
            "Payment Method": "Pago Móvil",
            "Maker Fee": 0.0,
            "Counterparty": "UserC",
            "Created Time": "2026-11-10 12:00:00",
        },
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    syncer = BinanceHistorySyncer()
    res = syncer.import_orders_file(
        file_bytes=buf.getvalue(),
        filename="p2p_export.xlsx",
        db=db_session,
        user_id=1,
        only_completed=True,
    )

    assert res.success is True
    assert res.orders_inserted == 1
    assert res.cancelled_skipped == 2
    assert res.total_volume_usdt == pytest.approx(100.0, abs=0.01)

    completed = OrderRepository(db_session, user_id=1).list_completed()
    assert [o.order_number for o in completed] == ["CSV-OK-01"]
    assert completed[0].payment_method == "Banesco"
    assert completed[0].fee_crypto == pytest.approx(0.1, abs=1e-4)


def test_tax_engine_ignores_cancelled_orders_defensively():
    """FIFO y Costo Promedio deben ignorar órdenes no COMPLETED aunque se pasen sin pre-filtrar."""
    now = datetime.now(UTC)
    orders = [
        Order(
            order_number="B1", trade_type="BUY", asset="USDT", fiat="VES",
            fiat_amount=10000.0, crypto_amount=100.0, unit_price=100.0,
            fee_fiat=0.0, fee_crypto=0.0, bcv_rate=100.0,
            order_status="COMPLETED", created_at=now,
        ),
        Order(
            order_number="B_CANC", trade_type="BUY", asset="USDT", fiat="VES",
            fiat_amount=999999.0, crypto_amount=100.0, unit_price=9999.99,
            fee_fiat=0.0, fee_crypto=0.0, bcv_rate=100.0,
            order_status="CANCELLED", created_at=now,
        ),
        Order(
            order_number="S1", trade_type="SELL", asset="USDT", fiat="VES",
            fiat_amount=11000.0, crypto_amount=100.0, unit_price=110.0,
            fee_fiat=0.0, fee_crypto=0.0, bcv_rate=100.0,
            order_status="COMPLETED", created_at=now,
        ),
        Order(
            order_number="S_CANC", trade_type="SELL", asset="USDT", fiat="VES",
            fiat_amount=50000.0, crypto_amount=100.0, unit_price=500.0,
            fee_fiat=0.0, fee_crypto=0.0, bcv_rate=100.0,
            order_status="CANCELLED_BY_SYSTEM", created_at=now,
        ),
    ]

    fifo_res = FIFOCostMethod().process_orders(orders)
    avg_res = WeightedAverageCostMethod().process_orders(orders)

    assert len(fifo_res) == 1
    assert fifo_res[0].order_number == "S1"
    assert fifo_res[0].net_profit_fiat == pytest.approx(1000.0, abs=0.01)

    assert len(avg_res) == 1
    assert avg_res[0].order_number == "S1"
    assert avg_res[0].net_profit_fiat == pytest.approx(1000.0, abs=0.01)


def test_reconciliation_engine_and_manual_match_block_cancelled_orders(trader_and_settings, db_session):
    """El motor de conciliación y el endpoint manual jamás deben vincular un comprobante a una orden cancelada."""
    user, _ = trader_and_settings
    now = datetime.now(UTC)

    cancelled_order = Order(
        user_id=int(user.id),
        order_number="ORD-CANC-NO-MATCH",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=25000.0,
        crypto_amount=50.0,
        unit_price=500.0,
        fee_fiat=0.0,
        fee_crypto=0.0,
        bcv_rate=400.0,
        order_status="CANCELLED",
        payment_method="Banesco",
        counterparty_name="Juan Perez",
        created_at=now,
    )
    sys_cancelled_order = Order(
        user_id=int(user.id),
        order_number="ORD-CANC-SYS-02",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=15000.0,
        crypto_amount=30.0,
        unit_price=500.0,
        fee_fiat=0.0,
        fee_crypto=0.0,
        bcv_rate=400.0,
        order_status="CANCELLED_BY_SYSTEM",
        payment_method="Mercantil",
        counterparty_name="Ana Gomez",
        created_at=now,
    )
    voucher = BankVoucher(
        user_id=int(user.id),
        bank_name="Banesco",
        reference_number="12345678",
        amount_ves=25000.0,
        bank_fee_ves=0.0,
        total_debited_ves=25000.0,
        sender_name="Juan Perez",
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        verification_status="UNMATCHED",
        voucher_date=now,
    )
    db_session.add_all([cancelled_order, sys_cancelled_order, voucher])
    db_session.commit()
    db_session.refresh(voucher)

    # 1. Hard filter en P2PReconciliationEngine
    score = P2PReconciliationEngine().calculate_score(voucher, cancelled_order)
    assert score == 0.0

    # 2. Endpoint manual match rechaza orden cancelada con HTTP 400
    with pytest.raises(HTTPException) as exc_match:
        match_voucher_with_order(
            voucher_id=int(voucher.id),
            payload=MatchVoucherRequest(order_number="ORD-CANC-NO-MATCH"),
            db=db_session,
            current_user=user,
        )
    assert exc_match.value.status_code == 400
    assert "CANCELLED" in str(exc_match.value.detail) or "COMPLET" in str(exc_match.value.detail).upper()

    # 3. Endpoint voucher manual con order_number cancelada también rechaza HTTP 400
    with pytest.raises(HTTPException) as exc_manual:
        create_manual_voucher(
            payload=ManualVoucherRequest(
                bank_name="Banesco",
                reference_number="99911122",
                amount_ves=25000.0,
                movement_type="DEBIT",
                order_number="ORD-CANC-NO-MATCH",
            ),
            db=db_session,
            current_user=user,
        )
    assert exc_manual.value.status_code == 400

    # 4. Filtro order_status="CANCELLED" en /api/orders agrupa CANCELLED y CANCELLED_BY_SYSTEM
    res_canc = list_orders(
        db=db_session,
        current_user=user,
        page=1,
        page_size=20,
        trade_type=None,
        order_status="CANCELLED",
        search=None,
    )
    assert res_canc.total == 2


def test_api_orders_sync_missing_keys_returns_400(trader_and_settings, db_session):
    """Si el usuario no ha configurado sus API Keys de Binance, /api/orders/sync debe responder 400 claro y no 502."""
    user, test_settings = trader_and_settings
    with pytest.raises(HTTPException) as exc:
        sync_binance_orders(
            req=SyncOrdersRequest(days=30),
            db=db_session,
            current_user=user,
            settings=test_settings,
        )
    assert exc.value.status_code == 400
    assert "Configuración" in str(exc.value.detail) or "API" in str(exc.value.detail)


def test_verify_binance_connection_detects_real_auth_failure(trader_and_settings, db_session):
    """verify_binance_connection debe probar una petición autenticada real y detectar -2015 / 401 aunque /api/v3/time responda 200."""
    user, test_settings = trader_and_settings
    factory = sessionmaker(bind=db_session.get_bind())
    km = ApiKeyManager(master_key=test_settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    km.store_secret(f"user_{user.id}:binance_api_key", "vm4Pabcd1234567890efghXk9b")
    km.store_secret(f"user_{user.id}:binance_private_key", "SecretPayload1234567890SecretPayload!")
    km.store_secret(f"user_{user.id}:binance_key_type", "HMAC")

    time_resp = MagicMock()
    time_resp.status_code = 200
    time_resp.json.return_value = {"serverTime": 1700000000000}
    time_resp.headers = {"x-mbx-used-weight-1m": "1"}

    auth_fail_resp = MagicMock()
    auth_fail_resp.status_code = 401
    auth_fail_resp.text = '{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}'
    auth_fail_resp.json.return_value = {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}
    auth_fail_resp.headers = {"x-mbx-used-weight-1m": "2"}

    with patch("httpx.Client.get", side_effect=[time_resp, auth_fail_resp]):
        data = verify_binance_connection(
            _current_user=user,
            settings=test_settings,
            db=db_session,
        )
        assert data.success is False
        assert data.is_connected is False
        assert "IP" in data.message or "permiso" in data.message.lower() or "rechaz" in data.message.lower()


def test_binance_client_reuses_http_client_and_retries_transient_errors(monkeypatch):
    """get_order_history debe reintentar errores transitorios de red/5xx y reutilizar la sesión HTTP."""
    client = BinanceP2PClient(api_key="test_api_key", private_key_pem="a" * 64)
    attempts = 0

    def flaky_get(self, url, params=None, headers=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("Transient timeout")
        return httpx.Response(
            status_code=200,
            json={"code": "000000", "message": "success", "data": []},
            headers={"x-mbx-used-weight": "2"},
            request=httpx.Request("GET", str(url)),
        )

    monkeypatch.setattr(httpx.Client, "get", flaky_get)
    now = 1700000000000
    res = client.get_order_history("BUY", start_timestamp=now - 1000, end_timestamp=now)
    assert res.code == "000000"
    assert attempts == 2
    client.close()
