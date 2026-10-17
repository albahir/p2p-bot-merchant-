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

### Fase 3: Integración de Google Stitch (MCP) y Modernización de UI
- [ ] **T10**: Registrar la configuración del servidor MCP de Google Stitch en `C:\Users\jonan\.gemini\config\mcp_config.json`.
- [ ] **T11**: Documentar la guía de obtención de API Key de Stitch y sincronización de pantallas.
- [ ] **T12**: Aplicar mejoras de diseño fintech (Glassmorphism, tarjetas de métricas, estilos de tablas) al Dashboard Streamlit.

### Fase 4: Monitores Proactivos, Cierre Mensual y Verificación de Cédula
- [ ] **T13**: Diseñar e implementar `SpreadMonitor` en `src/core/spread_monitor.py` para comparar el mercado P2P contra `bcv.org.ve`.
- [ ] **T14**: Integrar alertas de spread en `TelegramQueueDispatcher`.
- [x] **T15**: Actualizar `TradeResult`, `ExcelReporter` y `SheetsExporter` para incluir la columna de "Fecha y Hora" en el Detalle Fiscal.
- [x] **T16**: Implementar `send_document()` en `TelegramNotifier` y el servicio de cierre fiscal mensual automatizado con envío de `.xlsx` a Telegram y comando `/cierre_mensual`.
- [x] **T17**: Implementar `IdentityService` en `src/security/identity_service.py` con triple fallback en cascada (Caché local SQLite, SENIAT XML, CNE scraping) y extractor de cédula desde métodos de pago.
- [x] **T18**: Escribir suite de pruebas unitarias para Fecha/Hora, Cierre Mensual y Servicio de Identidad con 100% de cobertura.
- [x] **T19**: Ejecutar suite completa (`pytest`, `ruff`, `mypy`) y documentar en `memory.md`.
