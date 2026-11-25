"""Pruebas TDD para:
1. Ocultamiento del prefijo del token del bot de Telegram para rol TRADER (solo visible para ADMIN).
2. Fecha de inicio de corte por período contable (usuarios nuevos a mitad de mes).
3. Movimientos USDT no-P2P (Binance Pay / Binance ID / Depósitos / Retiros): CRUD aislado,
   sincronización idempotente con cooldown, integración en saldo en vivo, Kardex y reportes Excel/PDF
   sin inflar la base imponible ISLR (venezuela-tax-cpa).
"""

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import openpyxl
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.routes.accounting import (
    PeriodConfigUpdateRequest,
    _build_accounting_export_context,
    get_live_balance,
    get_period_config,
    save_period_config,
)
from src.api.routes.settings import get_telegram_status
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.models import Base, Order, User, WalletMovement
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.bcv_history_service import BCVHistoryService
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.fiscal_reconciler import FiscalReconciler
from src.reporting.pdf_reporter import PDFReporter
from src.security.api_key_manager import ApiKeyManager

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _make_user(db, username: str, role: str = "TRADER", tax_id: str = "V-25111222") -> User:
    u = User(
        username=username,
        password_hash="hashed",
        full_name=f"Usuario {username}",
        tax_id=tax_id,
        role=role,
        is_active=True,
        preferred_banks_json='["Banesco"]',
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_telegram_status_hides_bot_token_mask_for_trader() -> None:
    """TRADER solo ve 'Activo' sin prefijo ni sufijo del token del bot; ADMIN mantiene el diagnóstico enmascarado."""
    db = _make_session()
    try:
        test_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            TELEGRAM_BOT_TOKEN="8801234567:AAHTestSuperSecretTokenValue123456789",
        )
        admin = _make_user(db, "admin_tg", role="ADMIN")
        trader = _make_user(db, "trader_tg", role="TRADER")

        res_trader = get_telegram_status(current_user=trader, settings=test_settings)
        assert res_trader.is_configured is True
        assert res_trader.bot_token_masked == "Activo"
        assert "880" not in res_trader.bot_token_masked
        assert "AAH" not in res_trader.bot_token_masked

        res_admin = get_telegram_status(current_user=admin, settings=test_settings)
        assert res_admin.is_configured is True
        assert "880••••" in res_admin.bot_token_masked
    finally:
        db.close()


