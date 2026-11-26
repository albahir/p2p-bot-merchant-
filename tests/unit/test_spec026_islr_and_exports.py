"""Tests TDD (Rojo -> Verde) para SPEC-026:
Motor ISLR SENIAT (DPN-99025 / DPJ-99026), unificación fiscal/contable,
sincronización Binance Pay/Depósitos/Retiros, alertas de terceros y exportes oficiales.
"""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import openpyxl
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.models import BankVoucher, Base, JournalEntry, Order, User
from src.reporting.accounting_engine import AccountingEngine, LedgerSummary
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.fiscal_reconciler import FiscalReconciler
from src.reporting.pdf_reporter import PDFReporter
from src.reporting.reconciliation_engine import P2PReconciliationEngine, ReconciliationDecision
from src.reporting.sheets_exporter import SheetsExporter
from src.reporting.tax_engine import FIFOCostMethod, TradeResult

VET_TZ = timezone(timedelta(hours=-4))


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


# ---------------------------------------------------------------------------
# 1. Calculadora ISLR SENIAT (DPN-99025 / DPJ-99026) y Semáforo SPE (SNAT/2026/00099)
# ---------------------------------------------------------------------------


def test_islr_tarifa2_dpj99026_exact_seniat_validation() -> None:
    """Valida el cálculo oficial exacto de la planilla DPJ-99026 del usuario: Bs. 2.716.569,82 -> Bs. 902.133,73."""
    from src.reporting.islr_calculator import compute_islr_estimation

    est = compute_islr_estimation(
        gross_revenue_ves=3_570_546.21,
        cost_of_sales_ves=0.0,
        deductible_expenses_ves=853_976.39,
        tax_id="J507326101",
        ut_value_ves=43.0,
    )
    assert est.form_code == "DPJ-99026"
    assert est.taxpayer_type == "JURIDICA"
    assert est.net_income_ves == pytest.approx(2_716_569.82, abs=0.01)
    assert est.taxable_income_ut == pytest.approx(63_176.04, abs=0.02)
    assert est.bracket_rate == pytest.approx(0.34, abs=1e-6)
    assert est.subtrahend_ves == pytest.approx(21_500.00, abs=0.01)
    assert est.determined_tax_ves == pytest.approx(902_133.73, abs=0.01)


def test_islr_tarifa1_dpn99025_natural_person_single_deduction() -> None:
    """Persona Natural (V-/E-) aplica DPN-99025, desgravamen único 774 UT (Bs. 33.282) y rebaja 10 UT (Bs. 430)."""
    from src.reporting.islr_calculator import compute_islr_estimation

    est = compute_islr_estimation(
        gross_revenue_ves=600_000.0,
        cost_of_sales_ves=450_000.0,
        deductible_expenses_ves=10_000.0,
        tax_id="V-19456789",
        ut_value_ves=43.0,
    )
    assert est.form_code == "DPN-99025"
    assert est.taxpayer_type == "NATURAL"
    assert est.net_income_ves == pytest.approx(140_000.0, abs=0.01)
    assert est.single_deduction_ves == pytest.approx(33_282.0, abs=0.01)
    assert est.taxable_income_ves == pytest.approx(106_718.0, abs=0.01)
    assert est.personal_rebate_ves == pytest.approx(430.0, abs=0.01)
    # 106,718 / 43 = 2,481.81 UT -> Tramo >2000 a 2500 UT: 16% - 155 UT (6,665 Bs) - 430 Bs
    expected_tax = round((106_718.0 * 0.16) - (155 * 43.0) - 430.0, 2)
    assert est.determined_tax_ves == pytest.approx(expected_tax, abs=0.02)


