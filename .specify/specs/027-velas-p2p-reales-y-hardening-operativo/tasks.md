# Tareas Atómicas: SPEC-027 Velas P2P Verídicas y Hardening Operativo

- [x] **T27.0** Formalizar `SPEC-027` (`spec.md`, `plan.md`, `tasks.md`).
- [x] **T27.1** Escribir pruebas TDD en rojo (`tests/unit/test_spec027_velas_and_hardening.py`) verificando filtros reales, 3 tramos de ticket, Fail-Closed sin datos falsos, auth en `/api/market/collect`, retención NVMe y aislamiento de alertas/sesión.
- [x] **T27.2** Corregir alias bancarios, referencia sin hardcoded `1005.0` y fallbacks calibrados en `src/core/spread_monitor.py`, `src/core/rate_alert_service.py` y `src/integrations/telegram_notifier.py`.
- [x] **T27.3** Implementar recolección de 3 tickets reales (`250K`, `1M`, `5M`), respaldo multi-banco limpio y `prune_old_snapshots(days_keep=30)` en `src/core/market_analytics.py` y `src/data/repositories.py`.
- [x] **T27.4** Actualizar `src/api/routes/market.py` y `src/api/main.py` (cero fallback global al filtrar banco/ticket, lectura real de los 3 tramos, auth en `/api/market/collect`, purga programada).
- [x] **T27.5** Limpiar Velas P2P (`market/page.tsx`, `trading-candles-chart.tsx`), reducir tráfico `45s` (`telemetry-context.tsx`) y reforzar limpieza de sesión multi-usuario (`api.ts`).
- [x] **T27.6** Configurar rotación de logs en `docker/docker-compose.yml`, `docker image prune -f` en `scripts/deploy_vps.sh` y alinear `memory.md` / `SPEC-025` / `SPEC-023`.
- [x] **T27.7** Ejecutar verificación integral (`pytest`, `ruff`, `mypy`, `npm run build`, pruebas live DevTools y `security-review`) y cerrar `memory.md`.
