"""Motor cuantitativo, filtro Hampel MAD, VWAP por ticket y recolector OHLC P2P."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any, cast

from sqlalchemy.orm import Session

from src.core.spread_monitor import SpreadMonitor
from src.data.models import MarketHourlyRollup, MarketSnapshot
from src.data.repositories import MarketDataRepository
from src.reporting.bcv_history_service import BCVHistoryService

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1D": 86400,
}

MIN_PREDICTION_DAYS = 20
_HAMPEL_SCALE = 1.4826
TRACKED_TICKET_BUCKETS_VES: tuple[int, ...] = (250_000, 1_000_000, 5_000_000)
_CORE_VEN_BANKS: tuple[str, ...] = (
    "Banesco",
    "Banco de Venezuela",
    "Pago Móvil",
    "Mercantil",
    "BBVA Provincial",
    "Bancamiga",
    "BNC",
)


def match_tracked_ticket_bucket(ticket_ves: float | None) -> int | None:
    """Asocia un monto en VES a uno de los 3 tramos reales monitoreados (250K, 1M, 5M)."""
    if ticket_ves is None or ticket_ves <= 0:
        return None
    val = float(ticket_ves)
    for bucket in TRACKED_TICKET_BUCKETS_VES:
        if abs(val - float(bucket)) / float(bucket) <= 0.01:
            return bucket
    return None


def to_utc_epoch(dt: datetime) -> int:
    """Convierte un datetime naive (asumido UTC en SQLite) o aware a epoch UTC entero."""
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return int(aware.timestamp())


def hampel_filter[T](
    items: Sequence[T],
    value_fn: Callable[[T], float | None],
    window: int = 8,
    threshold: float = 4.0,
) -> list[T]:
    """Filtra outliers estadísticos mediante Mediana y MAD móvil sin achatar tendencias reales."""
    if not items:
        return []

    raw_vals: list[float | None] = []
    for item in items:
        val = value_fn(item)
        if val is None or not math.isfinite(val):
            raw_vals.append(None)
        else:
            raw_vals.append(float(val))

    n = len(items)
    half = max(1, window // 2)
    cleaned: list[T] = []

    for idx, item in enumerate(items):
        val = raw_vals[idx]
        if val is None:
            continue

        lo = max(0, idx - half)
        hi = min(n, idx + half + 1)
        win_vals = [v for v in raw_vals[lo:hi] if v is not None]
        if len(win_vals) < 3:
            cleaned.append(item)
            continue

        med = float(median(win_vals))
        devs = [abs(v - med) for v in win_vals]
        mad = float(median(devs))

        if mad > 0.0:
            sigma = _HAMPEL_SCALE * mad
            if abs(val - med) <= threshold * sigma:
                cleaned.append(item)
        else:
            # Si >50% de la ventana es idéntica (MAD=0), rechazar saltos extremos aislados >3%
            rel_diff = abs(val - med) / abs(med) if abs(med) > 1e-9 else abs(val - med)
            if rel_diff <= 0.03:
                cleaned.append(item)

    return cleaned


def _extract_ohlc(val: float | dict[str, Any]) -> tuple[float, float, float, float]:
    if isinstance(val, dict):
        o = float(val["open"])
        h = float(val["high"])
        low_v = float(val["low"])
        c = float(val["close"])
        return o, max(h, o, c), min(low_v, o, c), c
    v = float(val)
    return v, v, v, v


def aggregate_candles[T](
    items: Sequence[T],
    bucket_seconds: int,
    time_fn: Callable[[T], int],
    ohlc_fn: Callable[[T], float | dict[str, float]],
    vol_fn: Callable[[T], float | None] | None = None,
) -> list[dict[str, Any]]:
    """Agrupa lecturas o sub-velas en cubetas temporales exactas OHLC + volumen opcional."""
    if not items:
        return []

    safe_bucket = max(1, int(bucket_seconds))
    buckets: dict[int, list[tuple[int, int, T]]] = defaultdict(list)

    for order_idx, item in enumerate(items):
        raw_ts = int(time_fn(item))
        bucket_ts = (raw_ts // safe_bucket) * safe_bucket
        buckets[bucket_ts].append((raw_ts, order_idx, item))

    candles: list[dict[str, Any]] = []
    for bucket_ts in sorted(buckets.keys()):
        group = sorted(buckets[bucket_ts], key=lambda x: (x[0], x[1]))
        first_o, high_p, low_p, close_p = _extract_ohlc(ohlc_fn(group[0][2]))
        vols: list[float] = []

        for idx, (_, _, obj) in enumerate(group):
            o, h, low_v, c = _extract_ohlc(ohlc_fn(obj))
            if idx == 0:
                first_o = o
            high_p = max(high_p, h)
            low_p = min(low_p, low_v)
            close_p = c

            if vol_fn is not None:
                v_raw = vol_fn(obj)
                if v_raw is not None and math.isfinite(float(v_raw)):
                    vols.append(float(v_raw))

        vol_total = round(sum(vols), 4) if (vol_fn is not None and vols) else None
        candles.append(
            {
                "time": bucket_ts,
                "open": round(first_o, 4),
                "high": round(high_p, 4),
                "low": round(low_p, 4),
                "close": round(close_p, 4),
                "volume": vol_total,
            }
        )

    return candles


def chain_candles(candles: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Encadena velas continuas ajustando apertura actual al cierre anterior sin alterar copias originales."""
    if not candles:
        return []

    chained: list[dict[str, Any]] = []
    for idx, raw in enumerate(candles):
        c = dict(raw)
        c["open"] = float(c["open"])
        c["high"] = float(c["high"])
        c["low"] = float(c["low"])
        c["close"] = float(c["close"])
        if idx > 0:
            prev_close = float(chained[idx - 1]["close"])
            c["open"] = round(prev_close, 4)
            c["high"] = round(max(c["high"], prev_close, c["close"]), 4)
            c["low"] = round(min(c["low"], prev_close, c["close"]), 4)
        chained.append(c)
    return chained