def test_spe_threshold_evaluator_separates_real_income_from_bank_volume() -> None:
    """El semáforo SPE evalúa ingreso bruto real vs 600k/3M TCMV y jamás toma el flujo bancario rotado como ingreso."""
    from src.reporting.islr_calculator import evaluate_seniat_thresholds

    status = evaluate_seniat_thresholds(
        gross_revenue_ves=150_000.0,
        net_income_ves=45_000.0,
        bank_rotated_volume_ves=800_000_000.0,
        tcmv_rate_ves=950.0,
        tax_id="V-20111222",
    )
    assert status.islr_pn_mandatory is True  # > 1.500 UT (64.500 Bs) y > 1.000 UT neto (43.000 Bs)
    assert status.spe_interior_exceeded is False
    assert status.spe_capital_exceeded is False
    assert status.bank_volume_distinction_note != ""


# ---------------------------------------------------------------------------
# 2. Correcciones del Motor Fiscal & Contable (6 Hallazgos)
# ---------------------------------------------------------------------------


def test_tax_engine_never_falls_back_silently_to_bcv_1_0_and_flags_inventory_shortfall() -> None:
    """Prohibido bcv_rate=1.0 (convertiría Bs a USD 1:1) y venta sin stock debe advertir explícitamente."""
    dt = datetime(2026, 11, 5, 14, 0, tzinfo=UTC)
    sell_without_buy = Order(
        order_number="SELL-NO-BCV",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        crypto_amount=50.0,
        unit_price=1000.0,
        fiat_amount=50_000.0,
        fee_fiat=0.0,
        bcv_rate=0.0,  # Sin tasa
        order_status="COMPLETED",
        created_at=dt,
    )
    fifo = FIFOCostMethod()
    res = fifo.process_orders([sell_without_buy])
    assert len(res) == 1
    assert res[0].bcv_rate == 0.0
    assert res[0].net_profit_usd == 0.0  # Jamás 50,000.0 USD!
    assert len(fifo.inventory_warnings) >= 1
    assert "insuficiente" in fifo.inventory_warnings[0].lower() or "faltante" in fifo.inventory_warnings[0].lower()


def test_fiscal_reconciler_and_live_balance_unify_bank_and_crypto_fees() -> None:
    """FiscalReconciler resta comisiones bancarias en net_profit_ves y get_live_theoretical_balance resta fee_crypto."""
    db = _make_db()
    try:
        dt = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
        db.add_all(
            [
                Order(
                    order_number="ORD-U1",
                    trade_type="BUY",
                    asset="USDT",
                    fiat="VES",
                    crypto_amount=100.0,
                    unit_price=900.0,
                    fiat_amount=90_000.0,
                    fee_crypto=0.25,
                    fee_fiat=225.0,
                    bcv_rate=900.0,
                    order_status="COMPLETED",
                    created_at=dt,
                ),
                Order(
                    order_number="ORD-U2",
                    trade_type="SELL",
                    asset="USDT",
                    fiat="VES",
                    crypto_amount=100.0,
                    unit_price=950.0,
                    fiat_amount=95_000.0,
                    fee_crypto=0.25,
                    fee_fiat=237.5,
                    bcv_rate=900.0,
                    order_status="COMPLETED",
                    created_at=dt + timedelta(hours=1),
                ),
                BankVoucher(
                    bank_name="Banesco",
                    reference_number="11223344",
                    amount_ves=90_000.0,
                    bank_fee_ves=270.0,  # 0.30% Pago Móvil
                    total_debited_ves=90_270.0,
                    payment_method="PAGO_MOVIL",
                    movement_type="DEBIT",
                    associated_order_number="ORD-U1",
                    verification_status="MATCHED",
                    voucher_date=dt,
                ),
            ]
        )
        db.commit()

        fres = FiscalReconciler(db).reconcile_period("2026-11", initial_balance=10.0, initial_bcv_rate=900.0)
        # FIFO: 10 USDT iniciales @ 900 (9,000 Bs) + 90 USDT de ORD-U1 @ 902.25 (81,202.50 Bs) = 90,202.50 Bs
        # Ganancia = 95,000 - 90,202.50 - 237.50 (Binance SELL fee) - 270.00 (Bank fee 5.2.01) = 4,290.00 VES
        assert fres.net_profit_ves == pytest.approx(4290.00, abs=0.05)
        # Saldo teórico USDT: 10 + 100 - 100 - 0.50 fee_crypto = 9.50 USDT
        assert fres.calculated_final_balance == pytest.approx(9.50, abs=0.001)

        live = AccountingEngine(db).get_live_theoretical_balance(
            year=2026, month=11, initial_balances={"crypto_usdt": 10.0}
        )
        assert live.theoretical_usdt == pytest.approx(9.50, abs=0.01)
    finally:
        db.close()


