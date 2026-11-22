# Tasks: SPEC-025 Terminal de Velas P2P y Predictor Estadístico (`/market`)

## Fase 1: Especificación, Dependencia Gráfica y Modelos de BD
- [x] T25.1: Crear SDD `025-p2p-candles-trading-view` (`spec.md`, `plan.md`, `tasks.md`).
- [x] T25.2: Instalar `lightweight-charts@^4.2.1` en `frontend/` y agregar modelos `MarketSnapshot` / `MarketHourlyRollup` + repositorios en `src/data/models.py` y `src/data/repositories.py`.

## Fase 2: Motor Cuantitativo, Filtro Hampel y Recolector OHLC (TDD Red -> Green)
- [x] T25.3: Escribir suite de pruebas unitarias e integración en rojo (`tests/unit/test_market_analytics.py`) validando filtro de Hampel MAD, agrupación OHLC + encadenado de velas, EMA/RSI Wilder alineado, cálculo VWAP por ticket + profundidad Top 5/10/20, banda por percentiles 90% + backtest, recolector `MarketCollectorService` (incluyendo rollup horario y máximo sostenido) y rutas `/api/market/*`.
- [x] T25.4: Implementar `src/core/market_analytics.py` pasando todos los tests de matemática pura y recolección en verde.

## Fase 3: API REST y Recolector Background no intrusivo
- [x] T25.5: Crear `src/api/routes/market.py` (`/api/market/candles`, `/api/market/analytics`, `/api/market/collect`) con validación estricta, montarlo en `src/api/main.py` con recolector background opcional (inactivo en `skip_lifespan=True`).

## Fase 4: Interfaz Next.js Dedicada (`/market`) + Botón Aparte en Sidebar
- [x] T25.6: Agregar tipos y clientes en `frontend/src/lib/api.ts` y añadir botón independiente `Velas P2P` (`/market`) en `frontend/src/components/app-shell.tsx`.
- [x] T25.7: Crear `frontend/src/components/trading-candles-chart.tsx` (TradingView `lightweight-charts` v4 con Velas/Línea/Área, EMA9/21, Volumen/Profundidad, Banda 90%, RSI 14 sincronizado y Evolución BCV vs P2P) y la página `frontend/src/app/market/page.tsx`.

## Fase 5: Verificación, Auditoría y Documentación
- [x] T25.8: Ejecutar `pytest`, `ruff check .`, `mypy src/ scripts/`, `tsc --noEmit`, auditoría `security-review` y actualizar `memory.md` (ADR 065).
