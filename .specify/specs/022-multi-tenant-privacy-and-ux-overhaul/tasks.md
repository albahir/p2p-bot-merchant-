# Tasks: SPEC-022 Aislamiento Confidencial Multi-Usuario (Cero Visibilidad Cruzada Admin/Trader), Alerta de Riesgo Cambiario y Mejoras Tácticas UX/UI

## Fase 1: Suite TDD en Rojo (Aislamiento Multi-Usuario, Estado Operativo Admin, Entrada Manual <5s y Riesgo Cambiario)
- [x] T22.1: Crear `tests/unit/test_multi_tenant_isolation_and_ux.py` verificando en rojo:
  1. Aislamiento estricto de datos confidenciales (`orders`, `bank_vouchers`, `journal_entries`, `fiscal_period_snapshots`, `binance_api_key`): el `ADMIN` NO puede ver órdenes, saldos, comprobantes ni contabilidad de un `TRADER`, ni viceversa.
  2. Capacidad de cada usuario (`TRADER` y `ADMIN`) de conectar y verificar su propia API de Binance de forma aislada.
  3. Visibilidad exclusiva del `ADMIN` en `GET /api/users` y `/usuarios` (Telegram) sobre el **estado operativo** de cada usuario en todos los aspectos (`telegram_linked`, `binance_api_configured`, `binance_key_type`, `google_sheet_configured`) sin exponer saldos ni órdenes.
  4. Endpoint de conciliación manual ultrarrápida `POST /api/accounting/vouchers/manual` (fallback sin OCR en <5s con asiento contable automático).
  5. Detector de riesgo cambiario y spread intrabanco negativo en `RateAlertService.check_negative_spread_risk`.

## Fase 2: Implementación Backend (Modelos, Repositorios, Rutas y Bot de Telegram)
- [x] T22.2: Agregar `user_id` a `Order`, `WalletMovement`, `BankVoucher`, `JournalEntry` y `FiscalPeriodSnapshot` en `src/data/models.py` y migración automática en `init_db()` (`src/data/database.py`), aislando las consultas por `user_id` en `src/data/repositories.py`, `AccountingEngine`, `FiscalReconciler`, `BinanceHistorySyncer` y `BankReceiptOCR`.
- [x] T22.3: Aislar credenciales de Binance por usuario (`user_{id}:binance_api_key`) en `src/api/routes/settings.py` y `src/api/routes/orders.py` permitiendo que tanto `TRADER` como `ADMIN` conecten y evalúen su propia API de Binance sin cruzar datos.
- [x] T22.4: Enriquecer `UserPublicResponse` y `GET /api/users` (`src/api/routes/users.py`) + comando `/usuarios` (`src/integrations/telegram_notifier.py`) con indicadores de estado por usuario en Telegram, API Binance y Google Sheets, y aislar `/ordenes`, `/conciliacion`, `/cierre` y OCR por `user_id`.
- [x] T22.5: Implementar `POST /api/accounting/vouchers/manual` en `src/api/routes/accounting.py` para registro y conciliación manual ultrarrápida cuando falle el OCR, y `check_negative_spread_risk` en `src/core/rate_alert_service.py`.

## Fase 3: Implementación Frontend UX/UI ("P2P Merchant OS")
- [x] T22.6: Actualizar `frontend/src/components/app-shell.tsx` con:
  - Franja y borde superior global de emergencia en rojo/ámbar cuando **Parada Fail-Closed** (`botStatus.is_paused`) esté activa en cualquier pestaña.
  - Barra Táctica Móvil Inferior (`md:hidden`) para acceso rápido en teléfonos a Matriz, Calculadora, Contabilidad/Pago y Órdenes.
- [x] T22.7: Actualizar `frontend/src/app/page.tsx` y `frontend/src/app/calculator/page.tsx` con:
  - Pinning (`📌`) de bancos principales en la parte superior de la Matriz (persistido en `localStorage`).
  - Deep Linking de 1 clic mejorado (`Simular` pre-selecciona banco origen, banco destino óptimo y tasas en tiempo real).
  - Alerta visual de Spread Intrabanco Negativo / Riesgo Cambiario, jerarquía de color CTA vs botones secundarios Outlined y mayor contraste en textos secundarios.
- [x] T22.8: Actualizar `frontend/src/app/accounting/page.tsx` y `frontend/src/app/settings/page.tsx` con:
  - Modal de **Asiento Manual Ultrarrápido (`Alt+N`)** (<5s con teclado) junto a Cargar Recibo OCR.
  - Panel de conexión de API Binance propio para cada operador (`TRADER` y `ADMIN`) y **Matriz de Estado de Usuarios (Telegram / API Binance / Google Sheets)** para el `ADMIN` con aviso explícito de privacidad confidencial.

## Fase 4: Verificación Integral, Auditoría de Seguridad y Documentación
- [x] T22.9: Ejecutar suite completa de tests (`pytest`), `ruff check .`, `mypy src/ tests/ scripts/`, compilación `tsc --noEmit`, escaneo `security-review` y actualizar `tasks.md` y `MEMORY.md`.

## Fase 5: Sistema Dual de Spread (Por Banco + Por Precio en Vivo con Filtros Binance P2P) y Blindaje DevTools/API
- [x] T22.10: Implementar `SpreadMonitor.resolve_binance_pay_types` (lista blanca estricta de métodos de pago) y `SpreadMonitor.fetch_filtered_orderbook` en `src/core/spread_monitor.py` + endpoint `GET /api/spreads/orderbook` en `src/api/routes/spreads.py` con soporte para filtros reales de Binance P2P (`amount_usdt`, `trans_amount_ves`, `bank`, `merchant_only`) y cálculo de Spread Maker vs Spread Taker con caché TTL de 12 segundos.
- [x] T22.11: Enriquecer `SpreadMonitor.fetch_live_quotes` y `GET /api/spreads/matrix` para filtrar puntas por volumen (`transAmount` en Bs.) y estado de comerciante verificado.
- [x] T22.12: Actualizar `frontend/src/app/page.tsx` y `frontend/src/lib/api.ts` con el Selector de Modo de Análisis (`Vista Dual (Banco + Precio)`, `Spread por Banco`, `Spread por Precio (Libro Binance)`), toggle `Solo Comerciantes Verificados`, visualización del libro de anuncios de Compra y Venta con límites `Mín Bs. – Máx Bs.` y omisión de la cabecera `Authorization: Bearer` en endpoints públicos de mercado (`/api/spreads/*`).
- [x] T22.13: Endurecer `frontend/next.config.mjs` (`productionBrowserSourceMaps: false`, `poweredByHeader: false`, cabeceras de seguridad), `src/api/main.py` (ocultar `/docs`, `/redoc`, `/openapi.json` en producción + `Cache-Control: no-store`), `src/api/routes/settings.py` y `src/api/routes/websockets.py`.