def test_reconciliation_engine_real_ocr_auto_matches_and_detects_third_party() -> None:
    """ReconciliationEngine debe lograr >=90% sin requerir referencia dentro de order_number y detectar pago de tercero."""
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)

    order = Order(
        order_number="2299887766554433",  # Binance nunca incluye la ref bancaria aquí
        trade_type="SELL",
        fiat_amount=95_125.45,
        crypto_amount=100.0,
        unit_price=951.25,
        payment_method="Banesco",
        counterparty_name="CARLOS ALBERTO MENDOZA",
        order_status="COMPLETED",
        created_at=now,
    )
    voucher_same_holder = BankVoucher(
        id=1,
        bank_name="Banesco",
        reference_number="88776655",
        amount_ves=95_125.45,
        sender_name="CARLOS MENDOZA",
        payment_method="PAGO_MOVIL",
        movement_type="CREDIT",
        voucher_date=now + timedelta(minutes=4),
    )
    res_ok = engine.find_best_match(voucher_same_holder, [order])
    assert res_ok.decision == ReconciliationDecision.AUTO_MATCHED
    assert res_ok.score >= 90.0
    assert res_ok.details.get("third_party_alert") is False

    voucher_third_party = BankVoucher(
        id=2,
        bank_name="Banesco",
        reference_number="99887766",
        amount_ves=95_125.45,
        sender_name="MARIA GABRIELA RODRIGUEZ",
        payment_method="TRANSFERENCIA",
        movement_type="CREDIT",
        voucher_date=now + timedelta(minutes=10),
    )
    res_tp = engine.find_best_match(voucher_third_party, [order])
    assert res_tp.details.get("third_party_alert") is True


