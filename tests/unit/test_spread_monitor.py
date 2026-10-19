"""Tests unitarios (TDD) para el módulo SpreadMonitor y Rentabilidad Real P2P (SPEC-013 Fase 4)."""


from src.core.spread_monitor import (
    BankRateQuote,
    NetProfitCalculation,
    SpreadMonitor,
)


def test_net_profit_calculation_with_hidden_bank_fees():
    """Valida la fórmula fundamental con comisiones bancarias del 0.3% y comisión Binance."""
    # Comprar 1,000 USDT a 840 VES y vender a 855 VES (spread bruto de 1.78%)
    calc = SpreadMonitor.calculate_cycle_net_profit(
        crypto_amount=1000.0,
        buy_price=840.0,
        sell_price=855.0,
        binance_maker_fee_pct=0.0035,  # 0.35% comisión de Binance
        bank_fee_pct=0.003,            # 0.30% comisión bancaria (Pago Móvil)
    )

    assert isinstance(calc, NetProfitCalculation)
    assert calc.crypto_amount == 1000.0
    assert calc.gross_buy_ves == 840000.0
    assert calc.gross_sell_ves == 855000.0

    # Comisiones bancarias (0.3% en compra y venta)
    assert calc.bank_fee_buy_ves == 840000.0 * 0.003
    assert calc.bank_fee_sell_ves == 855000.0 * 0.003

    # Margen neto positivo tras descontar comisiones
    assert calc.net_profit_ves > 0
    assert calc.net_profit_usdt > 0
    assert calc.gross_spread_pct > 0.80
    assert calc.is_profitable is True
    assert calc.is_viable is True


def test_spread_monitor_critical_margin_alert():
    """Valida que si la operación genera ligera ganancia pero el spread es < 0.80%, active CRITICAL_MARGIN."""
    # Entre cuentas del mismo banco (0% comisión bancaria) con comisión Binance baja (0.1%)
    calc = SpreadMonitor.calculate_cycle_net_profit(
        crypto_amount=500.0,
        buy_price=1000.0,
        sell_price=1006.0,  # Spread bruto de 0.60% (< 0.80%)
        binance_maker_fee_pct=0.001,  # 0.10%
        bank_fee_pct=0.0,             # 0% mismo banco
    )

    assert calc.gross_spread_pct == 0.60
    assert calc.is_profitable is True
    assert calc.is_viable is False
    assert calc.warning_level == "CRITICAL_MARGIN"
    assert "0.80%" in calc.warning_message



def test_bank_arbitrage_matrix_ranking():
    """Valida la generación de la matriz banco a banco y detección de mejor arbitraje."""
    quotes = [
        BankRateQuote(bank_name="Banco de Venezuela", buy_rate=1000.0, sell_rate=1005.0),
        BankRateQuote(bank_name="Banesco", buy_rate=1002.0, sell_rate=1015.0),
        BankRateQuote(bank_name="Bancamiga", buy_rate=1001.0, sell_rate=1020.0),
        BankRateQuote(bank_name="Pago Móvil", buy_rate=1001.5, sell_rate=1010.0),
    ]

    monitor = SpreadMonitor()
    matrix = monitor.generate_arbitrage_matrix(quotes)

    assert len(matrix) == 4
    # Bancamiga tiene la mayor venta (1020), BDV tiene la menor compra (1000)
    best_arb = monitor.find_best_cross_arbitrage(quotes)
    assert best_arb is not None
    assert best_arb["buy_bank"] == "Banco de Venezuela"
    assert best_arb["sell_bank"] == "Bancamiga"
    assert best_arb["spread_ves"] == 20.0  # 1020 - 1000
    assert best_arb["spread_pct"] == 2.0   # 20 / 1000 = 2%


def test_bcv_gap_calculation():
    """Valida el cálculo de brecha cambiaria contra la tasa oficial del BCV."""
    monitor = SpreadMonitor()
    gap = monitor.calculate_bcv_gap(p2p_price=1000.0, bcv_rate=800.0)
    # (1000 - 800) / 800 = 25%
    assert gap == 25.0


def test_cross_arbitrage_guarantees_distinct_banks():
    """Valida que find_best_cross_arbitrage nunca seleccione el mismo banco para compra y venta."""
    # Banco Activo tiene tanto el precio de compra más bajo como el precio de venta más alto
    quotes = [
        BankRateQuote(bank_name="Banco Activo", buy_rate=998.50, sell_rate=1021.00),
        BankRateQuote(bank_name="Banesco", buy_rate=1002.50, sell_rate=1012.80),
        BankRateQuote(bank_name="Bancamiga", buy_rate=1000.80, sell_rate=1016.50),
    ]
    monitor = SpreadMonitor()
    best_arb = monitor.find_best_cross_arbitrage(quotes)

    assert best_arb is not None
    # No puede ser Banco Activo -> Banco Activo
    assert best_arb["buy_bank"] != best_arb["sell_bank"]
    # La mejor combinación interbancaria es:
    # Comprar en Bancamiga a 1000.80 y Vender en Banco Activo a 1021.00 (spread = 20.20 Bs, 2.02%)
    # Supera a Banco Activo -> Bancamiga (18.00 Bs) y Banesco -> Banco Activo (18.50 Bs)
    assert best_arb["buy_bank"] == "Bancamiga"
    assert best_arb["sell_bank"] == "Banco Activo"
    assert best_arb["spread_ves"] == round(1021.00 - 1000.80, 2)
    assert best_arb["spread_pct"] == round((20.20 / 1000.80) * 100, 2)


