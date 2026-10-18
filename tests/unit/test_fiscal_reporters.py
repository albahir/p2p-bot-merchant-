"""Pruebas unitarias para exportadores multi-pestaña (Excel y Google Sheets) con 4 hojas auditadas."""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.models import BankVoucher, Order, WalletMovement
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.fiscal_reconciler import FiscalReconciliationResult
from src.reporting.sheets_exporter import SheetsExporter


@pytest.fixture
def sample_data():
    recon = FiscalReconciliationResult(
        period="2026-10",
        initial_balance=100.0,
        inflows_deposits=150.0,
        inflows_p2p_buys=300.0,
        total_inflows=450.0,
        outflows_withdrawals=50.0,
        outflows_p2p_sells=200.0,
        total_outflows=250.0,
        volume_operated=500.0,
        total_fees=1.0,
        calculated_final_balance=299.0,
        actual_final_balance=299.0,
        discrepancy=0.0,
        gross_revenue_ves=11000.0,
        acquisition_cost_ves=10000.0,
        net_profit_ves=1000.0,
        net_profit_usd=20.0,
        status="BALANCED",
        orders_count=2,
        movements_count=2,
        vouchers_count=1,
        matched_vouchers_count=1,
        message="Período balanceado",
    )

    orders = [
        Order(
            order_number="BUY-101",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            crypto_amount=300.0,
            unit_price=52.0,
            fiat_amount=15600.0,
            fee_fiat=0.0,
            order_status="COMPLETED",
            bcv_rate=50.0,
            created_at=datetime(2026, 10, 5, 10, 0, tzinfo=UTC),
        ),
        Order(
            order_number="SELL-102",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            crypto_amount=200.0,
            unit_price=55.0,
            fiat_amount=11000.0,
            fee_fiat=0.0,
            order_status="COMPLETED",
            bcv_rate=50.0,
            created_at=datetime(2026, 10, 10, 14, 0, tzinfo=UTC),
        ),
    ]

    movements = [
        WalletMovement(
            txid="DEP-001",
            movement_type="DEPOSIT",
            asset="USDT",
            amount=150.0,
            fee=0.0,
            network="TRC20",
            status="COMPLETED",
            timestamp=datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
        ),
        WalletMovement(
            txid="WTH-001",
            movement_type="WITHDRAWAL",
            asset="USDT",
            amount=50.0,
            fee=1.0,
            network="BSC",
            status="COMPLETED",
            timestamp=datetime(2026, 10, 20, 16, 0, tzinfo=UTC),
        ),
    ]

    vouchers = [
        BankVoucher(
            bank_name="Banco de Venezuela",
            reference_number="9876543210",
            amount_ves=11000.0,
            sender_id="V-12345678",
            sender_name="JUAN PEREZ",
            associated_order_number="SELL-102",
            verification_status="MATCHED",
            payment_method="PAGO_MOVIL",
            created_at=datetime(2026, 10, 10, 14, 5, tzinfo=UTC),
        )
    ]

    return recon, orders, movements, vouchers


def test_excel_reporter_four_tabs(sample_data, tmp_path):
    """Verifica que el informe Excel se genere con exactamente las 4 pestañas requeridas."""
    recon, orders, movements, vouchers = sample_data
    out_file = str(tmp_path / "reporte_fiscal_4_pestanas.xlsx")

    res_path = ExcelReporter.generate_fiscal_reconstruction_report(
        reconciliation=recon,
        p2p_orders=orders,
        wallet_movements=movements,
        vouchers=vouchers,
        output_path=out_file,
    )

    assert os.path.exists(res_path)
    excel_file = pd.ExcelFile(res_path)
    sheet_names = excel_file.sheet_names

    assert "Resumen Fiscal" in sheet_names
    assert "Detalle P2P" in sheet_names
    assert "Depósitos y Retiros" in sheet_names
    assert "Conciliación Bancaria" in sheet_names

    df_resumen = pd.read_excel(res_path, sheet_name="Resumen Fiscal")
    assert len(df_resumen) >= 10
    assert any("Saldo Inicial" in str(val) for val in df_resumen["Concepto / Métrica"].values)

    df_p2p = pd.read_excel(res_path, sheet_name="Detalle P2P")
    assert len(df_p2p) == 2

    df_movs = pd.read_excel(res_path, sheet_name="Depósitos y Retiros")
    assert len(df_movs) == 2

    df_vouchers = pd.read_excel(res_path, sheet_name="Conciliación Bancaria")
    assert len(df_vouchers) == 1
    assert str(df_vouchers.iloc[0]["Referencia"]) == "9876543210"


def test_sheets_exporter_four_tabs(sample_data):
    """Verifica que SheetsExporter invoque y actualice las 4 pestañas en Google Sheets."""
    recon, orders, movements, vouchers = sample_data

    exporter = SheetsExporter(credentials_json={"client_email": "bot@example.com"})

    mock_client = MagicMock()
    mock_sh = MagicMock()
    mock_client.open_by_key.return_value = mock_sh

    mock_ws_resumen = MagicMock()
    mock_ws_p2p = MagicMock()
    mock_ws_movs = MagicMock()
    mock_ws_vouchers = MagicMock()

    def get_or_create_mock(sh, title, rows=100, cols=20):
        if title == "Resumen Fiscal":
            return mock_ws_resumen
        elif title == "Detalle P2P":
            return mock_ws_p2p
        elif title == "Depósitos y Retiros":
            return mock_ws_movs
        elif title == "Conciliación Bancaria":
            return mock_ws_vouchers
        return MagicMock()

    with (
        patch.object(exporter, "_get_client", return_value=mock_client),
        patch.object(exporter, "_get_or_create_worksheet", side_effect=get_or_create_mock),
    ):
            success = exporter.export_fiscal_reconstruction(
                sheet_id="fake_sheet_id_123",
                reconciliation=recon,
                p2p_orders=orders,
                wallet_movements=movements,
                vouchers=vouchers,
            )

            assert success is True
            assert mock_ws_resumen.clear.called
            assert mock_ws_resumen.append_rows.called
            assert mock_ws_p2p.clear.called
            assert mock_ws_p2p.append_rows.called
            assert mock_ws_movs.clear.called
            assert mock_ws_movs.append_rows.called
            assert mock_ws_vouchers.clear.called
            assert mock_ws_vouchers.append_rows.called