def test_export_context_includes_initial_inventory_cost_and_vet_journal_boundary(tmp_path: Path) -> None:
    """_build_accounting_export_context debe usar initial_usdt_cost_ves y /journal respetar fin de mes VET (22:00 VET)."""
    from src.api.routes.accounting import (
        PeriodConfigUpdateRequest,
        _build_accounting_export_context,
        get_journal_entries,
        save_period_config,
    )

    db = _make_db()
    try:
        user = User(
            username="p2p_corp",
            password_hash="x",
            full_name="IMPORTADORA ZENITH C.A.",
            tax_id="J-50732610-1",
            role="TRADER",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        save_period_config(
            payload=PeriodConfigUpdateRequest(
                year=2026,
                month=11,
                initial_usdt=100.0,
                initial_usdt_cost_ves=88_000.0,  # 880 Bs/USDT
                initial_banks={"Banesco": 50_000.0},
            ),
            db=db,
            current_user=user,
        )

        # Venta el 30/11 a las 22:00 VET (= 01/12 02:00 UTC) de los 100 USDT iniciales
        nov30_night_utc = datetime(2026, 11, 30, 22, 0, tzinfo=VET_TZ).astimezone(UTC).replace(tzinfo=None)
        db.add(
            Order(
                user_id=user.id,
                order_number="ORD-NOV30-VET",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                crypto_amount=100.0,
                unit_price=950.0,
                fiat_amount=95_000.0,
                fee_fiat=0.0,
                bcv_rate=920.0,
                order_status="COMPLETED",
                counterparty_name="Comprador Real",
                payment_method="Banesco",
                created_at=nov30_night_utc,
            )
        )
        db.add(
            JournalEntry(
                user_id=user.id,
                entry_number=1,
                date_time=nov30_night_utc,
                account_code="1.1.01",
                account_name="Banco Nacional VES - Banesco",
                debit=95_000.0,
                credit=0.0,
                reference="55667788",
                description="Ingreso Nov30 noche VET",
                order_number="ORD-NOV30-VET",
                prev_hash="0" * 64,
                entry_hash="a" * 64,
            )
        )
        db.add(
            JournalEntry(
                user_id=user.id,
                entry_number=1,
                date_time=nov30_night_utc,
                account_code="1.1.05",
                account_name="Activos Criptográficos - USDT",
                debit=0.0,
                credit=95_000.0,
                reference="55667788",
                description="Salida Nov30 noche VET",
                order_number="ORD-NOV30-VET",
                prev_hash="a" * 64,
                entry_hash="b" * 64,
            )
        )
        db.commit()

        # 1. Contexto debe asignar acquisition_cost = 88,000 Bs (NO 0 Bs!)
        ctx = _build_accounting_export_context(db, user, 2026, 11)
        assert len(ctx["tax_results"]) == 1
        assert ctx["tax_results"][0].acquisition_cost_fiat == pytest.approx(88_000.0, abs=0.01)
        assert ctx["tax_results"][0].net_profit_fiat == pytest.approx(7_000.0, abs=0.01)

        # 2. Consulta visual Libro Diario con rango VET 2026-11-01..2026-11-30 debe incluir las 22:00 VET (02:00 UTC dic-01)
        j_list = get_journal_entries(
            db=db,
            current_user=user,
            start_date="2026-11-01",
            end_date="2026-11-30",
        )
        assert len(j_list) == 2
        assert j_list[0].date_time.startswith("2026-11-30 22:00")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Exportaciones SENIAT (Excel, PDF, Órdenes, Google Sheets)
# ---------------------------------------------------------------------------


def test_excel_and_pdf_include_dpj_or_dpn_worksheets_and_corrected_igtf(tmp_path: Path) -> None:
    """Excel debe incluir 'Resumen Ejecutivo SENIAT' y PDF debe corregir texto IGTF 0% e incluir DPN/DPJ."""
    dt_utc = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    tax_results = [
        TradeResult(
            order_number="ORD-1",
            trade_type="SELL",
            crypto_amount=100.0,
            sell_price_fiat=1000.0,
            total_revenue_fiat=100_000.0,
            acquisition_cost_fiat=80_000.0,
            fee_fiat=250.0,
            net_profit_fiat=19_750.0,
            bcv_rate=900.0,
            net_profit_usd=21.94,
            created_at=dt_utc,
        )
    ]
    orders = [
        Order(
            order_number="ORD-0",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            crypto_amount=100.0,
            unit_price=800.0,
            fiat_amount=80_000.0,
            fee_fiat=0.0,
            bcv_rate=900.0,
            order_status="COMPLETED",
            counterparty_name="Proveedor Uno",
            payment_method="Banesco",
            created_at=dt_utc - timedelta(hours=2),
        ),
        Order(
            order_number="ORD-1",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            crypto_amount=100.0,
            unit_price=1000.0,
            fiat_amount=100_000.0,
            fee_fiat=250.0,
            bcv_rate=900.0,
            order_status="COMPLETED",
            counterparty_name="Cliente Uno",
            payment_method="Mercantil",
            created_at=dt_utc,
        ),
    ]
    ledgers = [
        LedgerSummary(
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            year=2026,
            month=11,
            initial_balance=50_000.0,
            total_debit=100_000.0,
            total_credit=80_000.0,
            final_balance=70_000.0,
            entries_count=2,
        )
    ]

    xlsx_path = str(tmp_path / "resumen_seniat.xlsx")
    ExcelReporter.generate_accounting_report(
        journal_entries=[],
        ledger_summaries=ledgers,
        vouchers=[],
        output_path=xlsx_path,
        tax_results=tax_results,
        orders=orders,
        account_holder="IMPORTADORA ZENITH C.A.",
        rif="J-50732610-1",
        period="2026-11",
        bcv_rate=900.0,
        cost_method="FIFO",
    )

    wb = openpyxl.load_workbook(xlsx_path)
    assert "Resumen Ejecutivo SENIAT" in wb.sheetnames
    df_exec = pd.read_excel(xlsx_path, sheet_name="Resumen Ejecutivo SENIAT")
    flat_text = " ".join(str(v) for row in df_exec.values for v in row if pd.notna(v))
    assert "DPJ-99026" in flat_text
    assert "Papel de trabajo contable" in flat_text
    assert "703" in flat_text and "763" in flat_text

    # Órdenes export debe traer Banco / Método de Pago
    df_orders = BinanceHistorySyncer.generate_orders_df(orders)
    assert "Banco / Método de Pago" in df_orders.columns
    assert df_orders.iloc[0]["Banco / Método de Pago"] == "Banesco"

    # PDF debe corregir texto IGTF ("alicuota del 0%") e incluir bloque DPJ/DPN
    pdf_path = str(tmp_path / "seniat.pdf")
    PDFReporter(company_name="IMPORTADORA ZENITH C.A.", rif="J-50732610-1").generate_accounting_pdf(
        journal_entries=[],
        ledger_summaries=ledgers,
        vouchers=[],
        output_path=pdf_path,
        tax_results=tax_results,
        orders=orders,
        period="2026-11",
        bcv_rate=900.0,
    )
    pdf_bytes = Path(pdf_path).read_bytes()
    assert b"alicuota del 0%" in pdf_bytes
    assert b"exentas del 3%" not in pdf_bytes
    assert b"DPJ-99026" in pdf_bytes


def test_sheets_exporter_uses_vet_timezone_and_omits_raw_hash() -> None:
    """export_accounting en Sheets debe usar Fecha y Hora (VET) y no exponer la columna técnica Hash SHA-256."""
    dt_utc = datetime(2026, 11, 15, 2, 30, 0, tzinfo=UTC)  # 2026-11-14 22:30:00 VET
    entries = [
        JournalEntry(
            entry_number=1,
            date_time=dt_utc,
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            debit=1000.0,
            credit=0.0,
            reference="998877",
            description="Venta USDT",
            order_number="ORD-99",
            entry_hash="a" * 64,
        )
    ]
    mock_sh = MagicMock()
    ws_diario = MagicMock()
    ws_mayor = MagicMock()
    ws_diario.title = "Libro Diario"
    ws_mayor.title = "Libro Mayor"
    mock_sh.worksheets.return_value = [ws_diario, ws_mayor]
    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_sh

    exp = SheetsExporter(credentials_json={"type": "service_account"})
    exp._get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]
    ok = exp.export_accounting(sheet_id="s1", journal_entries=entries, ledger_summaries=[])
    assert ok is True

    written = ws_diario.append_rows.call_args[0][0]
    assert "Hash SHA-256" not in written[0]
    assert any("VET" in str(h) for h in written[0])
    assert written[1][1] == "2026-11-14 22:30:00"


