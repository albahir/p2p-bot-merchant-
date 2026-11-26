# PLAN-027: Arquitectura Técnica — Velas P2P Verídicas y Hardening Operativo

## Fase 1 — Backend Velas P2P, 3 Tickets Reales y Cero Fallbacks Falsos
- `src/core/spread_monitor.py`: Completar `resolve_binance_pay_types` y añadir normalización canónica consistente para bancos venezolanos; eliminar `ref_rate = 1005.0` hardcoded usando tasa BCV/snapshot o BAPI directa sin suposiciones estáticas.
- `src/core/market_analytics.py` + `src/data/repositories.py`:
  - Definir `TRACKED_TICKET_BUCKETS_VES = (250_000, 1_000_000, 5_000_000)`.
  - Almacenar en `depth_json["tickets"]` y `bank_matrix_json["tickets"]` las lecturas reales de los 3 tramos sin contaminar `p2p_buy_avg20`/`p2p_sell_avg20` globales.
  - Implementar `MarketDataRepository.prune_old_snapshots(days_keep=30)` usando `clear_stale_hourly_cutoff` sin tocar `market_hourly_rollups`.
- `src/api/routes/market.py`:
  - Eliminar fallback silencioso global en `_snapshot_price_for_side` y `_rollup_ohlc_for_side` cuando se filtra por banco o tramo específico.
  - Soportar filtrado real de velas por `ticket_ves` mapeado a los 3 buckets (`250000`, `1000000`, `5000000`), con aviso transparente para montos personalizados.
  - Exigir `require_authenticated` en `POST /api/market/collect` y capturar snapshot global limpio sin contaminación de filtros.
  - En `GET /api/market/analytics`, garantizar comportamiento Fail-Closed honesto si Binance está caído bajo un filtro bancario/ticket.
- `src/core/rate_alert_service.py` y `src/integrations/telegram_notifier.py`: Bloquear datos calibrados `get_market_quotes()` cuando `use_sandbox=False`.

## Fase 2 — Frontend Velas P2P Simplificado y Aislamiento Multi-Usuario
- `frontend/src/app/market/page.tsx` + `trading-candles-chart.tsx`:
  - Retirar KPI `0/20 días` y bandas P05/P95 por defecto; mostrar en su lugar resumen práctico **Liquidez y Mejor Banco**.
  - Ocultar `EMA 9/21` y `RSI 14` detrás de toggle *Vista técnica* apagado por defecto.
  - Destacar los 3 tickets históricos reales (`Bs 250K`, `Bs 1M`, `Bs 5M`) y mantener presets `Bs 500K` / `Bs 3M` / personalizado aclarando su aplicación en VWAP en vivo.
- `frontend/src/lib/telemetry-context.tsx` + `frontend/src/lib/api.ts`:
  - Eliminar llamada repetitiva de `warmAuthenticatedSession()` dentro del `setInterval` de 45s.
  - Garantizar limpieza integral de cachés y claves de usuario en `logout`, `401`, `login` y `register`.

## Fase 3 — Infraestructura 100 GB NVMe, Documentación y Verificación Final
- `docker/docker-compose.yml` y `scripts/deploy_vps.sh`: rotación `json-file` (`max-size: "10m"`, `max-file: "3"`) y `docker image prune -f`.
- `memory.md` y `src/api/main.py`: conectar purga de snapshots > 30 días en ciclo de mantenimiento, alinear `SPEC-023` como pendiente (`0/26`) y corregir `memory.md`.
- Verificación completa: `pytest`, `ruff`, `mypy`, `npm run build`, `security-review` y pruebas en vivo con Chrome DevTools / Playwright.