def compute_ema_series(
    candles: Sequence[dict[str, Any]],
    period: int,
    value_key: str = "close",
) -> list[dict[str, Any]]:
    """Calcula Media Móvil Exponencial sembrada con SMA en el índice `period - 1`."""
    if period <= 0 or len(candles) < period:
        return []

    ema = sum(float(candles[i][value_key]) for i in range(period)) / float(period)
    k = 2.0 / float(period + 1)
    series: list[dict[str, Any]] = [
        {"time": int(candles[period - 1]["time"]), "value": round(ema, 4)}
    ]

    for idx in range(period, len(candles)):
        price = float(candles[idx][value_key])
        ema = (price * k) + (ema * (1.0 - k))
        series.append({"time": int(candles[idx]["time"]), "value": round(ema, 4)})

    return series


def _wilder_rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    if avg_gain == 0.0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_rsi_series(
    candles: Sequence[dict[str, Any]],
    period: int = 14,
) -> list[dict[str, Any]]:
    """Calcula RSI de Wilder alineado 1-a-1 con el eje lógico de velas (primeros `period` en None)."""
    if not candles:
        return []

    safe_period = max(2, int(period))
    result: list[dict[str, Any]] = [
        {"time": int(c["time"]), "value": None} for c in candles[:safe_period]
    ]
    if len(candles) <= safe_period:
        return result

    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, safe_period + 1):
        delta = float(candles[idx]["close"]) - float(candles[idx - 1]["close"])
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / float(safe_period)
    avg_loss = sum(losses) / float(safe_period)
    result.append(
        {
            "time": int(candles[safe_period]["time"]),
            "value": round(_wilder_rsi_value(avg_gain, avg_loss), 2),
        }
    )

    for idx in range(safe_period + 1, len(candles)):
        delta = float(candles[idx]["close"]) - float(candles[idx - 1]["close"])
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (safe_period - 1)) + gain) / float(safe_period)
        avg_loss = ((avg_loss * (safe_period - 1)) + loss) / float(safe_period)
        result.append(
            {
                "time": int(candles[idx]["time"]),
                "value": round(_wilder_rsi_value(avg_gain, avg_loss), 2),
            }
        )

    return result


