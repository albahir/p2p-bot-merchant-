"""Tests unitarios para el cliente de Binance P2P."""

import httpx
import pytest

from src.core.binance_client import BinanceP2PClient


def test_exceeding_30_day_window_raises_error():
    client = BinanceP2PClient(api_key="test", private_key_pem="test")
    start = 1700000000000
    # 31 días después
    end = start + (31 * 24 * 60 * 60 * 1000)

    with pytest.raises(ValueError, match="FAIL-CLOSED: La ventana de consulta histórica no puede superar los 30 días."):
        client.get_order_history(trade_type="BUY", start_timestamp=start, end_timestamp=end)

def test_check_weight_under_threshold():
    client = BinanceP2PClient(api_key="test", private_key_pem="test")
    headers = httpx.Headers({"x-mbx-used-weight": "150"})
    client.check_weight(headers)
    assert client.last_used_weight == 150