def test_binance_pay_deposits_withdrawals_sync_and_spot_permission_fallback(monkeypatch) -> None:
    """sync_binance_pay_movements debe sincronizar Pay + Depósitos + Salidas/Retiros Binance e tolerar falta de permisos Spot."""

    from config.settings import Settings
    from src.api.routes import accounting as acct_mod
    from src.api.routes.accounting import SyncBinancePayRequest, sync_binance_pay_movements
    from src.core.binance_client import BinanceAuthError

    acct_mod._BINANCE_PAY_SYNC_COOLDOWN.clear()
    db = _make_db()
    try:
        user = User(username="sync_trader", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        fake_settings = Settings()

        # Mock ApiKeyManager y BinanceP2PClient
        class FakeKM:
            def __init__(self, *args, **kwargs):
                pass

            def get_secret(self, key_name: str) -> str:
                return "A" * 64 if "api_key" in key_name else "B" * 64

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def get_pay_transactions(self, **kwargs):
                return [
                    {
                        "transactionId": "PAY9001",
                        "currency": "USDT",
                        "amount": "25.0",
                        "orderType": "C2C",
                        "transactionTime": int(datetime(2026, 11, 10, 14, 0, tzinfo=UTC).timestamp() * 1000),
                        "payerInfo": {"name": "Luis", "binanceId": "12345"},
                    }
                ]

            def get_deposit_history(self, **kwargs):
                return [
                    {
                        "id": "DEP5001",
                        "coin": "USDT",
                        "amount": "100.0",
                        "network": "TRC20",
                        "txId": "tx_dep_5001",
                        "address": "TWalletXYZ",
                        "insertTime": int(datetime(2026, 11, 11, 15, 0, tzinfo=UTC).timestamp() * 1000),
                    }
                ]

            def get_withdraw_history(self, **kwargs):
                return [
                    {
                        "id": "WDR7001",
                        "coin": "USDT",
                        "amount": "40.0",
                        "transactionFee": "1.0",
                        "network": "TRC20",
                        "txId": "tx_wdr_7001",
                        "address": "TOutWallet",
                        "applyTime": "2026-11-12 16:00:00",
                    }
                ]

        monkeypatch.setattr("src.security.api_key_manager.ApiKeyManager", FakeKM)
        monkeypatch.setattr("src.core.binance_client.BinanceP2PClient", FakeClient)

        res = sync_binance_pay_movements(
            payload=SyncBinancePayRequest(year=2026, month=11, include_spot_transfers=True),
            db=db,
            current_user=user,
            settings=fake_settings,
        )
        assert res.success is True
        assert res.inserted == 3
        assert res.pay_count == 1
        assert res.deposits_count == 1
        assert res.withdrawals_count == 1

        # Verificar saldo en vivo incluye +125 entradas (25 Pay + 100 Dep) y -41 salidas (40 + 1 fee)
        live = AccountingEngine(db, user_id=int(user.id)).get_live_theoretical_balance(year=2026, month=11)
        assert live.other_inflow_usdt == pytest.approx(125.0, abs=0.01)
        assert live.other_outflow_usdt == pytest.approx(41.0, abs=0.01)
        assert live.theoretical_usdt == pytest.approx(84.0, abs=0.01)

        # Limpiar cooldown y validar tolerancia cuando Spot retiros/depósitos da error 403
        acct_mod._BINANCE_PAY_SYNC_COOLDOWN.clear()

        class FakePayOnlyClient(FakeClient):
            def get_pay_transactions(self, **kwargs):
                return [
                    {
                        "transactionId": "PAY9002",
                        "currency": "USDT",
                        "amount": "-10.0",
                        "orderType": "PAY",
                        "transactionTime": int(datetime(2026, 11, 13, 14, 0, tzinfo=UTC).timestamp() * 1000),
                    }
                ]

            def get_deposit_history(self, **kwargs):
                raise BinanceAuthError("Sin permiso spot")

            def get_withdraw_history(self, **kwargs):
                raise BinanceAuthError("Sin permiso retiros")

        monkeypatch.setattr("src.core.binance_client.BinanceP2PClient", FakePayOnlyClient)
        res2 = sync_binance_pay_movements(
            payload=SyncBinancePayRequest(year=2026, month=11, include_spot_transfers=True),
            db=db,
            current_user=user,
            settings=fake_settings,
        )
        assert res2.success is True
        assert res2.pay_count == 1
        assert len(res2.warnings) == 2
    finally:
        db.close()
