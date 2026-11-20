"""Tests TDD para cumplimiento tributario y contable venezolano en exportaciones (venezuela-tax-cpa)."""

from datetime import UTC, datetime

import openpyxl
import pandas as pd

from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.models import BankVoucher, JournalEntry, Order
from src.reporting.accounting_engine import LedgerSummary
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.pdf_reporter import PDFReporter
from src.reporting.tax_engine import TradeResult


def test_seniat_excel_calculates_real_islr_net_income_not_cashflow(tmp_path):
    """LISLR Art. 1/4/27: la base imponible debe venir de ventas - costo PEPS - gastos, nunca de flujo 1.1.01."""
    dt_utc = datetime(2026, 11, 4, 1, 0, 0, tzinfo=UTC)  # 2026-11-03 21:00 VET

    # Banco tuvo salidas por 15.000 Bs (compra grande) y entradas por 6.000 Bs (venta parcial) -> flujo caja -9.000
    entries = [
        JournalEntry(
            entry_number=1,
            date_time=dt_utc,
            account_code="1.1.05",
            account_name="Activos Criptográficos - USDT",
            debit=15000.0,
            credit=0.0,
            reference="00011223",
            description="Compra 300 USDT",
            order_number="20261103000111222333",
            entry_hash="a" * 64,
        ),
        JournalEntry(
            entry_number=1,
            date_time=dt_utc,
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            debit=0.0,
            credit=15000.0,
            reference="00011223",
            description="Egreso compra",
            order_number="20261103000111222333",
            entry_hash="b" * 64,
        ),
        JournalEntry(
            entry_number=2,
            date_time=dt_utc,
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            debit=6000.0,
            credit=0.0,
            reference="00099887",
            description="Venta 100 USDT",
            order_number="20261103000999888777",
            entry_hash="c" * 64,
        ),
        JournalEntry(
            entry_number=2,
            date_time=dt_utc,
            account_code="5.2.01",
            account_name="Gastos Financieros - Comisiones Bancarias",
            debit=18.0,
            credit=0.0,
            reference="00099887",
            description="Comisión Pago Móvil",
            order_number="20261103000999888777",
            entry_hash="d" * 64,
        ),
        JournalEntry(
            entry_number=2,
            date_time=dt_utc,
            account_code="1.1.05",
            account_name="Activos Criptográficos - USDT",
            debit=0.0,
            credit=6018.0,
            reference="00099887",
            description="Descargo inventario",
            order_number="20261103000999888777",
            entry_hash="e" * 64,
        ),
    ]

    tax_results = [
        TradeResult(
            order_number="20261103000999888777",
            trade_type="SELL",
            crypto_amount=100.0,
            sell_price_fiat=60.0,
            total_revenue_fiat=6000.0,
            acquisition_cost_fiat=5000.0,
            fee_fiat=0.0,
            net_profit_fiat=1000.0,
            bcv_rate=50.0,
            net_profit_usd=20.0,
            created_at=dt_utc,
        )
    ]

    orders = [
        Order(
            order_number="20261103000111222333",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            crypto_amount=300.0,
            unit_price=50.0,
            fiat_amount=15000.0,
            fee_fiat=0.0,
            order_status="COMPLETED",
            bcv_rate=50.0,
            created_at=dt_utc,
        ),
        Order(
            order_number="20261103000999888777",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            crypto_amount=100.0,
            unit_price=60.0,
            fiat_amount=6000.0,
            fee_fiat=0.0,
            order_status="COMPLETED",
            bcv_rate=50.0,
            created_at=dt_utc,
        ),
    ]

    vouchers = [
        BankVoucher(
            id=1,
            bank_name="Banesco",
            destination_bank="Mercantil",
            reference_number="00011223",
            amount_ves=15000.0,
            bank_fee_ves=0.0,
            total_debited_ves=15000.0,
            sender_id="V-12345678",
            payment_method="TRANSFER",
            movement_type="DEBIT",
            verification_status="MATCHED",
            voucher_date=dt_utc,
        )
    ]

    ledgers = [
        LedgerSummary(
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            year=2026,
            month=11,
            initial_balance=20000.0,
            total_debit=6000.0,
            total_credit=15000.0,
            final_balance=11000.0,
            entries_count=2,
        )
    ]

    out = str(tmp_path / "seniat_peps.xlsx")
    ExcelReporter.generate_accounting_report(
        journal_entries=entries,
        ledger_summaries=ledgers,
        vouchers=vouchers,
        output_path=out,
        tax_results=tax_results,
        orders=orders,
        account_holder="Carlos Mendoza",
        rif="V-12345678-0",
        period="2026-11",
        bcv_rate=50.0,
    )

    wb = openpyxl.load_workbook(out)
    assert "Estado de Resultados" in wb.sheetnames
    assert "Kardex Inventario USDT" in wb.sheetnames

    df_seniat = pd.read_excel(out, sheet_name="Liquidación Fiscal SENIAT")
    metrics = dict(zip(df_seniat["Concepto Fiscal"], df_seniat["Monto (VES)"], strict=False))

    # Debe reportar ingresos reales por ventas (6000) y enriquecimiento neto positivo (1000 - 18 = 982), no flujo de caja (-9000)
    assert float(metrics["Ingresos Brutos por Ventas (VES)"]) == 6000.0
    assert float(metrics["Costo de Ventas PEPS (VES)"]) == 5000.0
    assert float(metrics["Gastos Financieros Deducibles - Comisiones Bancarias (VES)"]) == 18.0
    assert float(metrics["Enriquecimiento Neto Gravable ISLR (VES)"]) == 982.0

    # El Libro Diario debe estar en hora VET (2026-11-03 21:00:00) y terminar con SUMAS IGUALES
    ws_diario = wb["Libro Diario"]
    headers = [cell.value for cell in ws_diario[1]]
    assert any("VET" in str(h) for h in headers)
    last_row_vals = [cell.value for cell in ws_diario[ws_diario.max_row]]
    assert "SUMAS IGUALES" in [str(v) for v in last_row_vals if v]

    # Referencia con ceros iniciales conservada como texto
    assert ws_diario.cell(row=2, column=headers.index("Referencia") + 1).value == "00011223"

    # Kardex debe mostrar 300 comprados, 100 vendidos, 200 final
    df_kardex = pd.read_excel(out, sheet_name="Kardex Inventario USDT")
    kardex_map = dict(zip(df_kardex["Concepto"], df_kardex["Cantidad (USDT)"], strict=False))
    assert float(kardex_map["(+) Compras P2P USDT"]) == 300.0
    assert float(kardex_map["(-) Ventas P2P USDT"]) == 100.0
    assert float(kardex_map["(=) Inventario Final USDT"]) == 200.0


