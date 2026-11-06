"""Tests unitarios (TDD) para la extracción histórica por ventanas de 30 días hasta 180/365 días."""

from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.database import Base
from src.data.repositories import OrderRepository


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_sync_orders_multi_window_180_days():
    db = setup_in_memory_db()
    syncer = BinanceHistorySyncer()

    # Mock del cliente de Binance P2P
    mock_client = MagicMock()

    # Simular que cada ventana de 30 días devuelve 2 órdenes
    def mock_get_order_history(trade_type, start_timestamp, end_timestamp, page, rows):
        mock_item1 = MagicMock()
        mock_item1.orderNumber = f"ORD-{trade_type}-{start_timestamp}-1"
        mock_item1.tradeType.value = trade_type
        mock_item1.asset = "USDT"
        mock_item1.fiat = "VES"
        mock_item1.totalPrice = 5000.0
        mock_item1.amount = 100.0
        mock_item1.unitPrice = 50.0
        mock_item1.fee_decimal = 0.0
        mock_item1.orderStatus.value = "COMPLETED"
        mock_item1.createTime = start_timestamp + 1000
        mock_item1.counterPartNickName = "Trader Test"


        mock_resp = MagicMock()
        mock_resp.data = [mock_item1] if page == 1 else []
        return mock_resp

    mock_client.get_order_history.side_effect = mock_get_order_history

    # Ejecutar extracción por 180 días (6 meses = ~6 ventanas de 30 días)
    res = syncer.sync_orders(
        client=mock_client,
        db=db,
        days=180,
        trade_type="BUY",
        page_size=50,
    )

    assert res.success is True
    # Debería haber hecho aproximadamente 6 ventanas de consultas
    assert mock_client.get_order_history.call_count >= 6
    assert res.total_fetched >= 6

    # Verificar inserción en base de datos
    repo = OrderRepository(db)
    all_orders = repo.list_completed()
    assert len(all_orders) >= 6

