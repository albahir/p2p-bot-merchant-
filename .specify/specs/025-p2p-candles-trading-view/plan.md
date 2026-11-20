# PLAN-025: Diseño Técnico de Velas P2P y Predictor Estadístico (`/market`)

## 1. Modelo de Datos y Repositorio (`src/data/models.py`, `src/data/repositories.py`)
- `MarketSnapshot` (`market_snapshots`):
  - `id`, `timestamp` (UTC indexado), `bcv_rate`, `p2p_buy_best`, `p2p_buy_avg20`, `p2p_sell_best`, `p2p_sell_avg20`, `p2p_mid`, `brecha_pct`, `spread_ves`, `vol_buy_usdt`, `vol_sell_usdt`, `depth_json` (Top 5/10/20 + bancos × tickets).
- `MarketHourlyRollup` (`market_hourly_rollups`):
  - `hora_utc` (PK/unique indexada truncada a hora), `buy_open`, `buy_high`, `buy_low`, `buy_close`, `sell_open`, `sell_high`, `sell_low`, `sell_close`, `bcv_close`, `brecha_close`, `vol_buy_sum`, `vol_sell_sum`, `samples_count`, `bank_matrix_json` (por banco/ticket: `o, p, pc, x, u, d`).

## 2. Motor Cuantitativo & Recolector (`src/core/market_analytics.py`)
- `hampel_filter(values, window=10, threshold=4.0)`
- `aggregate_candles(points, bucket_seconds)` -> `{time, open, high, low, close, volume}` + `chain_candles`.
- `compute_ema_series(candles, period)` & `compute_rsi_series(candles, period=14)` (Wilder smoothing, alineada 1-a-1).
- `compute_vwap_for_ticket(ads, ticket_ves)` & `compute_depth_buckets(buy_ads, sell_ads)`.
- `compute_percentile_band(daily_closes, target_coverage=0.90)` + `backtest_percentile_band`.
- `MarketCollectorService`:
  - `capture_snapshot(db, bank_filter="*", merchant_only=False)`: usa `SpreadMonitor` + `BCVHistoryService` para capturar lectura en vivo y actualizar `MarketSnapshot` + `MarketHourlyRollup` (incluyendo detección `pc` máximo sostenido cuando la nueva lectura confirma la anterior!).

## 3. API REST (`/api/market/...` en `src/api/routes/market.py`)
- `GET /api/market/candles`: `side` (`sell`|`buy`|`bank`|`brecha`|`evolucion`), `timeframe` (`1m`|`5m`|`15m`|`1h`|`4h`|`1D`), `bank` (`*`|`Banesco`|`BDV`...), `ticket_ves`, `limit` (`<= 500`).
- `GET /api/market/analytics`: Devuelve KPIs vivos, **EMA4/12 + EMA5/20 + RSI14 + Velocidad de Brecha**, **Profundidad Top 5/10/20 + VWAP por ticket**, **Anomalías de liquidez (<60% mediana)**, **Banda 90% con backtest** (si hay historial suficiente) y **Comparativa horaria BCV vs P2P**.
- `POST /api/market/collect`: Dispara recolección manual inmediata (cooldown mínimo 15s anti-spam).
- Collector ligero en background en `src/api/main.py` (`lifespan`) cada 120s (desactivable vía env o en `skip_lifespan=True` de tests).

## 4. Frontend Next.js (`/market`)
- Instalar `lightweight-charts@^4.2.1` en `frontend/`.
- Botón dedicado **"Velas P2P"** (`href="/market"`, icono `candlestick_chart`) en `frontend/src/components/app-shell.tsx`.
- Cliente tipado en `frontend/src/lib/api.ts` (`getMarketCandles`, `getMarketAnalytics`, `triggerMarketCollect`).
- Componente `frontend/src/components/trading-candles-chart.tsx` (`lightweight-charts` v4: Candlesticks/Line/Area, EMA9, EMA21, Volumen/Profundidad relativa, Precio Banda 90%, RSI 14 sincronizado por logical range, modo Evolución P2P vs BCV con eje compartido).
- Página `frontend/src/app/market/page.tsx` con selector de los 5 modos, temporalidades, banco & ticket VWAP, panel de profundidad Top 5/10/20 y veredicto estadístico transparente.
