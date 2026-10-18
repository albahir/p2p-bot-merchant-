"""Pruebas unitarias para el comando /conciliacion y procesamiento de fotos de comprobantes en Telegram."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.models import Base
from src.integrations.receipt_ocr import ReceiptExtractionResult
from src.integrations.telegram_notifier import TelegramCommandPoller, TelegramNotifier
from src.reporting.fiscal_reconciler import FiscalReconciliationResult


@pytest.fixture(autouse=True)
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with patch("src.data.database.SessionLocal", session_factory):
        yield


@pytest.fixture
def notifier():
    return TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="123456",
        allowed_user_ids=[123456],
        use_sandbox=True,
    )


def test_telegram_handle_command_conciliacion(notifier):
    """Verifica que /conciliacion invoque la reconciliación contable y devuelva las 6 piezas."""
    mock_recon_result = FiscalReconciliationResult(
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

    with patch("src.reporting.fiscal_reconciler.FiscalReconciler.reconcile_period", return_value=mock_recon_result):
        resp = notifier.handle_command(user_id=123456, command="/conciliacion 2026-10")
        assert "Reconstrucción Fiscal P2P" in resp
        assert "2026-10" in resp
        assert "Saldo Inicial" in resp
        assert "BALANCED" in resp
        assert "1,000.00 VES" in resp


def test_telegram_process_receipt_photo(notifier):
    """Verifica que el procesamiento de foto de comprobante devuelva los datos extraídos."""
    mock_extraction = ReceiptExtractionResult(
        bank_name="Banco de Venezuela",
        reference_number="12345678",
        amount_ves=5500.0,
        sender_cedula="V-12345678",
        sender_name="CARLOS PEREZ",
        is_valid=True,
    )

    with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=mock_extraction):
        resp = notifier.process_receipt_photo(b"fake_image_bytes")
        assert "Comprobante Bancario Procesado" in resp
        assert "Banco de Venezuela" in resp
        assert "12345678" in resp
        assert "5,500.00 VES" in resp


def test_telegram_poller_handles_photo_message(notifier):
    """Verifica que TelegramCommandPoller detecte mensajes con foto y procese el comprobante."""
    poller = TelegramCommandPoller(notifier=notifier)

    fake_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 999,
                "message": {
                    "from": {"id": 123456},
                    "chat": {"id": 123456},
                    "photo": [
                        {"file_id": "thumb_123"},
                        {"file_id": "large_photo_456"},
                    ],
                },
            }
        ],
    }

    with (
        patch.object(notifier._client, "get") as mock_get,
        patch.object(notifier, "get_file_bytes", return_value=b"photo_bytes") as mock_get_bytes,
        patch.object(notifier, "process_receipt_photo", return_value="Comprobante OK") as mock_process,
        patch.object(notifier, "send_alert") as mock_send,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_updates
        mock_get.return_value = mock_resp

        processed = poller.poll_once()
        assert processed == 1
        mock_get_bytes.assert_called_with("large_photo_456")
        mock_process.assert_called_with(b"photo_bytes")
        mock_send.assert_called_with("Comprobante OK", chat_id="123456")