def test_pdf_reporter_multipage_without_15_entry_truncation(tmp_path):
    """Un Libro Diario legal en PDF no puede truncar en [:15]; debe paginar todos los asientos y sumar Debe=Haber."""
    now_utc = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
    entries = [
        JournalEntry(
            entry_number=i,
            date_time=now_utc,
            account_code="1.1.01" if i % 2 else "1.1.05",
            account_name="Banco Nacional VES" if i % 2 else "USDT",
            debit=100.0 if i % 2 else 0.0,
            credit=0.0 if i % 2 else 100.0,
            reference=f"000{i:04d}",
            description=f"Asiento operativo numero {i}",
            order_number=f"ORD-{i}",
            entry_hash="f" * 64,
        )
        for i in range(1, 51)  # 50 asientos (> 1 página)
    ]

    tax_results = [
        TradeResult(
            order_number="ORD-2",
            trade_type="SELL",
            crypto_amount=10.0,
            sell_price_fiat=55.0,
            total_revenue_fiat=550.0,
            acquisition_cost_fiat=500.0,
            fee_fiat=0.0,
            net_profit_fiat=50.0,
            bcv_rate=50.0,
            net_profit_usd=1.0,
            created_at=now_utc,
        )
    ]

    out_pdf = str(tmp_path / "libro_multipagina.pdf")
    reporter = PDFReporter(company_name="COMERCIO CARACAS C.A.", rif="J-40111222-3")
    reporter.generate_accounting_pdf(
        journal_entries=entries,
        ledger_summaries=[],
        vouchers=[],
        output_path=out_pdf,
        tax_results=tax_results,
        period="2026-11",
    )

    with open(out_pdf, "rb") as f:
        raw = f.read()
    assert b"/Count 1" not in raw  # Debe tener más de 1 página
    assert b"#50" in raw  # El asiento 50 debe aparecer (sin corte [:15])
    assert b"SUMAS IGUALES" in raw
    assert b"VET" in raw
    assert b"ESTADO DE RESULTADOS" in raw


