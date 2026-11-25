"""Endpoints REST para Terminal de Velas P2P, Profundidad de Libro y Predictor Estadístico."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.core.market_analytics import (
    MIN_PREDICTION_DAYS,
    TIMEFRAME_SECONDS,
    MarketCollectorService,
    aggregate_bank_snapshot,
    aggregate_candles,
    backtest_percentile_band,
    chain_candles,
    compute_brecha_velocity,
    compute_depth_summary,
    compute_ema_series,
    compute_liquidity_anomaly,
    compute_percentile_band,
    compute_rsi_series,
    compute_vwap_for_ticket,
    count_history_maturity,
    extract_daily_closes,
    hampel_filter,
    to_utc_epoch,
)
from src.core.spread_monitor import SpreadMonitor
from src.data.models import MarketHourlyRollup, MarketSnapshot
from src.data.repositories import MarketDataRepository
from src.reporting.bcv_history_service import BCVHistoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["Velas y Mercado P2P"])

_COLLECT_COOLDOWN_SECONDS = 15.0
_COLLECT_LOCK = threading.Lock()
_LAST_COLLECT_MONO = 0.0

DEFAULT_BANK_OPTIONS: list[str] = [
    "*",
    "Banesco",
    "Pago Móvil",
    "Banco de Venezuela",
    "Mercantil",
    "Bancamiga",
    "BBVA Banco Provincial",
    "BNC Banco Nacional de Crédito",
]


class CandlePoint(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class LinePoint(BaseModel):
    time: int
    value: float | None = None


class PercentileBandOut(BaseModel):
    floor: float
    ceiling: float
    coverage: float
    r_low_pct: float
    r_high_pct: float


class BandBacktestOut(BaseModel):
    hits: int
    evaluated: int
    hit_rate_pct: float


class MarketCandlesResponse(BaseModel):
    side: str
    timeframe: str
    bank: str
    ticket_ves: float
    candles: list[CandlePoint]
    ema9: list[LinePoint]
    ema21: list[LinePoint]
    rsi14: list[LinePoint]
    bcv_series: list[LinePoint]
    band: PercentileBandOut | None = None
    mature_days: int
    samples_total: int
    bank_options: list[str]
    warnings: list[str]


class DepthBucketOut(BaseModel):
    buy_usdt: float
    sell_usdt: float
    top1_share_pct: float
    imbalance: float


class DepthSummaryOut(BaseModel):
    top5: DepthBucketOut
    top10: DepthBucketOut
    top20: DepthBucketOut
    imbalance: float


class TicketVwapOut(BaseModel):
    fillable: bool
    vwap_price: float
    best_price: float
    slippage_pct: float
    top_price_covers_ticket: bool
    covered_ves: float
    ads_needed: int


class LiquidityAlertOut(BaseModel):
    detected: bool
    ratio_pct: float | None = None
    baseline_median_usdt: float | None = None
    status: str


class BankHourCellOut(BaseModel):
    bank: str
    sell_best: float
    sell_avg: float
    buy_best: float
    buy_avg: float
    sustained_high_pc: float | None = None
    vol_buy: float
    vol_sell: float
    buy_ads_count: int = 0
    sell_ads_count: int = 0


class MarketOrderFlowOut(BaseModel):
    """Conteo en vivo de anuncios/órdenes Compra vs Venta para el banco seleccionado."""
    bank_filter: str
    total_buy_ads: int
    total_sell_ads: int
    buy_ads_share_pct: float
    sell_ads_share_pct: float
    buy_merchants_count: int
    sell_merchants_count: int
    buy_month_orders_sum: int
    sell_month_orders_sum: int
    pressure_label: str


class MarketAnalyticsResponse(BaseModel):
    rsi14_current: float | None = None
    ema4_vs_ema12_pct: float | None = None
    ema5_vs_ema20_pct: float | None = None
    brecha_velocity: float | None = None
    depth_summary: DepthSummaryOut
    order_flow: MarketOrderFlowOut
    vwap_buy: TicketVwapOut
    vwap_sell: TicketVwapOut
    liquidity_alert: LiquidityAlertOut
    band: PercentileBandOut | None = None
    band_backtest: BandBacktestOut | None = None
    samples_total: int
    days_count: int
    min_prediction_days: int
    live_bcv: float
    live_p2p_buy: float
    live_p2p_sell: float
    brecha_pct: float
    banks_snapshot: list[BankHourCellOut]
    verdict_label: str
    warnings: list[str]


class CollectTriggerResponse(BaseModel):
    captured: bool
    cooldown_remaining_s: float
    message: str
    snapshot_timestamp: str | None = None


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if not raw or not isinstance(raw, str):
        return {}
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    except ValueError:
        return {}


def _snapshot_price_for_side(snap: MarketSnapshot, side: str, bank: str) -> float:
    if bank and bank not in ("*", "Todos") and snap.depth_json:
        depth_payload = _parse_json_dict(snap.depth_json)
        banks = depth_payload.get("banks")
        if isinstance(banks, dict):
            bank_cell = banks.get(bank)
            if isinstance(bank_cell, dict):
                if side == "buy":
                    val = float(bank_cell.get("buy_best") or bank_cell.get("buy_avg") or 0.0)
                else:
                    val = float(bank_cell.get("sell_best") or bank_cell.get("sell_avg") or 0.0)
                if val > 0:
                    return val

    if side == "buy":
        return float(cast(float, snap.p2p_buy_avg20) or cast(float, snap.p2p_buy_best) or 0.0)
    if side == "brecha":
        return float(cast(float, snap.brecha_pct) or 0.0)
    if side == "evolucion":
        return float(cast(float, snap.p2p_mid) or cast(float, snap.p2p_sell_avg20) or 0.0)
    return float(cast(float, snap.p2p_sell_avg20) or cast(float, snap.p2p_sell_best) or 0.0)


def _rollup_ohlc_for_side(rollup: MarketHourlyRollup, side: str, bank: str) -> dict[str, float] | float:
    if bank and bank not in ("*", "Todos") and rollup.bank_matrix_json:
        matrix = _parse_json_dict(rollup.bank_matrix_json)
        bank_entry = matrix.get(bank)
        if isinstance(bank_entry, dict):
            side_key = "buy" if side == "buy" else "sell"
            side_cell = bank_entry.get(side_key)
            if isinstance(side_cell, dict) and "o" in side_cell:
                return {
                    "open": float(side_cell["o"]),
                    "high": float(side_cell["p"]),
                    "low": float(side_cell["x"]),
                    "close": float(side_cell["d"]),
                }

    if side == "buy":
        return {
            "open": float(cast(float, rollup.buy_open) or 0.0),
            "high": float(cast(float, rollup.buy_high) or 0.0),
            "low": float(cast(float, rollup.buy_low) or 0.0),
            "close": float(cast(float, rollup.buy_close) or 0.0),
        }
    if side == "brecha":
        return float(cast(float, rollup.brecha_close) or 0.0)
    if side == "evolucion":
        mid_open = (float(cast(float, rollup.buy_open)) + float(cast(float, rollup.sell_open))) / 2.0
        mid_high = (float(cast(float, rollup.buy_high)) + float(cast(float, rollup.sell_high))) / 2.0
        mid_low = (float(cast(float, rollup.buy_low)) + float(cast(float, rollup.sell_low))) / 2.0
        mid_close = (float(cast(float, rollup.buy_close)) + float(cast(float, rollup.sell_close))) / 2.0
        return {
            "open": round(mid_open, 4),
            "high": round(mid_high, 4),
            "low": round(mid_low, 4),
            "close": round(mid_close, 4),
        }
    return {
        "open": float(cast(float, rollup.sell_open) or 0.0),
        "high": float(cast(float, rollup.sell_high) or 0.0),
        "low": float(cast(float, rollup.sell_low) or 0.0),
        "close": float(cast(float, rollup.sell_close) or 0.0),
    }


@router.get("/candles", response_model=MarketCandlesResponse)
def get_market_candles(
    db: Annotated[Session, Depends(get_db)],
    side: Annotated[str, Query(pattern="^(sell|buy|bank|evolucion|brecha)$")] = "sell",
    timeframe: Annotated[str, Query(pattern="^(1m|5m|15m|1h|4h|1D)$")] = "5m",
    bank: Annotated[str, Query(max_length=64)] = "*",
    ticket_ves: Annotated[float, Query(gt=0.0, le=500_000_000.0)] = 1_000_000.0,
    limit: Annotated[int, Query(ge=10, le=500)] = 240,
) -> MarketCandlesResponse:
    """Devuelve velas OHLC filtradas por Hampel, EMAs 9/21, RSI 14 alineado y serie BCV."""
    repo = MarketDataRepository(db)
    bucket_seconds = TIMEFRAME_SECONDS.get(timeframe, 300)
    maturity = count_history_maturity(db)
    rollups = repo.list_hourly_rollups(limit=min(limit * 4, 2000))
    use_rollups = timeframe in ("1h", "4h", "1D") and len(rollups) >= 3
    snapshots = repo.list_snapshots(limit=360 if use_rollups else min(limit * 6, 3000))
    warnings: list[str] = []
    candles_raw: list[dict[str, Any]] = []
    bcv_by_bucket: dict[int, float] = {}

    if use_rollups:
        cleaned_rollups = (
            hampel_filter(
                rollups,
                value_fn=lambda r: float(cast(float, r.sell_close) or 0.0),
                window=8,
                threshold=4.0,
            )
            if side != "brecha" and len(rollups) >= 10
            else rollups
        )
        candles_raw = aggregate_candles(
            cleaned_rollups,
            bucket_seconds=bucket_seconds,
            time_fn=lambda r: to_utc_epoch(cast(datetime, r.hora_utc)),
            ohlc_fn=lambda r: _rollup_ohlc_for_side(r, side, bank),
            vol_fn=lambda r: float(cast(float, r.vol_sell_sum) if side != "buy" else cast(float, r.vol_buy_sum)),
        )
        for r in cleaned_rollups:
            b_ts = (to_utc_epoch(cast(datetime, r.hora_utc)) // bucket_seconds) * bucket_seconds
            bcv_val = float(cast(float, r.bcv_close) or 0.0)
            if bcv_val > 0:
                bcv_by_bucket[b_ts] = round(bcv_val, 4)
    elif snapshots:
        valid_snaps = [
            s for s in snapshots if _snapshot_price_for_side(s, side, bank) > 0 or side == "brecha"
        ]
        cleaned_snaps = (
            hampel_filter(
                valid_snaps,
                value_fn=lambda s: _snapshot_price_for_side(s, side, bank),
                window=8,
                threshold=4.0,
            )
            if side != "brecha" and len(valid_snaps) >= 10
            else valid_snaps
        )
        candles_raw = aggregate_candles(
            cleaned_snaps,
            bucket_seconds=bucket_seconds,
            time_fn=lambda s: to_utc_epoch(cast(datetime, s.timestamp)),
            ohlc_fn=lambda s: _snapshot_price_for_side(s, side, bank),
            vol_fn=lambda s: float(
                cast(float, s.vol_buy_usdt) if side == "buy" else cast(float, s.vol_sell_usdt)
            ),
        )
        for s in cleaned_snaps:
            b_ts = (to_utc_epoch(cast(datetime, s.timestamp)) // bucket_seconds) * bucket_seconds
            bcv_val = float(cast(float, s.bcv_rate) or 0.0)
            if bcv_val > 0:
                bcv_by_bucket[b_ts] = round(bcv_val, 4)

    chained = chain_candles(candles_raw)[-limit:]
    ema9 = compute_ema_series(chained, 9)
    ema21 = compute_ema_series(chained, 21)
    rsi14 = compute_rsi_series(chained, 14)

    bcv_series: list[dict[str, Any]] = []
    last_bcv: float | None = None
    for c in chained:
        t = int(c["time"])
        if t in bcv_by_bucket:
            last_bcv = bcv_by_bucket[t]
        bcv_series.append({"time": t, "value": last_bcv})

    band_data: dict[str, float] | None = None
    if chained:
        daily_side = "buy" if side == "buy" else ("brecha" if side == "brecha" else "sell")
        daily_closes = extract_daily_closes(rollups, snapshots, side=daily_side)
        band_data = compute_percentile_band(
            daily_closes,
            anchor_price=float(chained[-1]["close"]),
            coverage=0.90,
            min_days=MIN_PREDICTION_DAYS,
        )

    if not chained:
        warnings.append(
            "Aún no hay lecturas guardadas. Pulsa 'Capturar ahora' o espera 2 min al recolector automático."
        )
    if maturity["days_count"] < MIN_PREDICTION_DAYS:
        warnings.append(
            f"Rango histórico en construcción ({maturity['days_count']}/{MIN_PREDICTION_DAYS} días). "
            f"El piso y techo estadístico se activará al completar {MIN_PREDICTION_DAYS} días cerrados."
        )

    return MarketCandlesResponse(
        side=side,
        timeframe=timeframe,
        bank=bank,
        ticket_ves=ticket_ves,
        candles=[CandlePoint(**c) for c in chained],
        ema9=[LinePoint(**p) for p in ema9],
        ema21=[LinePoint(**p) for p in ema21],
        rsi14=[LinePoint(**p) for p in rsi14],
        bcv_series=[LinePoint(**p) for p in bcv_series],
        band=PercentileBandOut(**band_data) if band_data else None,
        mature_days=maturity["days_count"],
        samples_total=maturity["samples_total"],
        bank_options=DEFAULT_BANK_OPTIONS,
        warnings=warnings,
    )


def _ema_spread_pct(candles: list[dict[str, Any]], fast: int, slow: int) -> float | None:
    fast_series = compute_ema_series(candles, fast)
    slow_series = compute_ema_series(candles, slow)
    if not fast_series or not slow_series:
        return None
    f_val = float(fast_series[-1]["value"])
    s_val = float(slow_series[-1]["value"])
    if s_val <= 0:
        return None
    return round(((f_val - s_val) / s_val) * 100.0, 4)


def _build_verdict(
    rsi_val: float | None,
    ema4_12: float | None,
    imbalance: float,
    candles_count: int,
) -> str:
    if candles_count < 15 or rsi_val is None:
        missing = max(1, 15 - candles_count)
        return f"Faltan {missing} velas (~{missing * 2} min) para medir fuerza compra/venta"
    if rsi_val >= 70.0:
        return "Tasa extendida al alza · Posible pausa o toma de ganancia"
    if rsi_val <= 30.0:
        return "Tasa golpeada a la baja · Posible rebote próximo"
    if ema4_12 is not None and ema4_12 > 0.08 and imbalance > 0.10:
        return "Impulso comprador · Más demanda que oferta"
    if ema4_12 is not None and ema4_12 < -0.08 and imbalance < -0.10:
        return "Presión bajista · Más oferta en anuncios"
    return "Mercado estable · Sin extremos de compra ni venta"


@router.get("/analytics", response_model=MarketAnalyticsResponse)
def get_market_analytics(
    db: Annotated[Session, Depends(get_db)],
    bank: Annotated[str, Query(max_length=64)] = "*",
    ticket_ves: Annotated[float, Query(gt=0.0, le=500_000_000.0)] = 1_000_000.0,
    side: Annotated[str, Query(pattern="^(sell|buy|bank|evolucion|brecha)$")] = "sell",
) -> MarketAnalyticsResponse:
    """Calcula KPIs en vivo, VWAP exacto por ticket en Bs, profundidad Top 5/10/20 y backtest."""
    repo = MarketDataRepository(db)
    maturity = count_history_maturity(db)
    snapshots = repo.list_snapshots(limit=500)
    rollups = repo.list_hourly_rollups(limit=200)
    warnings: list[str] = []

    mapped_bank = "Todos" if not bank or bank.strip() in ("*", "Todos") else bank.strip()
    buy_ads: list[dict[str, Any]] = []
    sell_ads: list[dict[str, Any]] = []
    book: dict[str, Any] = {}
    live_p2p_buy = 0.0
    live_p2p_sell = 0.0

    try:
        book = SpreadMonitor().fetch_filtered_orderbook(
            amount_usdt=100.0,
            amount_ves=ticket_ves,
            bank=mapped_bank,
            rows=20,
        )
        buy_ads = list(book.get("buy_ads") or [])
        sell_ads = list(book.get("sell_ads") or [])
        live_p2p_buy = float(book.get("best_buy_price") or 0.0)
        live_p2p_sell = float(book.get("best_sell_price") or 0.0)
    except (httpx.HTTPError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.warning("Fallo consultando libro Binance P2P para /api/market/analytics: %s", exc)
        warnings.append("Libro Binance temporalmente inaccesible; mostrando último snapshot local.")
        if snapshots:
            last_s = snapshots[-1]
            live_p2p_buy = float(cast(float, last_s.p2p_buy_best) or 0.0)
            live_p2p_sell = float(cast(float, last_s.p2p_sell_best) or 0.0)

    live_bcv = 0.0
    try:
        bcv_data = BCVHistoryService(db).get_or_fetch_current_rates()
        live_bcv = float((bcv_data or {}).get("usd") or 0.0)
    except (httpx.HTTPError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.warning("Fallo obteniendo BCV vivo: %s", exc)
    if live_bcv <= 0 and snapshots:
        live_bcv = float(cast(float, snapshots[-1].bcv_rate) or 0.0)

    mid = (
        (live_p2p_buy + live_p2p_sell) / 2.0
        if (live_p2p_buy > 0 and live_p2p_sell > 0)
        else (live_p2p_sell or live_p2p_buy)
    )
    brecha_pct = round(((mid - live_bcv) / live_bcv) * 100.0, 2) if (live_bcv > 0 and mid > 0) else 0.0

    depth_dict = compute_depth_summary(buy_ads, sell_ads)
    vwap_buy_dict = compute_vwap_for_ticket(buy_ads, ticket_ves)
    vwap_sell_dict = compute_vwap_for_ticket(sell_ads, ticket_ves)

    candles = chain_candles(
        aggregate_candles(
            snapshots,
            bucket_seconds=300,
            time_fn=lambda s: to_utc_epoch(cast(datetime, s.timestamp)),
            ohlc_fn=lambda s: _snapshot_price_for_side(s, side, bank),
        )
    )
    if len(candles) < 15 and len(snapshots) >= 15:
        candles = chain_candles(
            aggregate_candles(
                snapshots,
                bucket_seconds=60,
                time_fn=lambda s: to_utc_epoch(cast(datetime, s.timestamp)),
                ohlc_fn=lambda s: _snapshot_price_for_side(s, side, bank),
            )
        )
    rsi_series = compute_rsi_series(candles, 14)
    rsi14_current: float | None = None
    for pt in reversed(rsi_series):
        if pt["value"] is not None:
            rsi14_current = float(pt["value"])
            break

    ema4_12 = _ema_spread_pct(candles, 4, 12)
    ema5_20 = _ema_spread_pct(candles, 5, 20)
    brecha_vel = compute_brecha_velocity(snapshots)

    cutoff_2h = (datetime.now(UTC) - timedelta(hours=2)).replace(tzinfo=None)
    recent_2h = [s for s in snapshots if cast(datetime, s.timestamp) >= cutoff_2h]
    current_tot_vol = float(depth_dict["top20"]["buy_usdt"]) + float(depth_dict["top20"]["sell_usdt"])
    liq_alert = compute_liquidity_anomaly(recent_2h, current_tot_vol)

    daily_closes = extract_daily_closes(rollups, snapshots, side="sell")
    anchor = mid if mid > 0 else (daily_closes[-1] if daily_closes else 0.0)
    band_data = (
        compute_percentile_band(daily_closes, anchor_price=anchor, coverage=0.90)
        if anchor > 0
        else None
    )
    bt_data = backtest_percentile_band(daily_closes, coverage=0.90)

    # Desglose por banco combinando libro vivo + máximo sostenido (pc) del último rollup horario
    sustained_map: dict[str, float | None] = {}
    if rollups:
        latest_matrix = _parse_json_dict(rollups[-1].bank_matrix_json)
        for b_name, entry in latest_matrix.items():
            if isinstance(entry, dict) and isinstance(entry.get("sell"), dict):
                pc_val = entry["sell"].get("pc")
                sustained_map[str(b_name)] = float(pc_val) if pc_val is not None else None

    live_bank_stats = aggregate_bank_snapshot(buy_ads, sell_ads)
    banks_snapshot: list[BankHourCellOut] = []
    for b_name, st in sorted(
        live_bank_stats.items(),
        key=lambda kv: kv[1]["vol_buy"] + kv[1]["vol_sell"],
        reverse=True,
    )[:8]:
        banks_snapshot.append(
            BankHourCellOut(
                bank=b_name,
                sell_best=st["sell_best"],
                sell_avg=st["sell_avg"],
                buy_best=st["buy_best"],
                buy_avg=st["buy_avg"],
                sustained_high_pc=sustained_map.get(b_name),
                vol_buy=st["vol_buy"],
                vol_sell=st["vol_sell"],
                buy_ads_count=int(st.get("buy_ads_count") or 0),
                sell_ads_count=int(st.get("sell_ads_count") or 0),
            )
        )

    total_buy_ads = int(book.get("total_buy_ads") or len(buy_ads))
    total_sell_ads = int(book.get("total_sell_ads") or len(sell_ads))
    tot_flow = total_buy_ads + total_sell_ads
    buy_share = (
        float(book["buy_ads_share_pct"])
        if "buy_ads_share_pct" in book
        else (round((total_buy_ads / tot_flow) * 100.0, 1) if tot_flow > 0 else 50.0)
    )
    sell_share = (
        float(book["sell_ads_share_pct"])
        if "sell_ads_share_pct" in book
        else (round(100.0 - buy_share, 1) if tot_flow > 0 else 50.0)
    )
    buy_merchants = int(
        book["buy_merchants_count"]
        if book.get("buy_merchants_count") is not None
        else sum(1 for a in buy_ads if a.get("is_merchant"))
    )
    sell_merchants = int(
        book["sell_merchants_count"]
        if book.get("sell_merchants_count") is not None
        else sum(1 for a in sell_ads if a.get("is_merchant"))
    )
    buy_m_orders = int(
        book["buy_month_orders_sum"]
        if book.get("buy_month_orders_sum") is not None
        else sum(int(a.get("month_orders") or 0) for a in buy_ads)
    )
    sell_m_orders = int(
        book["sell_month_orders_sum"]
        if book.get("sell_month_orders_sum") is not None
        else sum(int(a.get("month_orders") or 0) for a in sell_ads)
    )
    default_pressure = (
        "Sin anuncios activos para este banco"
        if tot_flow == 0
        else (
            f"Mayor demanda de compra ({sell_share:.0f}% Venta vs {buy_share:.0f}% Compra)"
            if sell_share >= 58.0
            else (
                f"Mayor oferta disponible ({buy_share:.0f}% Compra vs {sell_share:.0f}% Venta)"
                if buy_share >= 58.0
                else f"Libro equilibrado ({buy_share:.0f}% Compra · {sell_share:.0f}% Venta)"
            )
        )
    )
    order_flow = MarketOrderFlowOut(
        bank_filter=mapped_bank,
        total_buy_ads=total_buy_ads,
        total_sell_ads=total_sell_ads,
        buy_ads_share_pct=buy_share,
        sell_ads_share_pct=sell_share,
        buy_merchants_count=buy_merchants,
        sell_merchants_count=sell_merchants,
        buy_month_orders_sum=buy_m_orders,
        sell_month_orders_sum=sell_m_orders,
        pressure_label=str(book.get("market_pressure_label") or default_pressure),
    )

    if maturity["days_count"] < MIN_PREDICTION_DAYS:
        warnings.append(
            f"Rango histórico en construcción ({maturity['days_count']}/{MIN_PREDICTION_DAYS} días)."
        )

    verdict = _build_verdict(
        rsi14_current,
        ema4_12,
        float(depth_dict["imbalance"]),
        len(candles),
    )

    return MarketAnalyticsResponse(
        rsi14_current=rsi14_current,
        ema4_vs_ema12_pct=ema4_12,
        ema5_vs_ema20_pct=ema5_20,
        brecha_velocity=brecha_vel,
        depth_summary=DepthSummaryOut(
            top5=DepthBucketOut(**depth_dict["top5"]),
            top10=DepthBucketOut(**depth_dict["top10"]),
            top20=DepthBucketOut(**depth_dict["top20"]),
            imbalance=float(depth_dict["imbalance"]),
        ),
        order_flow=order_flow,
        vwap_buy=TicketVwapOut(**vwap_buy_dict),
        vwap_sell=TicketVwapOut(**vwap_sell_dict),
        liquidity_alert=LiquidityAlertOut(**liq_alert),
        band=PercentileBandOut(**band_data) if band_data else None,
        band_backtest=BandBacktestOut(**bt_data) if bt_data else None,
        samples_total=maturity["samples_total"],
        days_count=maturity["days_count"],
        min_prediction_days=MIN_PREDICTION_DAYS,
        live_bcv=round(live_bcv, 4),
        live_p2p_buy=round(live_p2p_buy, 4),
        live_p2p_sell=round(live_p2p_sell, 4),
        brecha_pct=brecha_pct,
        banks_snapshot=banks_snapshot,
        verdict_label=verdict,
        warnings=warnings,
    )


@router.post("/collect", response_model=CollectTriggerResponse)
def trigger_market_collect(
    db: Annotated[Session, Depends(get_db)],
    bank: Annotated[str, Query(max_length=64)] = "*",
    ticket_ves: Annotated[float | None, Query(gt=0.0, le=500_000_000.0)] = None,
) -> CollectTriggerResponse:
    """Dispara captura manual inmediata de velas/profundidad con cooldown anti-spam de 15s."""
    global _LAST_COLLECT_MONO

    now_m = time.monotonic()
    with _COLLECT_LOCK:
        elapsed = now_m - _LAST_COLLECT_MONO
        if _LAST_COLLECT_MONO > 0 and elapsed < _COLLECT_COOLDOWN_SECONDS:
            remaining = round(_COLLECT_COOLDOWN_SECONDS - elapsed, 1)
            return CollectTriggerResponse(
                captured=False,
                cooldown_remaining_s=remaining,
                message=f"Espera {remaining}s antes de guardar otra lectura en vivo.",
            )
        _LAST_COLLECT_MONO = now_m

    try:
        snap = MarketCollectorService(db).capture_snapshot(
            bank_filter=bank,
            ticket_ves=ticket_ves,
        )
    except (httpx.HTTPError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.warning("Captura manual de mercado abortada (Fail-Closed): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo consultar Binance P2P en vivo en este momento.",
        ) from exc

    ts = cast(datetime, snap.timestamp)
    return CollectTriggerResponse(
        captured=True,
        cooldown_remaining_s=0.0,
        message="Lectura en vivo guardada y añadida al gráfico.",
        snapshot_timestamp=(ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts).isoformat(),
    )
