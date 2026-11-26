"""Pruebas TDD para SPEC-027: filtros reales de Velas P2P, 3 tickets históricos, cero datos inventados,
seguridad de /api/market/collect, retención NVMe y bloqueo de datos calibrados en producción.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.spread_monitor import SpreadMonitor
from src.data.database import Base
from src.data.models import MarketHourlyRollup, MarketSnapshot, User


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_resolve_binance_pay_types_covers_all_velas_dropdown_banks() -> None:
    """Todos los bancos del selector de Velas P2P deben mapear a payTypes reales de Binance."""
    from src.api.routes.market import DEFAULT_BANK_OPTIONS

    for bank_opt in DEFAULT_BANK_OPTIONS:
        if bank_opt == "*":
            assert SpreadMonitor.resolve_binance_pay_types(bank_opt) == []
            continue
        pay_types = SpreadMonitor.resolve_binance_pay_types(bank_opt)
        assert len(pay_types) >= 1, f"El banco '{bank_opt}' devolvió pay_types vacío y mezclaría todos los bancos"


def test_market_candles_never_fall_back_to_global_price_for_missing_bank() -> None:
    """Al filtrar por un banco sin presencia en el snapshot/rollup, jamás debe devolver el precio global '*'."""
    from src.api.routes.market import get_market_candles

    db = _make_db()
    try:
        base_dt = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
        for i in range(6):
            dt = base_dt + timedelta(minutes=5 * i)
            # Snapshots globales que solo contienen Banesco, nunca Mercantil
            db.add(
                MarketSnapshot(
                    timestamp=dt.replace(tzinfo=None),
                    bcv_rate=920.0,
                    p2p_buy_best=1100.0,
                    p2p_buy_avg20=1102.0,
                    p2p_sell_best=1110.0,
                    p2p_sell_avg20=1108.0,
                    p2p_mid=1105.0,
                    brecha_pct=20.1,
                    spread_ves=6.0,
                    vol_buy_usdt=5000.0,
                    vol_sell_usdt=6000.0,
                    depth_json=json.dumps(
                        {
                            "depth": {},
                            "banks": {
                                "Banesco": {
                                    "buy_best": 1100.0,
                                    "buy_avg": 1101.0,
                                    "sell_best": 1110.0,
                                    "sell_avg": 1109.0,
                                    "vol_buy": 5000.0,
                                    "vol_sell": 6000.0,
                                }
                            },
                        }
                    ),
                )
            )
            db.add(
                MarketHourlyRollup(
                    hora_utc=(base_dt + timedelta(hours=i)).replace(minute=0, second=0, microsecond=0, tzinfo=None),
                    buy_open=1100.0,
                    buy_high=1102.0,
                    buy_low=1099.0,
                    buy_close=1101.0,
                    sell_open=1108.0,
                    sell_high=1110.0,
                    sell_low=1107.0,
                    sell_close=1109.0,
                    bcv_close=920.0,
                    brecha_close=20.0,
                    vol_buy_sum=5000.0,
                    vol_sell_sum=6000.0,
                    samples_count=1,
                    bank_matrix_json=json.dumps({"Banesco": {"sell": {"o": 1108, "p": 1110, "x": 1107, "d": 1109, "u": 6000}}}),
                )
            )
        db.commit()

        res_5m = get_market_candles(side="bank", timeframe="5m", bank="Mercantil", ticket_ves=1_000_000.0, limit=50, db=db)
        assert res_5m.candles == []
        assert any("Mercantil" in w or "sin lecturas" in w.lower() for w in res_5m.warnings)

        res_1h = get_market_candles(side="bank", timeframe="1h", bank="Mercantil", ticket_ves=1_000_000.0, limit=50, db=db)
        assert res_1h.candles == []
    finally:
        db.close()


def test_tracked_three_tickets_capture_and_return_distinct_real_candles() -> None:
    """Velas P2P debe recolectar y servir series reales distintas para los 3 tramos (250K, 1M, 5M Bs)."""
    from src.api.routes.market import get_market_candles
    from src.core.market_analytics import TRACKED_TICKET_BUCKETS_VES, MarketCollectorService

    assert set(TRACKED_TICKET_BUCKETS_VES) == {250_000, 1_000_000, 5_000_000}

    db = _make_db()
    try:
        def fake_filtered_orderbook(self, amount_usdt=100.0, amount_ves=None, bank="Todos", merchant_only=False, rows=20, client=None):
            amt = float(amount_ves or 0.0)
            if amt >= 4_500_000:
                buy_p, sell_p = 1125.0, 1135.0
            elif amt >= 900_000:
                buy_p, sell_p = 1112.0, 1120.0
            elif amt >= 200_000:
                buy_p, sell_p = 1104.0, 1110.0
            else:
                buy_p, sell_p = 1101.0, 1106.0
            return {
                "best_buy_price": buy_p,
                "best_sell_price": sell_p,
                "buy_ads": [{"price": buy_p, "surplus_usdt": 8000.0, "banks": ["Banesco"]}],
                "sell_ads": [{"price": sell_p, "surplus_usdt": 9000.0, "banks": ["Banesco"]}],
            }

        collector = MarketCollectorService(db)
        with (
            patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", fake_filtered_orderbook),
            patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 920.0}),
        ):
            t0 = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
            collector.capture_snapshot(now_utc=t0)
            collector.capture_snapshot(now_utc=t0 + timedelta(minutes=5))

        c_250k = get_market_candles(side="sell", timeframe="5m", bank="*", ticket_ves=250_000.0, limit=50, db=db)
        c_5m = get_market_candles(side="sell", timeframe="5m", bank="*", ticket_ves=5_000_000.0, limit=50, db=db)

        assert len(c_250k.candles) == 2
        assert len(c_5m.candles) == 2
        assert c_250k.candles[-1].close == pytest.approx(1110.0, abs=0.1)
        assert c_5m.candles[-1].close == pytest.approx(1135.0, abs=0.1)
        assert c_5m.candles[-1].close > c_250k.candles[-1].close

        # Monto personalizado intermedio no inventa velas falsas y advierte claramente
        c_custom = get_market_candles(side="sell", timeframe="5m", bank="*", ticket_ves=777_000.0, limit=50, db=db)
        assert any("VWAP" in w or "personalizado" in w.lower() for w in c_custom.warnings)
    finally:
        db.close()


def test_trigger_market_collect_requires_auth_and_never_corrupts_global_series() -> None:
    """POST /api/market/collect debe exigir usuario autenticado y no ensuciar la serie global con filtros."""
    from src.api.routes import market as market_route

    sig = inspect.signature(market_route.trigger_market_collect)
    assert "current_user" in sig.parameters, "trigger_market_collect debe exigir current_user autenticado"

    db = _make_db()
    try:
        market_route._LAST_COLLECT_MONO = 0.0
        trader = User(username="trader_velas", password_hash="x", role="TRADER", is_active=True)
        db.add(trader)
        db.commit()
        db.refresh(trader)

        seen_calls: list[tuple[str, float | None]] = []

        def fake_book(self, amount_usdt=100.0, amount_ves=None, bank="Todos", merchant_only=False, rows=20, client=None):
            seen_calls.append((bank, amount_ves))
            # Banco específico devuelve precio exagerado si se consultara filtrado
            if bank != "Todos":
                return {
                    "best_buy_price": 1999.0,
                    "best_sell_price": 1999.0,
                    "buy_ads": [{"price": 1999.0, "surplus_usdt": 100.0, "banks": [bank]}],
                    "sell_ads": [{"price": 1999.0, "surplus_usdt": 100.0, "banks": [bank]}],
                }
            return {
                "best_buy_price": 1102.0,
                "best_sell_price": 1108.0,
                "buy_ads": [{"price": 1102.0, "surplus_usdt": 1000.0, "banks": ["Banesco"]}],
                "sell_ads": [{"price": 1108.0, "surplus_usdt": 1000.0, "banks": ["Banesco"]}],
            }

        with (
            patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", fake_book),
            patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 920.0}),
        ):
            res = market_route.trigger_market_collect(
                db=db,
                current_user=trader,
                bank="Bancamiga",
                ticket_ves=5_000_000.0,
            )
            assert res.captured is True

        snap = db.query(MarketSnapshot).first()
        assert snap is not None
        assert float(snap.p2p_sell_avg20) < 1200.0
        assert all(call_bank in ("*", "Todos") or call_bank == "Bancamiga" for call_bank, _ in seen_calls)
    finally:
        market_route._LAST_COLLECT_MONO = 0.0
        db.close()


def test_offline_fail_closed_no_calibrated_or_hardcoded_1005() -> None:
    """Sin red en producción, ni RateAlertService ni fetch_filtered_orderbook inventan tasas calibradas ni 1005.0."""
    from src.core import spread_monitor as sm_mod
    from src.core.rate_alert_service import RateAlertService

    sm_mod._ORDERBOOK_CACHE.clear()
    sm_mod._REF_RATE_CACHE.clear()
    sm_mod._VOLUME_QUOTES_CACHE.clear()

    # 1. fetch_filtered_orderbook sin Yadio ni caché no debe inventar ref_rate=1005.0 si BCV/caches faltan
    monitor = SpreadMonitor()
    with (
        patch.object(SpreadMonitor, "fetch_yadio_rate", return_value=None),
        patch("src.core.binance_client.BinanceP2PClient.search_p2p_ads", side_effect=OSError("Sin red")),
    ):
        res = monitor.fetch_filtered_orderbook(amount_usdt=100.0, bank="Mercantil")
        assert res["best_buy_price"] == 0.0
        assert res["best_sell_price"] == 0.0
        assert res["source"] == "error_fallback"
        assert res["trans_amount_ves"] == 0.0

    # 2. RateAlertService no debe caer en get_market_quotes() (1007.50 calibrado) cuando falla red
    svc = RateAlertService()
    with (
        patch.object(SpreadMonitor, "fetch_live_quotes", return_value=[]),
        patch.object(SpreadMonitor, "get_market_quotes", side_effect=AssertionError("No debe usar get_market_quotes en producción")),
    ):
        assert svc.check_bcv_rate_change(920.0, fecha_valor="2026-11-25") is None
        msg = svc.check_bcv_rate_change(925.0, fecha_valor="2026-11-26")
        assert msg is not None
        assert "N/D" in msg or "Sin datos P2P" in msg


def test_prune_old_market_snapshots_preserves_rollups() -> None:
    """La retención NVMe borra MarketSnapshot > 30 días pero conserva MarketHourlyRollup."""
    from src.data.repositories import MarketDataRepository

    db = _make_db()
    try:
        now_naive = datetime(2026, 11, 26, 12, 0, 0)
        old_dt = now_naive - timedelta(days=45)
        recent_dt = now_naive - timedelta(days=3)

        db.add(
            MarketSnapshot(
                timestamp=old_dt,
                bcv_rate=900.0,
                p2p_buy_best=1050.0,
                p2p_buy_avg20=1051.0,
                p2p_sell_best=1060.0,
                p2p_sell_avg20=1059.0,
                p2p_mid=1055.0,
                brecha_pct=17.2,
                spread_ves=8.0,
                vol_buy_usdt=1000.0,
                vol_sell_usdt=1000.0,
            )
        )
        db.add(
            MarketSnapshot(
                timestamp=recent_dt,
                bcv_rate=920.0,
                p2p_buy_best=1100.0,
                p2p_buy_avg20=1101.0,
                p2p_sell_best=1110.0,
                p2p_sell_avg20=1109.0,
                p2p_mid=1105.0,
                brecha_pct=20.1,
                spread_ves=8.0,
                vol_buy_usdt=2000.0,
                vol_sell_usdt=2000.0,
            )
        )
        db.add(
            MarketHourlyRollup(
                hora_utc=old_dt.replace(minute=0, second=0, microsecond=0),
                buy_open=1050.0,
                buy_high=1052.0,
                buy_low=1049.0,
                buy_close=1051.0,
                sell_open=1058.0,
                sell_high=1060.0,
                sell_low=1057.0,
                sell_close=1059.0,
                bcv_close=900.0,
                brecha_close=17.2,
                vol_buy_sum=1000.0,
                vol_sell_sum=1000.0,
                samples_count=10,
            )
        )
        db.commit()

        repo = MarketDataRepository(db)
        deleted = repo.prune_old_snapshots(days_keep=30, now_utc=now_naive.replace(tzinfo=UTC))
        assert deleted == 1
        assert db.query(MarketSnapshot).count() == 1
        assert db.query(MarketHourlyRollup).count() == 1
    finally:
        db.close()


def test_http_exception_imported_check() -> None:
    assert HTTPException is not None
