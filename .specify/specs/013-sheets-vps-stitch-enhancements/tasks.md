# Tareas Atómicas: SPEC-013 (Sheets, VPS, Stitch, Spread)

## 📌 Lista de Tareas

### Fase 1: Diagnóstico y Resiliencia de Google Sheets
- [x] **T01**: Agregar campos `last_error` y `client_email` a `SheetsExporter` en `src/reporting/sheets_exporter.py`.
- [x] **T02**: Capturar y tipificar errores específicos de Google API (HTTP 403 Permiso Denegado, HTTP 404 Hoja No Encontrada, Credenciales Faltantes) en `SheetsExporter`.
- [x] **T03**: Actualizar `_handle_sheets_sync()` en `src/integrations/telegram_notifier.py` para reportar el diagnóstico detallado e incluir el email al que se debe compartir la hoja.
- [x] **T04**: Actualizar el panel de Google Sheets en `src/reporting/dashboard/app.py` para mostrar el mensaje de error descriptivo en la interfaz.
- [x] **T05**: Escribir pruebas unitarias en `tests/unit/test_sheets_exporter.py` verificando la captura y reporte de los distintos tipos de error.
- [x] **T06**: Ejecutar suite completa de tests (`pytest`), `ruff check .` y `mypy src/` verificando 100% verde.

### Fase 2: Infraestructura VPS y Whitelist de IP para Binance
- [ ] **T07**: Crear script de aprovisionamiento en servidor VPS `scripts/deploy_vps.sh` para arranque 24/7 con Docker Compose.
- [ ] **T08**: Implementar función de detección de IP pública saliente en `src/security/permissions.py` para notificar en Telegram la IP exacta que debe agregarse a la whitelist de Binance.
- [ ] **T09**: Escribir pruebas unitarias para la detección de IP pública.

### Fase 3: Integración de Google Stitch (MCP) y Modernización de UI (Terminal P2P)
- [x] **T10**: Registrar la configuración del servidor MCP de Google Stitch en `C:\Users\jonan\.gemini\config\mcp_config.json`.
- [x] **T11**: Documentar la guía de arquitectura, obtención de API Key de Stitch y sincronización de pantallas en `docs/stitch_mcp_setup.md`.
- [x] **T12a**: Implementar el motor de temas y tokens de diseño Stitch en `src/reporting/dashboard/theme.py` (paleta Obsidian Fintech, Glassmorphism, badges semánticos, variables CSS sanitizadas).
- [x] **T12b**: Implementar el componente modular `terminal_header.py` en `src/reporting/dashboard/components/` (estado Fail-closed, Binance API weight, IP y hora local/UTC).
- [x] **T12c**: Implementar el componente modular `kpi_cards.py` en `src/reporting/dashboard/components/` (volumen, margen neto en VES/USD, spread BCV y ratio de conciliación).
- [x] **T12d**: Implementar el componente modular `receipt_center.py` en `src/reporting/dashboard/components/` (tabla de comprobantes bancarios, filtros y uploader interactivo en memoria con OCR reactivo).
- [x] **T12e**: Implementar el componente modular `ai_telemetry.py` en `src/reporting/dashboard/components/` (monitor en vivo del pool de claves de Gemini Vision).
- [x] **T12f**: Refactorizar e integrar el tema y componentes Stitch en `src/reporting/dashboard/app.py` y `fiscal_reconstruction_view.py`, aplicando estándares modernos de Streamlit 2026 (`width="stretch"`, `st.container(border=True)`, Material Symbols).
- [x] **T12g**: Escribir pruebas unitarias en `tests/unit/test_dashboard_theme.py` y `tests/unit/test_dashboard_components.py` validando la suite completa.



### Fase 4: Monitores Proactivos, Matriz de Arbitraje Bancario y Rentabilidad Real P2P
- [x] **T13a**: Diseñar e implementar `SpreadMonitor` en `src/core/spread_monitor.py` (comparativa P2P vs BCV, comisiones bancarias del 0.3% en Pago Móvil, regla de spread mínimo 0.80% y matriz de arbitraje interbancario).
- [x] **T13b**: Implementar el componente visual `arbitrage_matrix.py` en `src/reporting/dashboard/components/` (matriz de spreads por banco, calculadora maker de rentabilidad neta y alertas de margen crítico).
- [x] **T13c**: Integrar la pestaña `:material/candlestick_chart: Monitor & Arbitraje P2P` en `src/reporting/dashboard/app.py`.
- [x] **T13d**: Implementar el generador de "Certificación de Origen de Fondos / Compliance Bancario" en `src/reporting/excel_reporter.py` para justificación ante bancos.
- [x] **T14**: Integrar alertas automáticas de spread y comando `/spread` en `src/integrations/telegram_notifier.py`.
- [x] **T15**: Actualizar `TradeResult`, `ExcelReporter` y `SheetsExporter` para incluir la columna de "Fecha y Hora" en el Detalle Fiscal.
- [x] **T16**: Implementar `send_document()` en `TelegramNotifier` y el servicio de cierre fiscal mensual automatizado con envío de `.xlsx` a Telegram y comando `/cierre_mensual`.
- [x] **T17**: Implementar `IdentityService` en `src/security/identity_service.py` con triple fallback en cascada (Caché local SQLite, SENIAT XML, CNE scraping) y extractor de cédula desde métodos de pago.
- [x] **T18**: Escribir suite de pruebas unitarias en `tests/unit/test_spread_monitor.py` y `tests/unit/test_arbitrage_matrix.py`.
- [x] **T19**: Ejecutar suite completa (`pytest`, `ruff`, `mypy`) y documentar en `memory.md`.

