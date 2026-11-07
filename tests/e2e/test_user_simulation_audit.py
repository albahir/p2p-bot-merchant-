"""Suite E2E de Simulación Real de Usuario (SPEC-021).
Recorre como un operador humano todas las pantallas de P2P Merchant OS (API ASGI completa + contratos Web)
y todos los roles/comandos del Bot de Telegram (INVITADO, TRADER, ADMIN), verificando:
- Seguridad anti-fuga de OTP y sanitización de secretos hexadecimales de 64 caracteres.
- Onboarding de operadores pre-autorizados sin colisión IntegrityError.
- Cálculos exactos de arbitraje interbancario, escalado por monto, FIFO vs Costo Promedio y tasa BCV real.
- Contabilidad SENIAT: cadena SHA-256 íntegra multi-línea, desglose multi-banco, OCR Fail-closed y cierre mensual persistente.
- Exportaciones autenticadas por cabecera Bearer (Excel, CSV y PDF).
- Flujos completos del Bot de Telegram por rol, ruteo de /cierre al Trader solicitante y asientos contables en OCR móvil.
"""

from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_db, get_settings
from src.api.main import create_app
from src.core.spread_monitor import BankRateQuote, SpreadMonitor
from src.data.database import Base
from src.data.models import BankVoucher, FiscalPeriodSnapshot, JournalEntry, Order
from src.integrations.receipt_ocr import ReceiptExtractionResult
from src.integrations.telegram_notifier import TelegramNotifier, sanitize_message
from src.security.auth_service import AuthService

TEST_MASTER_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TEST_JWT_SECRET = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
TEST_BOT_TOKEN = "123456789:AAH_TEST_SIMULATION_TOKEN_987654"


@dataclass
class AsgiTestResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> Any:
        return json_lib.loads(self.content.decode("utf-8"))


def _drive_coroutine(coro: Any) -> Any:
    """Ejecuta una corrutina ASGI en memoria sin abrir sockets de sistema (compatible con Windows Sandbox)."""
    try:
        fut = coro.send(None)
        while True:
            # Si cede ante un awaitable simple (ej. sleep(0) / checkpoint), reanudar
            fut = coro.send(None)
            _ = fut
    except StopIteration as stop:
        return stop.value


