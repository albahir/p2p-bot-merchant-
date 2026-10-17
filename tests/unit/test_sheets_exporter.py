"""Tests unitarios para el exportador de Google Sheets."""

from unittest.mock import MagicMock, patch

from src.reporting.sheets_exporter import SheetsExporter
from src.reporting.tax_engine import TradeResult


def create_sample_results() -> list[TradeResult]:
    return [
        TradeResult(
            order_number="SELL_1001",
            trade_type="SELL",
            crypto_amount=100.0,
            sell_price_fiat=38.0,
            total_revenue_fiat=3800.0,
            acquisition_cost_fiat=3650.0,
            fee_fiat=2.0,
            net_profit_fiat=148.0,
            bcv_rate=36.5,
            net_profit_usd=4.05,
        ),
        TradeResult(
            order_number="SELL_1002",
            trade_type="SELL",
            crypto_amount=150.0,
            sell_price_fiat=38.2,
            total_revenue_fiat=5730.0,
            acquisition_cost_fiat=5490.0,
            fee_fiat=3.0,
            net_profit_fiat=237.0,
            bcv_rate=36.5,
            net_profit_usd=6.49,
        ),
    ]


def test_sheets_exporter_fails_closed_when_no_credentials():
    exporter = SheetsExporter(credentials_path="non_existent_file.json", credentials_json=None)
    success = exporter.export(sheet_id="test_sheet_id", results=create_sample_results())
    assert success is False


def test_sheets_exporter_export_success_multi_tab():
    mock_sh = MagicMock()
    mock_ws_detalle = MagicMock()
    mock_ws_resumen = MagicMock()

    # Simular worksheets existentes
    mock_ws_detalle.title = "Detalle Fiscal"
    mock_ws_resumen.title = "Resumen Ejecutivo"
    mock_sh.worksheets.return_value = [mock_ws_detalle, mock_ws_resumen]

    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_sh

    with patch("gspread.service_account_from_dict", return_value=mock_client):
        credentials_dict = {"type": "service_account", "project_id": "test-p2p"}
        exporter = SheetsExporter(credentials_json=credentials_dict)
        results = create_sample_results()

        success = exporter.export(sheet_id="mock_sheet_123", results=results)
        assert success is True

        # Verificar que se actualizaron ambas pestañas
        assert mock_ws_detalle.clear.called
        assert mock_ws_detalle.append_rows.called

        # Verificar datos escritos en Detalle
        detalle_call_args = mock_ws_detalle.append_rows.call_args[0][0]
        assert detalle_call_args[0][0] == "Fecha y Hora (UTC)"
        assert detalle_call_args[0][1] == "Orden"
        assert len(detalle_call_args) == 3  # Header + 2 registros

        assert mock_ws_resumen.clear.called
        assert mock_ws_resumen.append_rows.called


def test_sheets_exporter_creates_missing_worksheets():
    mock_sh = MagicMock()
    mock_ws_default = MagicMock()
    mock_ws_default.title = "Sheet1"
    mock_sh.worksheets.return_value = [mock_ws_default]

    mock_new_ws = MagicMock()
    mock_sh.add_worksheet.return_value = mock_new_ws

    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_sh

    with patch("gspread.service_account_from_dict", return_value=mock_client):
        exporter = SheetsExporter(credentials_json={"type": "service_account"})
        success = exporter.export(sheet_id="mock_sheet_123", results=create_sample_results())

        assert success is True
        # Debe llamar add_worksheet para Detalle Fiscal y Resumen Ejecutivo
        assert mock_sh.add_worksheet.call_count == 2


def test_sheets_exporter_handles_gspread_api_error_fail_closed():
    import gspread
    mock_client = MagicMock()
    mock_client.open_by_key.side_effect = gspread.exceptions.GSpreadException("Google API 403 Permission Denied: caller does not have permission")

    with patch("gspread.service_account_from_dict", return_value=mock_client):
        exporter = SheetsExporter(credentials_json={"type": "service_account", "client_email": "bot@test.iam.gserviceaccount.com"})
        success = exporter.export(sheet_id="forbidden_sheet", results=create_sample_results())
        assert success is False
        assert exporter.last_error is not None
        assert "Permiso denegado (HTTP 403)" in exporter.last_error
        assert "bot@test.iam.gserviceaccount.com" in exporter.last_error


def test_sheets_exporter_handles_404_not_found():
    import gspread
    mock_client = MagicMock()
    mock_client.open_by_key.side_effect = gspread.exceptions.GSpreadException("SpreadsheetNotFound: 404")

    with patch("gspread.service_account_from_dict", return_value=mock_client):
        exporter = SheetsExporter(credentials_json={"type": "service_account"})
        success = exporter.export(sheet_id="missing_sheet_999", results=create_sample_results())
        assert success is False
        assert exporter.last_error is not None
        assert "Hoja no encontrada (HTTP 404)" in exporter.last_error
        assert "missing_sheet_999" in exporter.last_error
