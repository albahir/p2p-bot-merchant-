"""Tests unitarios para el sincronizador de historial de órdenes Binance P2P a base de datos y CSV."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.binance_client import BinanceAuthError
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.core.binance_mock import MockBinanceP2PClient
from src.data.database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_sync_orders_success_with_mock_client(db_session):
    client = MockBinanceP2PClient()
    syncer = BinanceHistorySyncer()

    # 1. Primera ejecución: debe importar órdenes nuevas
    result = syncer.sync_orders(client=client, db=db_session, days=30, trade_type="ALL")

    assert result.success is True
    assert result.total_fetched > 0
    assert result.orders_inserted == result.total_fetched
    assert result.orders_existing == 0
    assert result.csv_bytes is not None
    assert len(result.csv_bytes) > 0
    assert result.total_volume_usdt > 0

    # 2. Segunda ejecución idéntica: debe detectar que ya existen en base de datos (idempotencia)
    result_dup = syncer.sync_orders(client=client, db=db_session, days=30, trade_type="ALL")
    assert result_dup.success is True
    assert result_dup.orders_inserted == 0
    assert result_dup.orders_existing == result.total_fetched


def test_sync_orders_filters_trade_type(db_session):
    client = MockBinanceP2PClient()
    syncer = BinanceHistorySyncer()

    result_buy = syncer.sync_orders(client=client, db=db_session, days=15, trade_type="BUY")
    assert result_buy.success is True
    assert all(o.trade_type == "BUY" for o in result_buy.orders)

    result_sell = syncer.sync_orders(client=client, db=db_session, days=15, trade_type="SELL")
    assert result_sell.success is True
    assert all(o.trade_type == "SELL" for o in result_sell.orders)


def test_sync_orders_handles_auth_error(db_session):
    client = MagicMock()
    client.get_order_history.side_effect = BinanceAuthError("Rechazo de autenticación Binance: IP no autorizada")

    syncer = BinanceHistorySyncer()
    result = syncer.sync_orders(client=client, db=db_session, days=7, trade_type="ALL")

    assert result.success is False
    assert result.orders_inserted == 0
    assert "IP no autorizada" in (result.error_message or "")


def test_sync_orders_generates_valid_csv_and_excel_format(db_session):
    client = MockBinanceP2PClient()
    syncer = BinanceHistorySyncer()

    result = syncer.sync_orders(client=client, db=db_session, days=30, trade_type="ALL")
    assert result.csv_bytes is not None
    assert result.excel_bytes is not None
    assert len(result.excel_bytes) > 2000

    # CSV con punto y coma para Excel España/Latam
    csv_text = result.csv_bytes.decode("utf-8-sig")
    assert "Número de Orden;" in csv_text or ";Tipo;" in csv_text
    assert "Cantidad Cripto" in csv_text
    assert "Monto Fiat" in csv_text
    assert "USDT" in csv_text

    # CSV con coma internacional
    assert result.csv_comma_bytes is not None
    csv_comma_text = result.csv_comma_bytes.decode("utf-8-sig")
    assert "Número de Orden," in csv_comma_text or ",Tipo," in csv_comma_text