def _request(
    app: Any,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json: Any = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> AsgiTestResponse:
    """Invoca el stack ASGI completo de FastAPI en memoria (rutas, Depends, RBAC, serialización)."""
    parsed = urlsplit(url)
    req_headers: list[tuple[bytes, bytes]] = [
        (b"host", b"testserver"),
    ]
    if headers:
        for k, v in headers.items():
            req_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    body_bytes = b""
    if json is not None:
        body_bytes = json_lib.dumps(json).encode("utf-8")
        req_headers.append((b"content-type", b"application/json"))
        req_headers.append((b"content-length", str(len(body_bytes)).encode("ascii")))
    elif files is not None:
        boundary = "----P2PBotBoundary7MA4YWxkTrZu0gW"
        chunks: list[bytes] = []
        for field_name, (filename, file_bytes, mime_type) in files.items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
            )
            chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
            chunks.append(file_bytes)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body_bytes = b"".join(chunks)
        req_headers.append((b"content-type", f"multipart/form-data; boundary={boundary}".encode()))
        req_headers.append((b"content-length", str(len(body_bytes)).encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("utf-8"),
        "query_string": parsed.query.encode("utf-8"),
        "headers": req_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    sent = False
    status_code = 500
    resp_headers: dict[str, str] = {}
    resp_chunks: list[bytes] = []

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
            for hk, hv in message.get("headers", []):
                resp_headers[hk.decode("latin-1").lower()] = hv.decode("latin-1")
        elif message["type"] == "http.response.body":
            resp_chunks.append(message.get("body", b""))

    # Parchear run_in_threadpool de Starlette/FastAPI para ejecutar en línea sin thread/eventloop
    async def _inline_threadpool(func: Any, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    with (
        patch("starlette.concurrency.run_in_threadpool", side_effect=_inline_threadpool),
        patch("fastapi.concurrency.run_in_threadpool", side_effect=_inline_threadpool),
        patch("starlette.routing.run_in_threadpool", side_effect=_inline_threadpool),
        patch("fastapi.routing.run_in_threadpool", side_effect=_inline_threadpool),
        patch("fastapi.dependencies.utils.run_in_threadpool", side_effect=_inline_threadpool),
    ):
        _drive_coroutine(app(scope, receive, send))

    return AsgiTestResponse(
        status_code=status_code,
        headers=resp_headers,
        content=b"".join(resp_chunks),
    )


@pytest.fixture
def sim_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db: Session = session_factory()

    settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_MASTER_KEY,
        JWT_SECRET_KEY=TEST_JWT_SECRET,
        TELEGRAM_BOT_TOKEN=TEST_BOT_TOKEN,
        TELEGRAM_ALERT_CHAT_ID="6326947793",
        TELEGRAM_ALLOWED_USER_IDS="6326947793",
        TELEGRAM_TRADER_USER_IDS="6430765245",
        USE_SANDBOX=True,
    )

    auth_svc = AuthService(db_session=db)
    auth_svc.ensure_default_admin(
        default_username="admin_master",
        default_password="AdminPassword2026!",
        admin_telegram_id="6326947793",
    )

    app = create_app(skip_lifespan=True, settings=settings)

    def _override_db() -> Session:
        return db

    def _override_settings():
        return settings

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    try:
        yield app, db, session_factory, settings
    finally:
        db.close()


def test_security_no_otp_leak_and_64hex_sanitization(sim_env):
    """1. Verifica Cero Fugas de OTP en recuperación web y redacción real de claves hex de 64 chars."""
    app, db, _, _ = sim_env

    from src.data.repositories import UserRepository

    repo = UserRepository(db)
    repo.create_user(
        username="local_operator",
        password_hash=AuthService.hash_password("InitialPass123!"),
        role="TRADER",
        telegram_id=None,
    )

    res = _request(app, "POST", "/api/auth/recover-password", json={"username": "local_operator"})
    assert res.status_code == 200
    body = res.json()
    assert "debug_code" not in body or body.get("debug_code") is None

    # Recuperación ingresando telegram_id numérico en lugar de username
    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True) as mock_send:
        res_tg = _request(app, "POST", "/api/auth/recover-password", json={"username": "6326947793"})
        assert res_tg.status_code == 200
        sent_text = mock_send.call_args[0][0]
        import re

        otp_match = re.search(r"(\d{6})", sent_text)
        assert otp_match is not None
        otp_code = otp_match.group(1)

    res_reset = _request(
        app,
        "POST",
        "/api/auth/reset-password",
        json={
            "username": "6326947793",
            "reset_code": otp_code,
            "new_password": "NewAdminPassword2026!",
        },
    )
    assert res_reset.status_code == 200

    # Sanitización de clave maestra de 64 caracteres hexadecimales
    leaked_msg = f"Error cargando llave {TEST_MASTER_KEY} en memoria"
    clean_msg = sanitize_message(leaked_msg)
    assert TEST_MASTER_KEY not in clean_msg
    assert "[REDACTED]" in clean_msg


def test_onboarding_preauthorized_operator_and_rbac_governance(sim_env):
    """2. Verifica que un operador pre-autorizado por Admin pueda registrarse en /register sin HTTP 500."""
    app, _, _, _ = sim_env

    login_res = _request(
        app,
        "POST",
        "/api/auth/login",
        json={"username": "admin_master", "password": "AdminPassword2026!"},
    )
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin pre-autoriza en /settings el ID de Telegram 6430765245
    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        pre_res = _request(
            app,
            "POST",
            "/api/users/authorize-telegram",
            headers=headers,
            json={"telegram_id": "6430765245", "role": "TRADER"},
        )
    assert pre_res.status_code == 200

    # Ahora el humano dueño de 6430765245 entra a /register a crear su usuario y clave
    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        reg_res = _request(
            app,
            "POST",
            "/api/auth/register",
            json={
                "username": "trader_caracas",
                "password": "TraderStrongPassword1!",
                "telegram_id": "6430765245",
                "google_sheet_id": "https://docs.google.com/spreadsheets/d/1TraderSheetVzla999/edit#gid=0",
            },
        )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["user"]["username"] == "trader_caracas"
    assert reg_data["user"]["role"] == "TRADER"
    assert reg_data["user"]["google_sheet_id"] == "1TraderSheetVzla999"


def test_market_spreads_and_calculator_math_simulation(sim_env):
    """3. Verifica cálculo de arbitraje en SpreadMonitor y escalado real por amount_usdt en /api/spreads/matrix."""
    app, _, _, _ = sim_env

    calc = SpreadMonitor.calculate_cycle_net_profit(
        crypto_amount=250.0,
        buy_price=1000.0,
        sell_price=1025.0,
    )
    assert calc.is_profitable is True
    assert calc.is_viable is True
    assert calc.net_profit_ves > 3500.0

    mock_quotes = [
        BankRateQuote(bank_name="Banesco", buy_rate=1000.0, sell_rate=1012.0),
        BankRateQuote(bank_name="Bancamiga", buy_rate=1002.0, sell_rate=1028.0),
    ]
    with (
        patch("src.core.spread_monitor.SpreadMonitor.fetch_live_quotes", return_value=mock_quotes),
        patch("src.reporting.bcv_service.BCVService.get_official_rate", return_value=897.54),
    ):
        mat_100 = _request(app, "GET", "/api/spreads/matrix?amount_usdt=100")
        mat_500 = _request(app, "GET", "/api/spreads/matrix?amount_usdt=500")
    assert mat_100.status_code == 200
    assert mat_500.status_code == 200
    best_100 = mat_100.json().get("best_arbitrage")
    best_500 = mat_500.json().get("best_arbitrage")
    assert best_100 is not None and best_500 is not None
    assert best_500["net_profit_ves"] == pytest.approx(best_100["net_profit_ves"] * 5.0, rel=1e-2)


def test_orders_upload_bcv_rate_fifo_vs_avg_and_authenticated_exports(sim_env):
    """4. Simula subida CSV de órdenes, verifica tasa BCV > 0, diferencia FIFO vs Promedio y exportación Bearer."""
    app, db, _, _ = sim_env

    login_res = _request(
        app,
        "POST",
        "/api/auth/login",
        json={"username": "admin_master", "password": "AdminPassword2026!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        b"Order Number,Order Type,Asset Type,Fiat Type,Total Price,Price,Quantity,Status,Created Time,Counterparty\n"
        b"ORD-1001,BUY,USDT,VES,100000.00,1000.00,100.00,Completed,2026-11-02 10:00:00,JuanVendedor\n"
        b"ORD-1002,BUY,USDT,VES,102000.00,1020.00,100.00,Completed,2026-11-03 11:00:00,MariaVendedora\n"
        b"ORD-1003,SELL,USDT,VES,105000.00,1050.00,100.00,Completed,2026-11-04 15:00:00,PedroComprador\n"
    )

    with patch("src.reporting.bcv_service.BCVService.fetch_current_rate", return_value=897.54):
        up_res = _request(
            app,
            "POST",
            "/api/orders/upload",
            headers=headers,
            files={"file": ("historial_noviembre.csv", csv_content, "text/csv")},
        )
    assert up_res.status_code == 200
    assert up_res.json()["orders_inserted"] == 3

    # Verificar que bcv_rate se guardó con la tasa oficial (897.54) y NO en 0.0
    saved_orders = db.query(Order).order_by(Order.order_number.asc()).all()
    assert len(saved_orders) == 3
    assert float(saved_orders[2].bcv_rate) == pytest.approx(897.54, rel=1e-3)

    # Comparar FIFO vs Costo Promedio (AVG) en /api/fiscal/summary
    with patch("src.reporting.bcv_service.BCVService.fetch_current_rate", return_value=897.54):
        fifo_res = _request(
            app,
            "GET",
            "/api/fiscal/summary?period=2026-11&cost_method=FIFO",
            headers=headers,
        )
        avg_res = _request(
            app,
            "GET",
            "/api/fiscal/summary?period=2026-11&cost_method=AVG",
            headers=headers,
        )

    assert fifo_res.status_code == 200
    assert avg_res.status_code == 200
    fifo_data = fifo_res.json()
    avg_data = avg_res.json()

    # FIFO: vende lote 1 (100 USDT @ 1,000 = 100,000) -> ganancia = 5,000 VES (~$5.57 USD)
    assert fifo_data["net_profit_ves"] == pytest.approx(5000.0, abs=0.05)
    assert fifo_data["net_profit_usd"] == pytest.approx(5000.0 / 897.54, abs=0.05)

    # AVG: costo promedio ((100,000 + 102,000) / 200 = 1,010) -> ganancia = 4,000 VES (~$4.46 USD)
    assert avg_data["net_profit_ves"] == pytest.approx(4000.0, abs=0.05)
    assert avg_data["net_profit_usd"] == pytest.approx(4000.0 / 897.54, abs=0.05)

    # Exportación autenticada por Bearer
    exp_xlsx = _request(app, "GET", "/api/orders/export?format=xlsx", headers=headers)
    exp_csv = _request(app, "GET", "/api/orders/export?format=csv_semicolon", headers=headers)
    assert exp_xlsx.status_code == 200
    assert exp_xlsx.content[:2] == b"PK"
    assert exp_csv.status_code == 200
    assert b"ORD-1001" in exp_csv.content


def test_accounting_ocr_hash_chain_multi_bank_and_close_month_persistence(sim_env):
    """5. Simula OCR Fail-closed, conciliación multi-banco, cadena SHA-256 lineal y cierre mensual persistente."""
    app, db, _, _ = sim_env

    login_res = _request(
        app,
        "POST",
        "/api/auth/login",
        json={"username": "admin_master", "password": "AdminPassword2026!"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Sembrar 2 órdenes completadas (Compra por Banesco y Venta por Mercantil)
    db.add_all(
        [
            Order(
                order_number="ORD-ACC-BUY",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=100000.0,
                crypto_amount=100.0,
                unit_price=1000.0,
                fee_fiat=0.0,
                fee_crypto=0.10,
                bcv_rate=897.54,
                order_status="COMPLETED",
                created_at=datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC),
            ),
            Order(
                order_number="ORD-ACC-SELL",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                fiat_amount=105000.0,
                crypto_amount=100.0,
                unit_price=1050.0,
                fee_fiat=0.0,
                fee_crypto=0.10,
                bcv_rate=897.54,
                order_status="COMPLETED",
                created_at=datetime(2026, 11, 5, 16, 0, 0, tzinfo=UTC),
            ),
        ]
    )
    db.commit()

    # 5a. Imagen inválida (no es un recibo) debe fallar Fail-closed (HTTP 400) sin ensuciar BD
    invalid_ocr = ReceiptExtractionResult(
        bank_name="",
        reference_number="",
        amount_ves=0.0,
        is_valid=False,
    )
    with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=invalid_ocr):
        bad_res = _request(
            app,
            "POST",
            "/api/accounting/vouchers/upload",
            headers=headers,
            files={"file": ("meme.jpg", b"not_a_receipt", "image/jpeg")},
        )
    assert bad_res.status_code == 400
    assert db.query(BankVoucher).count() == 0

    # 5b. Subir comprobante 1 (Compra Banesco con comisión interbancaria 300 Bs -> 3 líneas en Libro Diario)
    ocr_buy = ReceiptExtractionResult(
        is_valid=True,
        bank_name="Banesco",
        destination_bank="Mercantil",
        reference_number="99887701",
        amount_ves=100000.0,
        bank_fee_ves=300.0,
        sender_cedula="V-18999000",
        sender_name="OPERADOR P2P",
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        date_time="2026-11-05 12:05:00",
    )
    with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=ocr_buy):
        v1_res = _request(
            app,
            "POST",
            "/api/accounting/vouchers/upload",
            headers=headers,
            files={"file": ("recibo_banesco.jpg", b"valid_img_1", "image/jpeg")},
        )
    assert v1_res.status_code == 200
    assert v1_res.json()["verification_status"] == "MATCHED"

    # 5c. Subir comprobante 2 (Venta Mercantil -> 2 líneas en Libro Diario)
    ocr_sell = ReceiptExtractionResult(
        is_valid=True,
        bank_name="Banco Mercantil",
        reference_number="99887702",
        amount_ves=105000.0,
        bank_fee_ves=0.0,
        sender_cedula="V-20111222",
        sender_name="CLIENTE COMPRADOR",
        payment_method="PAGO_MOVIL",
        movement_type="CREDIT",
        date_time="2026-11-05 16:05:00",
    )
    with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=ocr_sell):
        v2_res = _request(
            app,
            "POST",
            "/api/accounting/vouchers/upload",
            headers=headers,
            files={"file": ("recibo_mercantil.jpg", b"valid_img_2", "image/jpeg")},
        )
    assert v2_res.status_code == 200
    assert v2_res.json()["verification_status"] == "MATCHED"

    # 5d. Verificar Libro Diario: Debe == Haber y cadena SHA-256 lineal perfecta sin bifurcaciones
    j_res = _request(
        app,
        "GET",
        "/api/accounting/journal?start_date=2026-11-01&end_date=2026-11-30",
        headers=headers,
    )
    assert j_res.status_code == 200
    entries_db = db.query(JournalEntry).order_by(JournalEntry.id.asc()).all()
    assert len(entries_db) == 5  # 3 líneas compra + 2 líneas venta
    assert sum(float(e.debit) for e in entries_db) == pytest.approx(sum(float(e.credit) for e in entries_db), abs=0.01)
    assert entries_db[0].prev_hash == "0" * 64
    for idx in range(1, len(entries_db)):
        assert entries_db[idx].prev_hash == entries_db[idx - 1].entry_hash

    # 5e. Verificar desglose bancario real en /api/accounting/balances/live
    live_res = _request(
        app,
        "GET",
        "/api/accounting/balances/live?year=2026&month=11&initial_usdt=500&initial_ves=200000",
        headers=headers,
    )
    assert live_res.status_code == 200
    breakdown_names = [b["bank_name"] for b in live_res.json()["bank_breakdown"]]
    assert any("Banesco" in n for n in breakdown_names)
    assert any("Mercantil" in n for n in breakdown_names)

    # 5f. Ejecutar Cierre de Mes ("CERRAR-MES") y verificar persistencia real en BD al recargar
    with patch("src.reporting.bcv_service.BCVService.fetch_current_rate", return_value=897.54):
        close_res = _request(
            app,
            "POST",
            "/api/fiscal/reconcile",
            headers=headers,
            json={
                "period": "2026-11",
                "initial_balance": 500.0,
                "actual_final_balance": 499.8,  # 500 + 100 - 100 - 0.20 fees P2P = 499.8
                "asset": "USDT",
            },
        )
    assert close_res.status_code == 200
    assert close_res.json()["total_fees"] == pytest.approx(0.20, abs=1e-4)
    assert close_res.json()["status"] == "BALANCED"

    snap_in_db = db.query(FiscalPeriodSnapshot).filter_by(period="2026-11").first()
    assert snap_in_db is not None

    snap_get = _request(app, "GET", "/api/fiscal/snapshot?period=2026-11", headers=headers)
    assert snap_get.status_code == 200
    assert snap_get.json()["is_closed"] is True