def test_period_cutoff_start_date_filters_sync_live_balance_fiscal_and_exports() -> None:
    """Un usuario que empieza el 25 de noviembre solo contabiliza, sincroniza y exporta desde el 25/11 VET."""
    db = _make_session()
    try:
        BCVHistoryService(db).seed_historical_rates_if_missing()
        user = _make_user(db, "nuevo_nov25", role="TRADER")

        saved = save_period_config(
            payload=PeriodConfigUpdateRequest(
                year=2026,
                month=11,
                cutoff_start_date="2026-11-25",
                initial_usdt=100.0,
                initial_usdt_cost_ves=91982.27,
                initial_banks={"Banesco": 50000.0},
            ),
            db=db,
            current_user=user,
        )
        assert saved.cutoff_start_date == "2026-11-25"
        assert abs(saved.bcv_day1_rate - 919.8227) < 0.01

        vet_tz = timezone(timedelta(hours=-4))
        dt_before = datetime(2026, 11, 10, 14, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        dt_after = datetime(2026, 11, 25, 10, 30, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)

        db.add(
            Order(
                user_id=user.id,
                order_number="OLD_NOV10",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=90000.0,
                crypto_amount=100.0,
                unit_price=900.0,
                fee_fiat=0.0,
                fee_crypto=0.0,
                bcv_rate=895.0,
                order_status="COMPLETED",
                created_at=dt_before,
            )
        )
        db.add(
            Order(
                user_id=user.id,
                order_number="NEW_NOV25",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=55000.0,
                crypto_amount=50.0,
                unit_price=1100.0,
                fee_fiat=0.0,
                fee_crypto=0.0,
                bcv_rate=919.8227,
                order_status="COMPLETED",
                created_at=dt_after,
            )
        )
        db.commit()

        cfg = get_period_config(year=2026, month=11, db=db, current_user=user)
        assert cfg.orders_count_in_period == 1

        engine = AccountingEngine(db=db, user_id=int(user.id))
        live = engine.get_live_theoretical_balance(
            year=2026,
            month=11,
            initial_balances={"crypto_usdt": 100.0, "banks": {"Banesco": 50000.0}},
            cutoff_start_date=date(2026, 11, 25),
        )
        assert live.inflow_usdt == 50.0
        assert live.theoretical_usdt == 150.0

        reconciler = FiscalReconciler(db_session=db, user_id=int(user.id))
        fres = reconciler.reconcile_period(
            period="2026-11",
            initial_balance=100.0,
            initial_bcv_rate=919.8227,
            cutoff_start_date=date(2026, 11, 25),
        )
        assert fres.orders_count == 1
        assert fres.inflows_p2p_buys == 50.0
        assert fres.calculated_final_balance == 150.0

        ctx = _build_accounting_export_context(db, user, 2026, 11)
        assert [o.order_number for o in ctx["orders"]] == ["NEW_NOV25"]

        captured_starts: list[int] = []

        class SpyClient:
            def get_order_history(
                self, trade_type: str, start_timestamp: int, end_timestamp: int, page: int = 1, rows: int = 50
            ) -> Any:
                captured_starts.append(start_timestamp)
                return SimpleNamespace(data=[])

        expected_min_ms = int(datetime(2026, 11, 25, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC).timestamp() * 1000)
        BinanceHistorySyncer().sync_orders(
            client=SpyClient(),
            db=db,
            year=2026,
            month=11,
            start_date=date(2026, 11, 25),
            user_id=int(user.id),
        )
        assert captured_starts
        assert min(captured_starts) == expected_min_ms
    finally:
        db.close()


def test_wallet_movements_crud_idor_protection_live_balance_and_exports(tmp_path: Path) -> None:
    """CRUD de movimientos USDT (Binance Pay / Depósito / Retiro) aislado por usuario, reflejado en saldo y Kardex sin inflar ISLR."""
    from src.api.routes.accounting import (
        CreateWalletMovementRequest,
        create_wallet_movement,
        delete_wallet_movement,
        list_wallet_movements,
    )

    db = _make_session()
    try:
        trader_a = _make_user(db, "trader_a_wm", role="TRADER")
        trader_b = _make_user(db, "trader_b_wm", role="TRADER")

        r_in = create_wallet_movement(
            payload=CreateWalletMovementRequest(
                movement_type="DEPOSIT",
                asset="USDT",
                amount=50.0,
                fee=0.0,
                channel="BINANCE_PAY",
                counterparty="cliente@correo.com",
                note="Recibido por Binance ID",
                date_vet="2026-11-25",
            ),
            db=db,
            current_user=trader_a,
        )
        assert r_in.amount == 50.0
        in_id = r_in.id

        r_out = create_wallet_movement(
            payload=CreateWalletMovementRequest(
                movement_type="WITHDRAWAL",
                asset="USDT",
                amount=10.0,
                fee=1.0,
                channel="TRC20",
                counterparty="TAddress123",
                note="Retiro a wallet fría",
                date_vet="2026-11-25",
            ),
            db=db,
            current_user=trader_a,
        )
        assert r_out.amount == 10.0

        list_a = list_wallet_movements(db=db, current_user=trader_a, year=2026, month=11)
        assert len(list_a) == 2

        list_b = list_wallet_movements(db=db, current_user=trader_b, year=2026, month=11)
        assert len(list_b) == 0

        # Protección IDOR: Trader B no puede eliminar un movimiento de Trader A
        with pytest.raises(HTTPException) as exc_info:
            delete_wallet_movement(movement_id=in_id, db=db, current_user=trader_b)
        assert exc_info.value.status_code == 404

        live_res = get_live_balance(
            db=db,
            current_user=trader_a,
            year=2026,
            month=11,
            initial_usdt=0.0,
            initial_ves=0.0,
        )
        assert live_res.other_inflow_usdt == 50.0
        assert live_res.other_outflow_usdt == 11.0
        assert live_res.theoretical_usdt == 39.0

        ctx = _build_accounting_export_context(db, trader_a, 2026, 11)
        assert len(ctx["wallet_movements"]) == 2

        xlsx_path = str(tmp_path / "kardex_pay.xlsx")
        ExcelReporter.generate_accounting_report(
            journal_entries=ctx["entries"],
            ledger_summaries=ctx["ledgers"],
            vouchers=ctx["vouchers"],
            output_path=xlsx_path,
            tax_results=ctx["tax_results"],
            orders=ctx["orders"],
            wallet_movements=ctx["wallet_movements"],
            account_holder=ctx["account_holder"],
            rif=ctx["tax_id"],
            period=ctx["period"],
            bcv_rate=919.8227,
            initial_usdt=0.0,
            initial_usdt_cost_ves=0.0,
            initial_ves=0.0,
        )
        wb = openpyxl.load_workbook(xlsx_path)
        ws_er = wb["Estado de Resultados"]
        er_map = {ws_er.cell(r, 1).value: ws_er.cell(r, 2).value for r in range(2, ws_er.max_row + 1)}
        assert er_map["(=) Enriquecimiento Neto Gravable ISLR"] == 0.0

        ws_k = wb["Kardex Inventario USDT"]
        k_map = {ws_k.cell(r, 1).value: ws_k.cell(r, 2).value for r in range(2, ws_k.max_row + 1)}
        assert k_map["(=) Inventario Final USDT"] == 39.0

        pdf_path = str(tmp_path / "kardex_pay.pdf")
        PDFReporter(company_name="Trader A", rif="V-12345678").generate_accounting_pdf(
            journal_entries=ctx["entries"],
            ledger_summaries=ctx["ledgers"],
            vouchers=ctx["vouchers"],
            output_path=pdf_path,
            tax_results=ctx["tax_results"],
            orders=ctx["orders"],
            wallet_movements=ctx["wallet_movements"],
            period="2026-11",
            bcv_rate=919.8227,
            initial_usdt=0.0,
            initial_usdt_cost_ves=0.0,
            initial_ves=0.0,
        )
        pdf_bytes = Path(pdf_path).read_bytes()
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"39.0000 USDT" in pdf_bytes

        del_ok = delete_wallet_movement(movement_id=in_id, db=db, current_user=trader_a)
        assert del_ok["deleted"] is True
        assert db.query(WalletMovement).filter(WalletMovement.id == in_id).first() is None
    finally:
        db.close()


def test_sync_binance_pay_idempotent_and_respects_cooldown() -> None:
    """Sincroniza Binance Pay (entradas positivas, salidas negativas) idempotentemente y aplica cooldown de 60s."""
    from src.api.routes.accounting import (
        _BINANCE_PAY_SYNC_COOLDOWN,
        SyncBinancePayRequest,
        sync_binance_pay_movements,
    )

    db = _make_session()
    try:
        trader = _make_user(db, "trader_pay", role="TRADER")
        _BINANCE_PAY_SYNC_COOLDOWN.clear()

        test_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
        )
        factory = sessionmaker(bind=db.get_bind())
        km = ApiKeyManager(master_key=TEST_SECRET, db_session_factory=factory)
        km.store_secret(f"user_{trader.id}:binance_api_key", "vm4Pabcd1234567890efghXk9b")
        km.store_secret(f"user_{trader.id}:binance_private_key", "SecretPayload1234567890SecretPayload!")

        vet_tz = timezone(timedelta(hours=-4))
        ts_ms = int(datetime(2026, 11, 25, 11, 0, tzinfo=vet_tz).astimezone(UTC).timestamp() * 1000)
        mock_pay_rows = [
            {
                "orderId": "PAY_ORD_1",
                "transactionId": "TX_IN_001",
                "transactionTime": ts_ms,
                "amount": "75.50",
                "currency": "USDT",
                "orderType": "C2C",
                "payerInfo": {"name": "Juan Perez", "binanceId": "11223344"},
                "note": "Envio por Binance ID",
            },
            {
                "orderId": "PAY_ORD_2",
                "transactionId": "TX_OUT_002",
                "transactionTime": ts_ms + 5000,
                "amount": "-20.00",
                "currency": "USDT",
                "orderType": "PAY",
                "receiverInfo": {"name": "Proveedor", "binanceId": "55667788"},
                "note": "Pago servicio",
            },
        ]

        with patch("src.core.binance_client.BinanceP2PClient.get_pay_transactions", return_value=mock_pay_rows):
            res1 = sync_binance_pay_movements(
                payload=SyncBinancePayRequest(year=2026, month=11),
                db=db,
                current_user=trader,
                settings=test_settings,
            )
            assert res1.inserted == 2
            assert res1.existing == 0

            # Segunda llamada inmediata -> bloqueada por cooldown (429) para proteger UID weight 3000
            with pytest.raises(HTTPException) as exc_cd:
                sync_binance_pay_movements(
                    payload=SyncBinancePayRequest(year=2026, month=11),
                    db=db,
                    current_user=trader,
                    settings=test_settings,
                )
            assert exc_cd.value.status_code == 429

            # Tras vencer cooldown -> 100% idempotente (0 nuevos, 2 existentes)
            _BINANCE_PAY_SYNC_COOLDOWN.clear()
            res2 = sync_binance_pay_movements(
                payload=SyncBinancePayRequest(year=2026, month=11),
                db=db,
                current_user=trader,
                settings=test_settings,
            )
            assert res2.inserted == 0
            assert res2.existing == 2

        rows = db.query(WalletMovement).filter(WalletMovement.user_id == trader.id).all()
        assert len(rows) == 2
        by_type = {str(m.movement_type): float(m.amount) for m in rows}
        assert by_type["DEPOSIT"] == 75.50
        assert by_type["WITHDRAWAL"] == 20.00
    finally:
        db.close()
