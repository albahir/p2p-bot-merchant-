"""Tests unitarios (TDD) para los Exportadores Contables: Excel, PDF y Google Sheets (SPEC-017)."""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.data.models import BankVoucher, JournalEntry
from src.reporting.accounting_engine import LedgerSummary
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.pdf_reporter import PDFReporter
from src.reporting.sheets_exporter import SheetsExporter


def sample_accounting_data():
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    entries = [
        JournalEntry(
            id=1,
            entry_number=1,
            date_time=now,
            account_code="1.1.05",
            account_name="Activos Criptográficos - USDT",
            debit=3000.0,
            credit=0.0,
            reference="REF-0102554433",
            description="Compra P2P 60 USDT - Orden ORD-001",
            voucher_id=1,
            order_number="ORD-001",
            prev_hash="0" * 64,
            entry_hash="a" * 64,
        ),
        JournalEntry(
            id=2,
            entry_number=1,
            date_time=now,
            account_code="5.2.01",
            account_name="Gastos Financieros - Comisiones Bancarias",
            debit=9.0,
            credit=0.0,
            reference="REF-0102554433",
            description="Comisión bancaria débito P2P",
            voucher_id=1,
            order_number="ORD-001",
            prev_hash="a" * 64,
            entry_hash="b" * 64,
        ),
        JournalEntry(
            id=3,
            entry_number=1,
            date_time=now,
            account_code="1.1.01",
            account_name="Banco Nacional VES - Banco de Venezuela",
            debit=0.0,
            credit=3009.0,
            reference="REF-0102554433",
            description="Egreso bancario compra P2P",
            voucher_id=1,
            order_number="ORD-001",
            prev_hash="b" * 64,
            entry_hash="c" * 64,
        ),
    ]

    ledgers = [
        LedgerSummary(
            account_code="1.1.01",
            account_name="Banco Nacional VES",
            year=2026,
            month=11,
            initial_balance=10000.0,
            total_debit=0.0,
            total_credit=3009.0,
            final_balance=6991.0,
            entries_count=1,
        ),
        LedgerSummary(
            account_code="1.1.05",
            account_name="Activos Criptográficos - USDT",
            year=2026,
            month=11,
            initial_balance=500.0,
            total_debit=3000.0,
            total_credit=0.0,
            final_balance=3500.0,
            entries_count=1,
        ),
    ]

    vouchers = [
        BankVoucher(
            id=1,
            bank_name="Banco de Venezuela",
            destination_bank="Banesco",
            reference_number="0102554433",
            amount_ves=3000.0,
            bank_fee_ves=9.0,
            total_debited_ves=3009.0,
            sender_id="V-19456789",
            sender_name="CARLOS PEREZ",
            sender_phone="0414-1234567",
            concept="Pago orden Binance",
            payment_method="PAGO_MOVIL",
            movement_type="DEBIT",
            associated_order_number="ORD-001",
            verification_status="MATCHED",
            reconciliation_score=95.0,
            voucher_date=now,
        )
    ]

    return entries, ledgers, vouchers


def test_excel_accounting_report_generation(tmp_path):
    entries, ledgers, vouchers = sample_accounting_data()
    out_file = str(tmp_path / "test_reporte_contable.xlsx")

    path = ExcelReporter.generate_accounting_report(
        journal_entries=entries,
        ledger_summaries=ledgers,
        vouchers=vouchers,
        output_path=out_file,
    )

    assert os.path.exists(path)
    import openpyxl

    wb = openpyxl.load_workbook(path)
    sheet_names = wb.sheetnames

    assert "Libro Diario" in sheet_names
    assert "Libro Mayor" in sheet_names
    assert "Conciliación Bancaria" in sheet_names
    assert "Liquidación Fiscal SENIAT" in sheet_names


def test_pdf_accounting_report_generation(tmp_path):
    entries, ledgers, vouchers = sample_accounting_data()
    out_file = str(tmp_path / "test_reporte_contable.pdf")

    pdf_reporter = PDFReporter()
    path = pdf_reporter.generate_accounting_pdf(
        journal_entries=entries,
        ledger_summaries=ledgers,
        vouchers=vouchers,
        output_path=out_file,
    )

    assert os.path.exists(path)
    assert os.path.getsize(path) > 100

    # Comprobar firma de cabecera y cierre estándar PDF
    with open(path, "rb") as f:
        content = f.read()
        assert content.startswith(b"%PDF-")
        assert b"%%EOF" in content


def test_sheets_exporter_accounting():
    entries, ledgers, _ = sample_accounting_data()
    exporter = SheetsExporter()

    mock_client = MagicMock()
    mock_sh = MagicMock()
    mock_ws = MagicMock()
    mock_sh.worksheets.return_value = [mock_ws]
    mock_ws.title = "Libro Diario"
    mock_sh.add_worksheet.return_value = mock_ws
    mock_client.open_by_key.return_value = mock_sh

    exporter._get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]

    success = exporter.export_accounting(
        sheet_id="fake_sheet_id",
        journal_entries=entries,
        ledger_summaries=ledgers,
    )

    assert success is True
    assert mock_client.open_by_key.called
