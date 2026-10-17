"""Tests unitarios para el generador de cierre fiscal mensual y despacho a Telegram."""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import Order
from src.integrations.telegram_notifier import TelegramNotifier
from src.reporting.monthly_closer import MonthlyFiscalCloser


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_monthly_closer_empty_month():
    session_factory = setup_in_memory_db()
    notifier = MagicMock(spec=TelegramNotifier)
    closer = MonthlyFiscalCloser(session_factory=session_factory, notifier=notifier)

    file_path, metrics = closer.execute_close(year=2026, month=9, send_telegram=True)
    assert file_path is None
    assert metrics["total_orders"] == 0
    assert not notifier.send_document.called


def test_monthly_closer_with_orders_generates_excel_and_sends(tmp_path):
    session_factory = setup_in_memory_db()
    db = session_factory()

    # Órdenes de Septiembre 2026
    o1 = Order(
        order_number="BUY_SEP_1",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=3500.0,
        crypto_amount=100.0,
        unit_price=35.0,
        fee_fiat=10.0,
        bcv_rate=35.0,
        order_status="COMPLETED",
        created_at=datetime(2026, 9, 10, 10, 0, 0, tzinfo=UTC),
    )
    o2 = Order(
        order_number="SELL_SEP_1",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=3800.0,
        crypto_amount=100.0,
        unit_price=38.0,
        fee_fiat=15.0,
        bcv_rate=35.0,
        order_status="COMPLETED",
        created_at=datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC),
    )
    # Orden de Octubre 2026 (no debe incluirse en el cierre de Septiembre)
    o3 = Order(
        order_number="SELL_OCT_1",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=4000.0,
        crypto_amount=100.0,
        unit_price=40.0,
        fee_fiat=15.0,
        bcv_rate=36.0,
        order_status="COMPLETED",
        created_at=datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC),
    )

    db.add_all([o1, o2, o3])
    db.commit()
    db.close()

    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send_document.return_value = True

    output_dir = str(tmp_path)
    closer = MonthlyFiscalCloser(session_factory=session_factory, notifier=notifier, output_dir=output_dir)

    file_path, metrics = closer.execute_close(year=2026, month=9, send_telegram=True)

    assert file_path is not None
    assert os.path.exists(file_path)
    assert "2026_09" in file_path
    assert metrics["total_orders"] == 1  # 1 venta procesada en septiembre
    assert metrics["crypto_sold"] == 100.0
    assert metrics["net_profit_fiat"] == 275.0  # 3800 - 3510 - 15 = 275

    # Verificar que se llamó a send_document de Telegram con el archivo y caption
    assert notifier.send_document.called
    call_args = notifier.send_document.call_args[1]
    assert call_args["file_path"] == file_path
    assert "Septiembre 2026" in call_args["caption"]
    assert "Ganancia Neta" in call_args["caption"]


def test_telegram_send_document_handles_network_and_sanitization(tmp_path):
    dummy_file = tmp_path / "test.xlsx"
    dummy_file.write_bytes(b"dummy excel content")

    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="1001", allowed_user_ids=[1001])

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    notifier._client.post = MagicMock(return_value=mock_resp)

    caption_with_secret = "Reporte mensual con api_key: 'super_secret_12345678'"
    success = notifier.send_document(file_path=str(dummy_file), caption=caption_with_secret)

    assert success is True
    assert notifier._client.post.called
    posted_data = notifier._client.post.call_args[1]["data"]
    assert "super_secret_12345678" not in posted_data["caption"]
    assert "[REDACTED]" in posted_data["caption"]