def _bucket_depth(
    buy_ads: Sequence[dict[str, Any]],
    sell_ads: Sequence[dict[str, Any]],
    top_n: int,
) -> dict[str, float]:
    b_slice = buy_ads[:top_n]
    s_slice = sell_ads[:top_n]
    buy_usdt = sum(max(0.0, float(ad.get("surplus_usdt") or 0.0)) for ad in b_slice)
    sell_usdt = sum(max(0.0, float(ad.get("surplus_usdt") or 0.0)) for ad in s_slice)
    total = buy_usdt + sell_usdt

    imbalance = (sell_usdt - buy_usdt) / total if total > 0 else 0.0
    top1_buy = max(0.0, float(b_slice[0].get("surplus_usdt") or 0.0)) if b_slice else 0.0
    top1_sell = max(0.0, float(s_slice[0].get("surplus_usdt") or 0.0)) if s_slice else 0.0
    top1_share = ((top1_buy + top1_sell) / total * 100.0) if total > 0 else 0.0

    return {
        "buy_usdt": round(buy_usdt, 2),
        "sell_usdt": round(sell_usdt, 2),
        "top1_share_pct": round(min(100.0, max(0.0, top1_share)), 2),
        "imbalance": round(max(-1.0, min(1.0, imbalance)), 4),
    }