def test_orders_excel_includes_vet_timezone_and_bcv_values():
    """La descarga de órdenes debe incluir hora legal VET (UTC-4) y tasa/valor BCV oficial."""
    dt_utc = datetime(2026, 11, 1, 2, 0, tzinfo=UTC)  # 2026-10-31 22:00:00 VET
    orders = [
        Order(
            order_number="20261031000123456789",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            crypto_amount=100.0,
            unit_price=55.0,
            fiat_amount=5500.0,
            fee_crypto=0.0,
            fee_fiat=0.0,
            bcv_rate=50.0,
            order_status="COMPLETED",
            counterparty_name="TraderVE",
            created_at=dt_utc,
        )
    ]

    df = BinanceHistorySyncer.generate_orders_df(orders)
    assert "Fecha y Hora (VET)" in df.columns
    assert "Tasa BCV (VES/USD)" in df.columns
    assert "Equivalente USD (BCV)" in df.columns
    assert df.iloc[0]["Fecha y Hora (VET)"] == "2026-10-31 22:00:00"
    assert float(df.iloc[0]["Tasa BCV (VES/USD)"]) == 50.0
    assert float(df.iloc[0]["Equivalente USD (BCV)"]) == 110.0


def test_user_tax_id_supports_cedula_and_rif_and_propagates_to_reports(tmp_path):
    """El sistema debe aceptar Cédula (natural) o RIF (jurídico/personal) y estamparlo en Excel y PDF."""
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.api.routes.accounting import export_accounting_excel, export_accounting_pdf
    from src.api.routes.auth import _validate_and_normalize_tax_id, update_recovery_profile
    from src.api.schemas.auth import RecoveryProfileUpdateRequest
    from src.data.database import Base
    from src.data.repositories import UserRepository

    assert _validate_and_normalize_tax_id("v-19456789") == "V-19456789"
    assert _validate_and_normalize_tax_id("19456789") == "V-19456789"
    assert _validate_and_normalize_tax_id("j-40123456-7") == "J-40123456-7"
    with pytest.raises(HTTPException) as exc:
        _validate_and_normalize_tax_id("<script>alert(1)</script>")
    assert exc.value.status_code == 422

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = UserRepository(db).create_user(
            username="comerciante_ve",
            password_hash="x",
            role="TRADER",
            full_name="María Rodríguez",
        )
        res = update_recovery_profile(
            req=RecoveryProfileUpdateRequest(tax_id="V-20111222"),
            db=db,
            current_user=user,
        )
        assert res["user"].tax_id == "V-20111222"

        excel_resp = export_accounting_excel(db=db, current_user=user, year=2026, month=11)
        df_seniat = pd.read_excel(excel_resp.path, sheet_name="Liquidación Fiscal SENIAT")
        metrics = dict(zip(df_seniat["Concepto Fiscal"], df_seniat["Monto (VES)"], strict=False))
        assert metrics["Cédula / RIF"] == "V-20111222"

        pdf_resp = export_accounting_pdf(db=db, current_user=user, year=2026, month=11)
        with open(pdf_resp.path, "rb") as f:
            pdf_bytes = f.read()
        assert b"V-20111222" in pdf_bytes
    finally:
        db.close()