def test_telegram_bot_all_personas_commands_ocr_and_cierre_routing(sim_env):
    """6. Simula a un usuario real en Telegram como Desconocido, INVITADO, TRADER y ADMIN."""
    app, db, session_factory, _ = sim_env

    # Sembrar orden completada para probar conciliación en Telegram y /cierre
    db.add_all(
        [
            Order(
                order_number="TG-BUY-01",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=50000.0,
                crypto_amount=50.0,
                unit_price=1000.0,
                fee_fiat=0.0,
                bcv_rate=897.54,
                order_status="COMPLETED",
                created_at=datetime(2026, 10, 10, 12, 0, 0, tzinfo=UTC),
            ),
            Order(
                order_number="TG-SELL-01",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                fiat_amount=52500.0,
                crypto_amount=50.0,
                unit_price=1050.0,
                fee_fiat=0.0,
                bcv_rate=897.54,
                order_status="COMPLETED",
                created_at=datetime(2026, 10, 12, 15, 0, 0, tzinfo=UTC),
            ),
        ]
    )
    db.commit()

    notifier = TelegramNotifier(
        bot_token=TEST_BOT_TOKEN,
        default_chat_id="6326947793",
        allowed_user_ids=[6326947793],
        trader_user_ids=[6430765245],
        use_sandbox=True,
        session_factory=session_factory,
    )
    notifier.send_alert = MagicMock(return_value=True)  # type: ignore[method-assign]
    notifier.send_document = MagicMock(return_value=True)  # type: ignore[method-assign]

    with patch("src.data.database.SessionLocal", session_factory):
        # A. Admin bloquea directamente a un desconocido aún no registrado en BD (/revocar)
        rev_unknown = notifier.handle_command(user_id=6326947793, command="/revocar 999111222")
        assert "revocado" in rev_unknown.lower() or "bloqueado" in rev_unknown.lower()

        # B. Admin autoriza un INVITADO (888111222)
        auth_guest = notifier.handle_command(user_id=6326947793, command="/autorizar 888111222 INVITADO")
        assert "INVITADO" in auth_guest

        # Rol INVITADO: /estado funciona, comandos sensibles fallan Fail-closed
        assert "EN LÍNEA" in notifier.handle_command(user_id=888111222, command="/estado")
        assert "Acceso Restringido" in notifier.handle_command(user_id=888111222, command="/cierre 2026-10")
        assert "Acceso Restringido" in notifier.handle_command(user_id=888111222, command="/conciliacion 2026-10")
        assert "Acceso Restringido" in notifier.handle_command(user_id=888111222, command="/cedula V12345678")

        # C. Rol TRADER (6430765245):
        # - /estado debe funcionar igual que /status
        status_trader = notifier.handle_command(user_id=6430765245, command="/estado")
        assert "Estado del Bot" in status_trader
        assert "TRADER" in status_trader

        # - Teclado inline de TRADER no debe mostrar botones exclusivos de Admin (/pause, /resume)
        trader_markup = notifier.get_quick_actions_markup(role="TRADER")
        callbacks = [btn["callback_data"] for row in trader_markup["inline_keyboard"] for btn in row]
        assert "/pause" not in callbacks
        assert "/resume" not in callbacks

        # - Trader envía foto de comprobante que hace match con TG-BUY-01 -> crea BankVoucher Y JournalEntry
        tg_ocr = ReceiptExtractionResult(
            is_valid=True,
            bank_name="Banesco",
            reference_number="77665544",
            amount_ves=50000.0,
            bank_fee_ves=150.0,
            sender_cedula="V-15444333",
            sender_name="TRADER TELEGRAM",
            payment_method="PAGO_MOVIL",
            movement_type="DEBIT",
            date_time="2026-10-10 12:03:00",
        )
        with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=tg_ocr):
            photo_msg, vid = notifier.process_receipt_photo(b"tg_photo_bytes", user_id=6430765245)
        assert vid is not None
        assert "VINCULADO" in photo_msg
        assert db.query(JournalEntry).filter_by(voucher_id=vid).count() >= 2

        # - Trader reclasifica comprobante a CREDIT -> comisión bancaria se limpia a 0.0
        vtype_msg = notifier.handle_command(user_id=6430765245, command=f"/vtype:{vid}:CREDIT")
        assert "Venta P2P" in vtype_msg
        db.expire_all()
        updated_v = db.query(BankVoucher).filter_by(id=vid).first()
        assert updated_v is not None
        assert float(updated_v.bank_fee_ves) == 0.0

        # - Trader ejecuta /cierre 2026-10 -> el Excel debe enviarse al chat_id del Trader ("6430765245")
        cierre_resp = notifier.handle_command(user_id=6430765245, command="/cierre 2026-10")
        assert "2026-10" in cierre_resp
        assert notifier.send_document.called
        sent_kwargs = notifier.send_document.call_args.kwargs
        assert str(sent_kwargs.get("chat_id")) == "6430765245"

        # D. Admin ejecuta /pause en Telegram -> se sincroniza con GET /api/bot/status en la Web
        pause_resp = notifier.handle_command(user_id=6326947793, command="/pause")
        assert "pausadas" in pause_resp.lower()

        login_res = _request(
            app,
            "POST",
            "/api/auth/login",
            json={"username": "admin_master", "password": "AdminPassword2026!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
        bot_status_res = _request(app, "GET", "/api/bot/status", headers=headers)
        assert bot_status_res.status_code == 200
        assert bot_status_res.json()["is_paused"] is True

        notifier.handle_command(user_id=6326947793, command="/resume")
        bot_status_res2 = _request(app, "GET", "/api/bot/status", headers=headers)
        assert bot_status_res2.status_code == 200
        assert bot_status_res2.json()["is_paused"] is False