def compute_depth_summary(
    buy_ads: Sequence[dict[str, Any]],
    sell_ads: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Resume profundidad Top 5 / Top 10 / Top 20 y desequilibrio neto (demanda - oferta) / total."""
    top5 = _bucket_depth(buy_ads, sell_ads, 5)
    top10 = _bucket_depth(buy_ads, sell_ads, 10)
    top20 = _bucket_depth(buy_ads, sell_ads, 20)
    return {
        "top5": top5,
        "top10": top10,
        "top20": top20,
        "imbalance": top20["imbalance"],
    }


def compute_vwap_for_ticket(
    ads: Sequence[dict[str, Any]],
    ticket_ves: float,
) -> dict[str, Any]:
    """Recorre el libro real para calcular tasa promedio ponderada (VWAP) y deslizamiento en Bs."""
    if not ads or ticket_ves <= 0:
        best = float(ads[0].get("price") or 0.0) if ads else 0.0
        return {
            "fillable": False,
            "vwap_price": 0.0,
            "best_price": round(best, 4),
            "slippage_pct": 0.0,
            "top_price_covers_ticket": False,
            "covered_ves": 0.0,
            "ads_needed": 0,
        }

    best_price = float(ads[0].get("price") or 0.0)
    remaining_ves = float(ticket_ves)
    total_ves_filled = 0.0
    total_usdt_filled = 0.0
    ads_needed = 0

    for ad in ads:
        price = float(ad.get("price") or 0.0)
        surplus_usdt = max(0.0, float(ad.get("surplus_usdt") or 0.0))
        if price <= 0 or surplus_usdt <= 0:
            continue

        cap_ves = surplus_usdt * price
        take_ves = min(remaining_ves, cap_ves)
        take_usdt = take_ves / price
        total_ves_filled += take_ves
        total_usdt_filled += take_usdt
        remaining_ves -= take_ves
        ads_needed += 1
        if remaining_ves <= 1e-6:
            break

    fillable = remaining_ves <= 1e-3 and total_usdt_filled > 0
    vwap_price = total_ves_filled / total_usdt_filled if total_usdt_filled > 0 else 0.0
    slippage_pct = (
        (abs(vwap_price - best_price) / best_price) * 100.0
        if (best_price > 0 and vwap_price > 0)
        else 0.0
    )
    return {
        "fillable": fillable,
        "vwap_price": round(vwap_price, 4),
        "best_price": round(best_price, 4),
        "slippage_pct": round(slippage_pct, 4),
        "top_price_covers_ticket": bool(ads_needed == 1 and fillable),
        "covered_ves": round(total_ves_filled, 2),
        "ads_needed": ads_needed,
    }


def _weighted_quantile(sorted_pairs: list[tuple[float, float]], q: float) -> float:
    total_w = sum(w for _, w in sorted_pairs)
    if total_w <= 0:
        return sorted_pairs[0][0]
    target = q * total_w
    acc = 0.0
    prev_val = sorted_pairs[0][0]
    for val, w in sorted_pairs:
        next_acc = acc + w
        if next_acc >= target:
            if w <= 0:
                return val
            frac = max(0.0, min(1.0, (target - acc) / w))
            return prev_val + frac * (val - prev_val)
        acc = next_acc
        prev_val = val
    return sorted_pairs[-1][0]


def compute_percentile_band(
    daily_closes: Sequence[float],
    anchor_price: float,
    coverage: float = 0.90,
    min_days: int = MIN_PREDICTION_DAYS,
) -> dict[str, float] | None:
    """Calcula banda probabilística empírica ponderada por recencia; Fail-Closed si hay pocos días."""
    valid = [float(v) for v in daily_closes if v is not None and math.isfinite(float(v)) and float(v) > 0]
    if len(valid) < min_days or anchor_price <= 0:
        return None

    returns = [(valid[i] - valid[i - 1]) / valid[i - 1] for i in range(1, len(valid))]
    if len(returns) < 2:
        return None

    decay = 0.94
    n_ret = len(returns)
    weighted = sorted(
        ((returns[i], decay ** (n_ret - 1 - i)) for i in range(n_ret)),
        key=lambda x: x[0],
    )

    safe_cov = max(0.10, min(0.99, float(coverage)))
    alpha = (1.0 - safe_cov) / 2.0
    r_low = _weighted_quantile(weighted, alpha)
    r_high = _weighted_quantile(weighted, 1.0 - alpha)

    return {
        "floor": round(float(anchor_price) * (1.0 + r_low), 2),
        "ceiling": round(float(anchor_price) * (1.0 + r_high), 2),
        "coverage": round(safe_cov, 4),
        "r_low_pct": round(r_low * 100.0, 2),
        "r_high_pct": round(r_high * 100.0, 2),
    }


def backtest_percentile_band(
    daily_closes: Sequence[float],
    coverage: float = 0.90,
    min_days: int = MIN_PREDICTION_DAYS,
) -> dict[str, Any] | None:
    """Ejecuta backtest walk-forward sin look-ahead bias sobre cierres diarios históricos."""
    valid = [float(v) for v in daily_closes if v is not None and math.isfinite(float(v)) and float(v) > 0]
    if len(valid) <= min_days:
        return None

    hits = 0
    evaluated = 0
    for idx in range(min_days, len(valid)):
        history = valid[:idx]
        anchor = valid[idx - 1]
        actual = valid[idx]
        band = compute_percentile_band(
            history,
            anchor_price=anchor,
            coverage=coverage,
            min_days=min_days,
        )
        if band is None:
            continue
        evaluated += 1
        if band["floor"] <= actual <= band["ceiling"]:
            hits += 1

    if evaluated == 0:
        return None

    return {
        "hits": hits,
        "evaluated": evaluated,
        "hit_rate_pct": round((hits / float(evaluated)) * 100.0, 2),
    }


def compute_liquidity_anomaly(
    snapshots: Sequence[MarketSnapshot],
    current_vol_usdt: float,
) -> dict[str, Any]:
    """Detecta liquidez anómalamente baja (<60% de la mediana reciente) con umbral Fail-Closed."""
    vols = [
        float(cast(float, s.vol_buy_usdt) or 0.0) + float(cast(float, s.vol_sell_usdt) or 0.0)
        for s in snapshots
        if (float(cast(float, s.vol_buy_usdt) or 0.0) + float(cast(float, s.vol_sell_usdt) or 0.0)) > 0
    ]
    if len(vols) < 6 or current_vol_usdt <= 0:
        return {
            "detected": False,
            "ratio_pct": None,
            "baseline_median_usdt": None,
            "status": "collecting",
        }

    base_med = float(median(vols))
    ratio_pct = (current_vol_usdt / base_med) * 100.0 if base_med > 0 else 100.0
    detected = ratio_pct < 60.0
    return {
        "detected": detected,
        "ratio_pct": round(ratio_pct, 1),
        "baseline_median_usdt": round(base_med, 2),
        "status": "thin_liquidity" if detected else "normal",
    }


def compute_brecha_velocity(snapshots: Sequence[MarketSnapshot]) -> float | None:
    """Calcula la velocidad de cambio de la brecha BCV en puntos porcentuales por hora."""
    if len(snapshots) < 2:
        return None
    recent = snapshots[-min(6, len(snapshots)):]
    first = recent[0]
    last = recent[-1]
    t0 = to_utc_epoch(cast(datetime, first.timestamp))
    t1 = to_utc_epoch(cast(datetime, last.timestamp))
    hours = (t1 - t0) / 3600.0
    if hours <= 1e-4:
        return 0.0
    delta = float(cast(float, last.brecha_pct) or 0.0) - float(cast(float, first.brecha_pct) or 0.0)
    return round(delta / hours, 4)


def _top_trimmed_avg(ads: Sequence[dict[str, Any]], top_n: int = 20) -> float:
    sample = ads[:top_n]
    prices = [float(ad["price"]) for ad in sample if float(ad.get("price") or 0.0) > 0]
    if not prices:
        return 0.0
    if len(prices) >= 5:
        cleaned = hampel_filter(prices, value_fn=lambda p: p, window=7, threshold=4.0)
        if cleaned:
            prices = cleaned
    return round(sum(prices) / float(len(prices)), 4)


@dataclass
class _BankAccumulator:
    buy_prices: list[float] = field(default_factory=list)
    sell_prices: list[float] = field(default_factory=list)
    buy_vol: float = 0.0
    sell_vol: float = 0.0


def aggregate_bank_snapshot(
    buy_ads: Sequence[dict[str, Any]],
    sell_ads: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Agrupa mejores puntas, promedios y liquidez USDT por banco a partir del libro vivo."""
    by_bank: dict[str, _BankAccumulator] = defaultdict(_BankAccumulator)
    for ad in buy_ads:
        price = float(ad.get("price") or 0.0)
        vol = max(0.0, float(ad.get("surplus_usdt") or 0.0))
        if price <= 0:
            continue
        for bank in ad.get("banks") or []:
            acc = by_bank[str(bank)]
            acc.buy_prices.append(price)
            acc.buy_vol += vol

    for ad in sell_ads:
        price = float(ad.get("price") or 0.0)
        vol = max(0.0, float(ad.get("surplus_usdt") or 0.0))
        if price <= 0:
            continue
        for bank in ad.get("banks") or []:
            acc = by_bank[str(bank)]
            acc.sell_prices.append(price)
            acc.sell_vol += vol

    summary: dict[str, dict[str, float]] = {}
    for bank_name, acc in by_bank.items():
        summary[bank_name] = {
            "buy_best": round(min(acc.buy_prices), 2) if acc.buy_prices else 0.0,
            "buy_avg": round(sum(acc.buy_prices) / len(acc.buy_prices), 2) if acc.buy_prices else 0.0,
            "sell_best": round(max(acc.sell_prices), 2) if acc.sell_prices else 0.0,
            "sell_avg": round(sum(acc.sell_prices) / len(acc.sell_prices), 2) if acc.sell_prices else 0.0,
            "vol_buy": round(acc.buy_vol, 2),
            "vol_sell": round(acc.sell_vol, 2),
            "buy_ads_count": float(len(acc.buy_prices)),
            "sell_ads_count": float(len(acc.sell_prices)),
        }
    return summary


def _update_cell(
    prev_cell: dict[str, Any] | None,
    price: float,
    vol: float,
) -> dict[str, Any]:
    if price <= 0:
        return prev_cell or {}
    if not prev_cell or "o" not in prev_cell:
        return {
            "o": round(price, 4),
            "p": round(price, 4),
            "pc": None,
            "prev_p": round(price, 4),
            "x": round(price, 4),
            "u": round(vol, 2),
            "d": round(price, 4),
        }

    prev_p = float(prev_cell.get("prev_p") or prev_cell.get("d") or price)
    sustained_candidate = min(prev_p, price)
    prev_pc = prev_cell.get("pc")
    new_pc = (
        max(float(prev_pc), sustained_candidate)
        if prev_pc is not None
        else sustained_candidate
    )
    return {
        "o": float(prev_cell["o"]),
        "p": round(max(float(prev_cell["p"]), price), 4),
        "pc": round(new_pc, 4),
        "prev_p": round(price, 4),
        "x": round(min(float(prev_cell["x"]), price), 4),
        "u": round(float(prev_cell.get("u") or 0.0) + vol, 2),
        "d": round(price, 4),
    }


class MarketCollectorService:
    """Captura instantáneas en vivo desde Binance P2P + BCV y consolida velas horarias en BD."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketDataRepository(db)

    def capture_snapshot(
        self,
        bank_filter: str = "*",
        now_utc: datetime | None = None,
        ticket_ves: float | None = None,
        collect_missing_banks: bool = False,
    ) -> MarketSnapshot:
        """Consulta el libro vivo + tasa BCV y registra snapshot + rollup horario."""
        ts_aware = (now_utc or datetime.now(UTC)).astimezone(UTC)
        ts_naive = ts_aware.replace(tzinfo=None)
        mapped_bank = "Todos" if not bank_filter or bank_filter.strip() in ("*", "Todos") else bank_filter.strip()

        monitor = SpreadMonitor()
        book = monitor.fetch_filtered_orderbook(
            amount_usdt=100.0,
            amount_ves=ticket_ves if (ticket_ves and ticket_ves > 0) else None,
            bank=mapped_bank,
            rows=20,
        )
        buy_ads = list(book.get("buy_ads") or [])
        sell_ads = list(book.get("sell_ads") or [])
        if not buy_ads and not sell_ads:
            raise RuntimeError("Sin liquidez P2P disponible para capturar snapshot")

        bcv_data = BCVHistoryService(self.db).get_or_fetch_current_rates()
        bcv_rate = float((bcv_data or {}).get("usd") or 0.0)

        p2p_buy_best = float(book.get("best_buy_price") or (buy_ads[0]["price"] if buy_ads else 0.0))
        p2p_sell_best = float(book.get("best_sell_price") or (sell_ads[0]["price"] if sell_ads else 0.0))
        p2p_buy_avg20 = _top_trimmed_avg(buy_ads, 20) or p2p_buy_best
        p2p_sell_avg20 = _top_trimmed_avg(sell_ads, 20) or p2p_sell_best

        if p2p_buy_avg20 > 0 and p2p_sell_avg20 > 0:
            p2p_mid = round((p2p_buy_avg20 + p2p_sell_avg20) / 2.0, 4)
        else:
            p2p_mid = p2p_sell_avg20 or p2p_buy_avg20

        brecha_pct = (
            round(((p2p_mid - bcv_rate) / bcv_rate) * 100.0, 4)
            if (bcv_rate > 0 and p2p_mid > 0)
            else 0.0
        )
        spread_ves = round(p2p_sell_avg20 - p2p_buy_avg20, 4)

        depth_summary = compute_depth_summary(buy_ads, sell_ads)
        vol_buy_usdt = float(depth_summary["top20"]["buy_usdt"])
        vol_sell_usdt = float(depth_summary["top20"]["sell_usdt"])
        bank_prices = aggregate_bank_snapshot(buy_ads, sell_ads)

        # Normalizar y completar lecturas reales de bancos clave si faltaron en Top 20 global
        if collect_missing_banks and mapped_bank == "Todos":
            present_canon = {SpreadMonitor.canonical_user_bank_name(k) for k in bank_prices}
            for core_bank in _CORE_VEN_BANKS:
                if core_bank in present_canon:
                    continue
                try:
                    b_book = monitor.fetch_filtered_orderbook(
                        amount_usdt=100.0,
                        amount_ves=1_000_000.0,
                        bank=core_bank,
                        rows=10,
                    )
                    b_buy = [
                        ad for ad in (b_book.get("buy_ads") or [])
                        if any(SpreadMonitor.bank_matches_user_bank(str(x), core_bank) for x in (ad.get("banks") or []))
                    ]
                    b_sell = [
                        ad for ad in (b_book.get("sell_ads") or [])
                        if any(SpreadMonitor.bank_matches_user_bank(str(x), core_bank) for x in (ad.get("banks") or []))
                    ]
                    if b_buy or b_sell:
                        b_stats = aggregate_bank_snapshot(b_buy, b_sell)
                        for b_k, b_v in b_stats.items():
                            if SpreadMonitor.bank_matches_user_bank(b_k, core_bank) and b_k not in bank_prices:
                                bank_prices[b_k] = b_v
                except (RuntimeError, ValueError, OSError, TimeoutError):
                    continue

        # Recolectar los 3 tramos reales de ticket (250K, 1M, 5M Bs) cuando es captura global
        ticket_buckets_data: dict[str, dict[str, Any]] = {}
        if mapped_bank == "Todos" and ticket_ves is None:
            for bucket_ves in TRACKED_TICKET_BUCKETS_VES:
                try:
                    t_book = monitor.fetch_filtered_orderbook(
                        amount_usdt=100.0,
                        amount_ves=float(bucket_ves),
                        bank="Todos",
                        rows=20,
                    )
                    t_buy = list(t_book.get("buy_ads") or [])
                    t_sell = list(t_book.get("sell_ads") or [])
                    if not t_buy and not t_sell:
                        continue
                    t_buy_best = float(t_book.get("best_buy_price") or (t_buy[0]["price"] if t_buy else 0.0))
                    t_sell_best = float(t_book.get("best_sell_price") or (t_sell[0]["price"] if t_sell else 0.0))
                    t_buy_avg = _top_trimmed_avg(t_buy, 20) or t_buy_best
                    t_sell_avg = _top_trimmed_avg(t_sell, 20) or t_sell_best
                    t_depth = compute_depth_summary(t_buy, t_sell)
                    ticket_buckets_data[str(bucket_ves)] = {
                        "buy_best": round(t_buy_best, 4),
                        "buy_avg20": round(t_buy_avg, 4),
                        "sell_best": round(t_sell_best, 4),
                        "sell_avg20": round(t_sell_avg, 4),
                        "vol_buy": round(float(t_depth["top20"]["buy_usdt"]), 2),
                        "vol_sell": round(float(t_depth["top20"]["sell_usdt"]), 2),
                        "banks": aggregate_bank_snapshot(t_buy, t_sell),
                    }
                except (RuntimeError, ValueError, OSError, TimeoutError):
                    continue

        depth_payload: dict[str, Any] = {"depth": depth_summary, "banks": bank_prices}
        if ticket_buckets_data:
            depth_payload["tickets"] = ticket_buckets_data

        snapshot = MarketSnapshot(
            timestamp=ts_naive,
            bcv_rate=round(bcv_rate, 4),
            p2p_buy_best=round(p2p_buy_best, 4),
            p2p_buy_avg20=round(p2p_buy_avg20, 4),
            p2p_sell_best=round(p2p_sell_best, 4),
            p2p_sell_avg20=round(p2p_sell_avg20, 4),
            p2p_mid=round(p2p_mid, 4),
            brecha_pct=brecha_pct,
            spread_ves=spread_ves,
            vol_buy_usdt=round(vol_buy_usdt, 2),
            vol_sell_usdt=round(vol_sell_usdt, 2),
            depth_json=json.dumps(depth_payload),
        )
        saved_snap = self.repo.add_snapshot(snapshot)
        self._update_hourly_rollup(
            hora_utc=ts_naive.replace(minute=0, second=0, microsecond=0),
            p2p_buy_avg20=p2p_buy_avg20,
            p2p_sell_avg20=p2p_sell_avg20,
            bcv_rate=bcv_rate,
            brecha_pct=brecha_pct,
            vol_buy_usdt=vol_buy_usdt,
            vol_sell_usdt=vol_sell_usdt,
            bank_prices=bank_prices,
            ticket_buckets=ticket_buckets_data,
        )
        return saved_snap

    def _update_hourly_rollup(
        self,
        *,
        hora_utc: datetime,
        p2p_buy_avg20: float,
        p2p_sell_avg20: float,
        bcv_rate: float,
        brecha_pct: float,
        vol_buy_usdt: float,
        vol_sell_usdt: float,
        bank_prices: dict[str, dict[str, float]],
        ticket_buckets: dict[str, dict[str, Any]] | None = None,
    ) -> MarketHourlyRollup:
        existing = self.repo.get_rollup_by_hour(hora_utc)
        matrix: dict[str, Any] = {}
        if existing and existing.bank_matrix_json:
            try:
                loaded = json.loads(str(existing.bank_matrix_json))
                if isinstance(loaded, dict):
                    matrix = loaded
            except ValueError:
                matrix = {}

        # Actualizar clave global "*" y bancos observados con seguimiento de máximo sostenido (pc)
        global_raw = matrix.get("*")
        global_prev: dict[str, Any] = global_raw if isinstance(global_raw, dict) else {}
        matrix["*"] = {
            "sell": _update_cell(global_prev.get("sell"), p2p_sell_avg20, vol_sell_usdt),
            "buy": _update_cell(global_prev.get("buy"), p2p_buy_avg20, vol_buy_usdt),
        }
        for bank_name, stats in bank_prices.items():
            prev_raw = matrix.get(bank_name)
            prev_b: dict[str, Any] = prev_raw if isinstance(prev_raw, dict) else {}
            matrix[bank_name] = {
                "sell": _update_cell(
                    prev_b.get("sell"),
                    stats.get("sell_best") or stats.get("sell_avg") or 0.0,
                    stats.get("vol_sell") or 0.0,
                ),
                "buy": _update_cell(
                    prev_b.get("buy"),
                    stats.get("buy_best") or stats.get("buy_avg") or 0.0,
                    stats.get("vol_buy") or 0.0,
                ),
            }

        if ticket_buckets:
            tickets_raw = matrix.get("tickets")
            tickets_map: dict[str, Any] = dict(tickets_raw) if isinstance(tickets_raw, dict) else {}
            for t_key, t_val in ticket_buckets.items():
                prev_t_raw = tickets_map.get(t_key)
                prev_t: dict[str, Any] = prev_t_raw if isinstance(prev_t_raw, dict) else {}
                tickets_map[t_key] = {
                    "sell": _update_cell(
                        prev_t.get("sell"),
                        float(t_val.get("sell_avg20") or t_val.get("sell_best") or 0.0),
                        float(t_val.get("vol_sell") or 0.0),
                    ),
                    "buy": _update_cell(
                        prev_t.get("buy"),
                        float(t_val.get("buy_avg20") or t_val.get("buy_best") or 0.0),
                        float(t_val.get("vol_buy") or 0.0),
                    ),
                }
            matrix["tickets"] = tickets_map

        prev_vol_buy = float(cast(float, existing.vol_buy_sum)) if existing is not None else 0.0
        prev_vol_sell = float(cast(float, existing.vol_sell_sum)) if existing is not None else 0.0
        rollup = MarketHourlyRollup(
            hora_utc=hora_utc,
            buy_open=p2p_buy_avg20,
            buy_high=p2p_buy_avg20,
            buy_low=p2p_buy_avg20,
            buy_close=p2p_buy_avg20,
            sell_open=p2p_sell_avg20,
            sell_high=p2p_sell_avg20,
            sell_low=p2p_sell_avg20,
            sell_close=p2p_sell_avg20,
            bcv_close=bcv_rate,
            brecha_close=brecha_pct,
            vol_buy_sum=round(prev_vol_buy + vol_buy_usdt, 2),
            vol_sell_sum=round(prev_vol_sell + vol_sell_usdt, 2),
            samples_count=1,
            bank_matrix_json=json.dumps(matrix),
        )

        return self.repo.upsert_hourly_rollup(rollup)


def count_history_maturity(db: Session) -> dict[str, int]:
    """Cuenta muestras totales y días calendario cubiertos entre snapshots y rollups horarios."""
    repo = MarketDataRepository(db)
    snaps = repo.list_snapshots(limit=5000)
    rollups = repo.list_hourly_rollups(limit=5000)
    days: set[str] = set()
    for s in snaps:
        dt = cast(datetime, s.timestamp)
        days.add(dt.strftime("%Y-%m-%d"))
    for r in rollups:
        dt = cast(datetime, r.hora_utc)
        days.add(dt.strftime("%Y-%m-%d"))
    samples_total = max(len(snaps), sum(int(cast(int, r.samples_count) or 0) for r in rollups))
    return {
        "samples_total": samples_total,
        "days_count": len(days),
        "rollups_count": len(rollups),
    }


def extract_daily_closes(
    rollups: Sequence[MarketHourlyRollup],
    snapshots: Sequence[MarketSnapshot],
    side: str = "sell",
) -> list[float]:
    """Extrae serie ordenada de cierres diarios (VES o %) para banda probabilística y backtest."""
    by_day: dict[str, float] = {}
    for r in rollups:
        dt = cast(datetime, r.hora_utc)
        day_key = dt.strftime("%Y-%m-%d")
        if side == "buy":
            val = float(cast(float, r.buy_close) or 0.0)
        elif side == "brecha":
            val = float(cast(float, r.brecha_close) or 0.0)
        else:
            val = float(cast(float, r.sell_close) or 0.0)
        if val > 0:
            by_day[day_key] = val

    for s in snapshots:
        dt = cast(datetime, s.timestamp)
        day_key = dt.strftime("%Y-%m-%d")
        if side == "buy":
            val = float(cast(float, s.p2p_buy_avg20) or 0.0)
        elif side == "brecha":
            val = float(cast(float, s.brecha_pct) or 0.0)
        else:
            val = float(cast(float, s.p2p_sell_avg20) or 0.0)
        if val > 0:
            by_day[day_key] = val

    return [by_day[k] for k in sorted(by_day.keys())]


def clear_stale_hourly_cutoff(now_utc: datetime | None = None, days_keep: int = 90) -> datetime:
    """Calcula corte temporal naive UTC para consultas recientes."""
    ref = (now_utc or datetime.now(UTC)).astimezone(UTC)
    return (ref - timedelta(days=days_keep)).replace(tzinfo=None)
