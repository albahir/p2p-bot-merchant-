"""Pruebas unitarias e integración (TDD) para Velas P2P, Profundidad y Predictor Estadístico (SPEC-025)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.market_analytics import (
    MarketCollectorService,
    aggregate_candles,
    backtest_percentile_band,
    chain_candles,
    compute_depth_summary,
    compute_ema_series,
    compute_percentile_band,
    compute_rsi_series,
    compute_vwap_for_ticket,
    hampel_filter,
)
from src.data.database import Base
from src.data.models import MarketSnapshot


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_hampel_filter_strips_isolated_spike_without_flattening_trend():
    """El filtro de Hampel MAD debe descartar anuncios basura aislados sin borrar subidas reales."""
    base_ts = int(datetime(2026, 11, 20, 14, 0, tzinfo=UTC).timestamp())
    points: list[tuple[int, float, float]] = []
    for i in range(25):
        price = 1060.0 + i * 0.2
        if i == 12:
            price = 1140.0  # Anuncio outlier absurdo aislado
        points.append((base_ts + i * 60, price, 5000.0))

    cleaned = hampel_filter(points, value_fn=lambda p: p[1], window=8, threshold=4.0)
    prices = [p[1] for p in cleaned]
    assert 1140.0 not in prices
    assert len(cleaned) == 24


def test_aggregate_and_chain_candles_plus_ema_and_aligned_rsi():
    """Debe agrupar OHLC en cubetas exactas, encadenar open=prev_close y alinear RSI 14 por índice."""
    base_ts = int(datetime(2026, 11, 20, 10, 0, tzinfo=UTC).timestamp())
    raw_points: list[tuple[int, float, float]] = []
    # 20 cubetas de 5 minutos (100 minutos, 2 lecturas por cubeta)
    for i in range(40):
        val = 1000.0 + (i * 0.5) + (0.3 if i % 2 else -0.2)
        raw_points.append((base_ts + i * 150, round(val, 2), 1000.0))

    candles = aggregate_candles(
        raw_points,
        bucket_seconds=300,
        time_fn=lambda p: p[0],
        ohlc_fn=lambda p: p[1],
        vol_fn=lambda p: p[2],
    )
    assert len(candles) == 20
    assert candles[0]["volume"] == 2000.0

    chained = chain_candles(candles)
    for idx in range(1, len(chained)):
        assert chained[idx]["open"] == chained[idx - 1]["close"]
        assert chained[idx]["high"] >= max(chained[idx]["open"], chained[idx]["close"])
        assert chained[idx]["low"] <= min(chained[idx]["open"], chained[idx]["close"])

    ema9 = compute_ema_series(chained, 9)
    assert len(ema9) == len(chained) - 8  # Empieza en índice 8

    rsi14 = compute_rsi_series(chained, 14)
    assert len(rsi14) == len(chained)
    # Primeras 14 velas sin valor (para alinear eje lógico con Lightweight Charts)
    assert rsi14[0]["value"] is None
    assert rsi14[13]["value"] is None
    assert rsi14[14]["value"] is not None
    assert 0.0 <= float(rsi14[14]["value"]) <= 100.0


def test_depth_summary_and_ticket_vwap_detects_slippage():
    """Debe calcular acumulados Top 5/10/20, desequilibrio y VWAP real para el ticket en VES."""
    buy_ads = [
        {"price": 1060.0, "surplus_usdt": 100.0},   # Top 1 aguanta Bs 106,000
        {"price": 1062.0, "surplus_usdt": 400.0},   # Bs 424,800
        {"price": 1065.0, "surplus_usdt": 1500.0},
    ]
    sell_ads = [
        {"price": 1070.0, "surplus_usdt": 200.0},
        {"price": 1068.0, "surplus_usdt": 800.0},
    ]

    depth = compute_depth_summary(buy_ads, sell_ads)
    assert depth["top5"]["buy_usdt"] == 2000.0
    assert depth["top5"]["sell_usdt"] == 1000.0
    # buy_ads = oferta, sell_ads = demanda -> desequilibrio negativo (más oferta que demanda)
    assert depth["imbalance"] < 0.0

    # Para comprar Bs 318,400 (~100 USDT @1060 + 200 USDT @1062)
    vwap = compute_vwap_for_ticket(buy_ads, ticket_ves=318_400.0)
    assert vwap["fillable"] is True
    assert vwap["vwap_price"] > 1060.0
    assert vwap["slippage_pct"] > 0.0
    assert vwap["top_price_covers_ticket"] is False


def test_percentile_band_and_backtest_fail_closed():
    """Debe requerir mínimo de días para banda 90% y calcular percentiles ponderados + backtest real."""
    assert compute_percentile_band([1000.0] * 10, anchor_price=1000.0) is None

    closes = [1000.0 + (i * 2.5) + ((-1) ** i) * 4.0 for i in range(30)]
    band = compute_percentile_band(closes, anchor_price=closes[-1])
    assert band is not None
    assert band["floor"] < closes[-1] < band["ceiling"]

    bt = backtest_percentile_band(closes)
    assert bt is not None
    assert bt["evaluated"] > 0
    assert 0.0 <= bt["hit_rate_pct"] <= 100.0


def test_market_collector_captures_snapshot_and_sustained_hourly_rollup():
    """Debe capturar instantánea viva, crear/actualizar rollup horario y calcular máximo sostenido (pc)."""
    db = _make_db()
    try:
        mock_book = {
            "best_buy_price": 1062.0,
            "best_sell_price": 1068.5,
            "buy_ads": [
                {"price": 1062.0, "surplus_usdt": 500.0, "banks": ["Banesco"]},
                {"price": 1063.0, "surplus_usdt": 1500.0, "banks": ["Pago Móvil", "Banesco"]},
            ],
            "sell_ads": [
                {"price": 1068.5, "surplus_usdt": 300.0, "banks": ["Banesco"]},
                {"price": 1067.0, "surplus_usdt": 900.0, "banks": ["Banco de Venezuela"]},
            ],
        }
        collector = MarketCollectorService(db)
        ts1 = datetime(2026, 11, 20, 15, 10, tzinfo=UTC)
        with (
            patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", return_value=mock_book),
            patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 918.76}),
        ):
            snap1 = collector.capture_snapshot(now_utc=ts1)
            assert snap1.bcv_rate == 918.76
            assert snap1.p2p_sell_avg20 > 1067.0

            # Segunda lectura dentro de la misma hora con Banesco bajando a 1066.0 -> sostenido pc = min(1068.5, 1066.0)
            mock_book_2 = {
                "best_buy_price": 1061.5,
                "best_sell_price": 1066.0,
                "buy_ads": [{"price": 1061.5, "surplus_usdt": 700.0, "banks": ["Banesco"]}],
                "sell_ads": [{"price": 1066.0, "surplus_usdt": 1200.0, "banks": ["Banesco"]}],
            }
        with (
            patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", return_value=mock_book_2),
            patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 918.76}),
        ):
            snap2 = collector.capture_snapshot(now_utc=ts1 + timedelta(minutes=10))
            assert snap2.id != snap1.id

        rollups = collector.repo.list_hourly_rollups()
        assert len(rollups) == 1
        assert rollups[0].samples_count == 2
        assert rollups[0].sell_high >= rollups[0].sell_low
    finally:
        db.close()


def test_api_market_endpoints_return_candles_and_analytics():
    """Verifica /api/market/candles y /api/market/analytics en llamada directa de controlador."""
    from src.api.routes.market import get_market_analytics, get_market_candles

    db = _make_db()
    try:
        base_dt = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
        for i in range(22):
            dt = base_dt + timedelta(minutes=5 * i)
            db.add(
                MarketSnapshot(
                    timestamp=dt,
                    bcv_rate=918.76,
                    p2p_buy_best=1062.0 + i * 0.1,
                    p2p_buy_avg20=1063.0 + i * 0.1,
                    p2p_sell_best=1068.0 + i * 0.1,
                    p2p_sell_avg20=1066.5 + i * 0.1,
                    p2p_mid=1064.75 + i * 0.1,
                    brecha_pct=15.9 + i * 0.01,
                    spread_ves=-6.0,
                    vol_buy_usdt=12000.0,
                    vol_sell_usdt=15000.0,
                )
            )
        db.commit()

        res_candles = get_market_candles(side="sell", timeframe="5m", bank="*", ticket_ves=1_000_000.0, limit=100, db=db)
        assert res_candles.side == "sell"
        assert len(res_candles.candles) == 22
        assert len(res_candles.ema9) == 14
        assert len(res_candles.rsi14) == 22

        with patch(
            "src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook",
            return_value={
                "best_buy_price": 1063.0,
                "best_sell_price": 1069.0,
                "buy_ads": [{"price": 1063.0, "surplus_usdt": 1000.0, "banks": ["Banesco"]}],
                "sell_ads": [{"price": 1069.0, "surplus_usdt": 1500.0, "banks": ["Banesco"]}],
            },
        ):
            analytics = get_market_analytics(bank="*", ticket_ves=500_000.0, db=db)
            assert analytics.samples_total == 22
            assert analytics.rsi14_current is not None
            assert analytics.depth_summary.top5.buy_usdt >= 0.0

        res_evo = get_market_candles(side="evolucion", timeframe="5m", bank="*", ticket_ves=1_000_000.0, limit=100, db=db)
        assert len(res_evo.bcv_series) == 22
        assert res_evo.bcv_series[-1].value == 918.76

        res_brecha = get_market_candles(side="brecha", timeframe="5m", bank="*", ticket_ves=1_000_000.0, limit=100, db=db)
        assert len(res_brecha.candles) == 22
    finally:
        db.close()


def test_trigger_market_collect_enforces_cooldown():
    """Verifica captura manual /api/market/collect y cooldown anti-spam de 15s."""
    from src.api.routes import market as market_route

    db = _make_db()
    try:
        market_route._LAST_COLLECT_MONO = 0.0
        mock_book = {
            "best_buy_price": 1062.0,
            "best_sell_price": 1068.0,
            "buy_ads": [{"price": 1062.0, "surplus_usdt": 600.0, "banks": ["Banesco"]}],
            "sell_ads": [{"price": 1068.0, "surplus_usdt": 900.0, "banks": ["Banesco"]}],
        }
        with (
            patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", return_value=mock_book),
            patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 918.76}),
        ):
            first = market_route.trigger_market_collect(db=db, bank="*")
            assert first.captured is True
            assert first.cooldown_remaining_s == 0.0

            second = market_route.trigger_market_collect(db=db, bank="*")
            assert second.captured is False
            assert second.cooldown_remaining_s > 0.0
    finally:
        market_route._LAST_COLLECT_MONO = 0.0
        db.close()