def test_spread_monitor_fetch_live_quotes_with_client():
    """fetch_live_quotes debe consultar anuncios vía cliente y retornar BankRateQuote por banco."""
    from src.core.binance_mock import MockBinanceP2PClient

    client = MockBinanceP2PClient()
    monitor = SpreadMonitor()

    quotes = monitor.fetch_live_quotes(client=client)
    assert len(quotes) > 0
    for q in quotes:
        assert isinstance(q, BankRateQuote)
        assert q.buy_rate > 0
        assert q.sell_rate > 0
        assert q.bank_name != ""

    bank_names = [q.bank_name for q in quotes]
    assert "Banco de Venezuela" in bank_names or "Banesco" in bank_names


def test_spread_monitor_fetch_live_quotes_fallback_on_network_error():
    """fetch_live_quotes debe retornar cotizaciones de respaldo si el cliente de red falla."""
    class FailingClient:
        def search_p2p_ads(self, *args, **kwargs):
            raise RuntimeError("Network timeout simulation")

    monitor = SpreadMonitor()
    quotes = monitor.fetch_live_quotes(client=FailingClient())
    # Debe retornar cotizaciones calibradas de respaldo sin fallar
    assert len(quotes) > 0
    assert any(q.bank_name == "Banco de Venezuela" for q in quotes)


def test_bank_rate_quote_extended_attributes():
    """Valida los nuevos atributos enriquecidos de BankRateQuote conservando retrocompatibilidad."""
    q = BankRateQuote(
        bank_name="Banesco",
        buy_rate=1012.0,
        sell_rate=1006.0,
        total_ads=25,
        score=95.0,
        liquidity_pct=22.5,
        binance_code="Banesco",
        exchanges=["binance", "bybit"],
        source="pitbullchain",
    )
    assert q.total_ads == 25
    assert q.score == 95.0
    assert q.liquidity_pct == 22.5
    assert q.binance_code == "Banesco"
    assert "bybit" in q.exchanges
    assert q.source == "pitbullchain"


def test_fetch_pitbullchain_quotes_mock(monkeypatch):
    """Valida el parseo correcto de la respuesta de PitbullChain API."""
    import httpx

    sample_payload = {
        "data": {
            "banks": [
                {
                    "bank": "Banesco",
                    "binanceId": "Banesco",
                    "totalAds": 18,
                    "avgBuyPrice": 1012.50,
                    "avgSellPrice": 1006.80,
                    "spread": 5.70,
                    "spreadPct": 0.56,
                    "score": 88,
                    "liquidityPct": 18.2,
                    "exchanges": ["binance", "bybit"],
                },
                {
                    "bank": "BancoDeVenezuela",
                    "binanceId": "BancoDeVenezuela",
                    "totalAds": 20,
                    "avgBuyPrice": 1012.80,
                    "avgSellPrice": 1009.00,
                    "spread": 3.80,
                    "spreadPct": 0.38,
                    "score": 85,
                    "liquidityPct": 20.0,
                    "exchanges": ["binance"],
                },
            ]
        }
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return sample_payload

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    monitor = SpreadMonitor()
    quotes = monitor.fetch_pitbullchain_quotes(exchange="binance")

    assert len(quotes) == 2
    assert quotes[0].bank_name == "Banesco"
    assert quotes[0].buy_rate == 1012.50
    assert quotes[0].sell_rate == 1006.80
    assert quotes[0].total_ads == 18
    assert quotes[0].score == 88.0
    assert quotes[0].source == "pitbullchain"
    assert quotes[1].bank_name == "Banco de Venezuela" or quotes[1].bank_name == "BancoDeVenezuela"


def test_fetch_yadio_rate_mock(monkeypatch):
    """Valida la consulta de tasa de mercado libre en Yadio."""
    import httpx

    class MockResponse:
        status_code = 200
        def json(self):
            return {"usd": 1008.50, "eur": 1130.20, "timestamp": 1792430000}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    monitor = SpreadMonitor()
    rate = monitor.fetch_yadio_rate()
    assert rate == 1008.50


def test_fetch_criptoya_rate_mock(monkeypatch):
    """Valida la consulta de spread Maker/Taker en CriptoYa."""
    import httpx

    class MockResponse:
        status_code = 200
        def json(self):
            return {"ask": 1009.20, "bid": 1011.50, "time": 1792430000}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    monitor = SpreadMonitor()
    res = monitor.fetch_criptoya_rate()
    assert res is not None
    assert res["ask"] == 1009.20
    assert res["bid"] == 1011.50




