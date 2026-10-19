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


def test_binance_client_ed25519_signature():
    """El cliente debe firmar correctamente con clave privada Ed25519 PEM."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("utf-8")
    client = BinanceP2PClient(api_key="my_binance_key", private_key_pem=pem)

    params = {"timestamp": 1700000000000, "recvWindow": 5000, "tradeType": "BUY"}
    signed = client.sign_params(params)

    assert "signature" in signed
    assert len(signed["signature"]) > 40
    assert signed["timestamp"] == 1700000000000


def test_binance_client_hmac_signature():
    """El cliente debe generar una firma HMAC-SHA256 hex válida ante una secret key simétrica."""
    secret = "a" * 64
    client = BinanceP2PClient(api_key="my_binance_key", private_key_pem=secret)

    params = {"timestamp": 1700000000000, "recvWindow": 5000}
    signed = client.sign_params(params)

    assert "signature" in signed
    assert len(signed["signature"]) == 64  # SHA-256 hex digest


def test_binance_client_get_order_history_sends_signature(monkeypatch):
    """La llamada a listUserOrderHistory debe incluir X-MBX-APIKEY y el parámetro de firma."""
    secret = "b" * 64
    client = BinanceP2PClient(api_key="test_api_key_123", private_key_pem=secret)

    captured_request = {}

    def mock_get(self, url, params=None, headers=None):
        captured_request["url"] = str(url)
        captured_request["params"] = params
        captured_request["headers"] = headers
        mock_resp = httpx.Response(
            status_code=200,
            json={"code": "000000", "message": "success", "data": []},
            headers={"x-mbx-used-weight": "5"},
            request=httpx.Request("GET", str(url))
        )
        return mock_resp

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    now = 1700000000000
    res = client.get_order_history("BUY", start_timestamp=now - 1000, end_timestamp=now)
    assert res.code == "000000"
    assert "signature" in captured_request["params"]
    assert captured_request["headers"]["X-MBX-APIKEY"] == "test_api_key_123"


def test_binance_client_search_p2p_ads_filters_and_trade_methods(monkeypatch):
    """get_order_book / search_p2p_ads debe enviar filtros bancarios y parsear tradeMethods."""
    client = BinanceP2PClient(api_key="test_api_key", private_key_pem="test_pem")

    captured_payload = {}

    def mock_post(self, url, json=None, headers=None):
        captured_payload["url"] = str(url)
        captured_payload["json"] = json
        mock_data = {
            "code": "000000",
            "message": "success",
            "total": 1,
            "success": True,
            "data": [
                {
                    "adv": {
                        "advNo": "ADV_123",
                        "tradeType": "BUY",
                        "asset": "USDT",
                        "fiatUnit": "VES",
                        "price": "1005.50",
                        "surplusAmount": "2500.00",
                        "minSingleTransAmount": "500.00",
                        "maxSingleTransAmount": "50000.00",
                        "tradeMethods": [
                            {"tradeMethodName": "Banco de Venezuela", "payType": "SpecificBank"},
                            {"tradeMethodName": "Pago Móvil", "payType": "PagoMovil"},
                        ],
                    },
                    "advertiser": {
                        "nickName": "MerchantPro",
                        "monthOrderCount": 850,
                        "monthFinishRate": 0.995,
                    },
                }
            ],
        }
        return httpx.Response(
            status_code=200,
            json=mock_data,
            headers={"x-mbx-used-weight": "1"},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    res = client.search_p2p_ads(
        asset="USDT",
        fiat="VES",
        trade_type="BUY",
        pay_types=["SpecificBank", "PagoMovil"],
        trans_amount=1000.0,
        merchant_check=True,
    )

    assert res.code == "000000"
    assert len(res.data) == 1
    item = res.data[0]
    assert item.adv.price == "1005.50"
    assert "Banco de Venezuela" in item.bank_names
    assert "Pago Móvil" in item.bank_names
    assert captured_payload["json"]["payTypes"] == ["SpecificBank", "PagoMovil"]
    assert captured_payload["json"]["transAmount"] == "1000.0"
    assert captured_payload["json"]["merchantCheck"] is True


def test_mock_binance_search_p2p_ads_banks():
    """MockBinanceP2PClient debe devolver anuncios con métodos bancarios y respetar pay_types."""
    from src.core.binance_mock import MockBinanceP2PClient

    mock = MockBinanceP2PClient()
    # 1. Búsqueda general
    res_all = mock.search_p2p_ads(asset="USDT", fiat="VES", trade_type="BUY", rows=10)
    assert res_all.code == "000000"
    assert len(res_all.data) > 0
    first_ad = res_all.data[0]
    assert len(first_ad.bank_names) > 0

    # 2. Filtrado por Banesco
    res_banesco = mock.search_p2p_ads(asset="USDT", fiat="VES", trade_type="BUY", pay_types=["Banesco"])
    for ad in res_banesco.data:
        assert any("Banesco" in b for b in ad.bank_names)

    # 3. Filtrado por monto
    res_amount = mock.search_p2p_ads(asset="USDT", fiat="VES", trade_type="BUY", trans_amount=2000.0)
    for ad in res_amount.data:
        min_amt = float(ad.adv.minSingleTransAmount or "0")
        max_amt = float(ad.adv.maxSingleTransAmount or "99999999")
        assert min_amt <= 2000.0 <= max_amt



