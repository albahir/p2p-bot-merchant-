# Tasks 014: Reconstrucción Contable P2P de 6 Piezas y OCR Bancario

## 📋 Lista Atómica de Tareas (Ciclo TDD)

### Fase 1: Modelos de Datos y Persistencia
- [ ] **T01**: Crear modelos SQLAlchemy `WalletMovement`, `BankVoucher` y `FiscalPeriodSnapshot` en `src/data/models.py`.
- [ ] **T02**: Crear repositorios de acceso a datos en `src/data/repositories.py` (`WalletMovementRepository`, `BankVoucherRepository`, `FiscalSnapshotRepository`).
- [ ] **T03**: Escribir pruebas unitarias en `tests/unit/test_fiscal_repositories.py` verificando CRUD e idempotencia.

### Fase 2: Parser Inteligente de Archivos Binance (.csv y .xlsx)
- [ ] **T04**: Implementar `BinanceFileParser` en `src/core/file_parser.py` para procesar archivos de Órdenes C2C, Depósitos y Retiros, con omisión automática de metadatos en Excel y mapeo de encabezados en español.
- [ ] **T05**: Escribir pruebas unitarias en `tests/unit/test_file_parser.py` utilizando los formatos reales compartidos por el usuario.

### Fase 3: OCR Bancario de Comprobantes en VES con Gemini Vision
- [ ] **T06**: Implementar `BankReceiptOCR` en `src/integrations/receipt_ocr.py` conectado al `AIKeyPool` (3 claves API con balanceo round-robin) para extraer referencia, monto VES, banco y cédula.
- [ ] **T07**: Implementar algoritmo de auto-matching entre comprobantes bancarios y órdenes P2P (`match_receipt_with_orders`).
- [ ] **T08**: Escribir pruebas unitarias en `tests/unit/test_receipt_ocr.py` con fixtures y mocks de respuestas de Gemini Vision.

### Fase 4: Motor de Reconstrucción de 6 Piezas y Snapshots
- [ ] **T09**: Extender `FIFOCostMethod` en `src/reporting/tax_engine.py` para admitir lotes de inventario inicial valorados a la tasa oficial BCV.
- [ ] **T10**: Implementar `FiscalReconciler` en `src/reporting/fiscal_reconciler.py` ejecutando la ecuación de consistencia de 6 piezas y detección de mermas.
- [ ] **T11**: Escribir pruebas unitarias en `tests/unit/test_fiscal_reconciler.py` verificando balance exacto y discrepancias.

### Fase 5: Exportación Multi-Pestaña (Excel y Google Sheets)
- [ ] **T12**: Extender `ExcelReporter` en `src/reporting/excel_reporter.py` para generar las 4 pestañas auditadas: 1) Resumen Fiscal, 2) Detalle P2P, 3) Depósitos/Retiros, 4) Conciliación Bancaria.
- [ ] **T13**: Extender `SheetsExporter` en `src/reporting/sheets_exporter.py` para sincronizar las 4 pestañas correspondientes en la hoja de Google Sheets.
- [ ] **T14**: Escribir pruebas unitarias en `tests/unit/test_fiscal_reporters.py`.

### Fase 6: UI en Dashboard Streamlit y Notificaciones en Telegram
- [ ] **T15**: Crear la vista de "Reconstrucción Fiscal" en `src/reporting/dashboard/app.py` con carga de archivos de Binance, uploader de capturas bancarias y tarjetas de 6 piezas.
- [ ] **T16**: Agregar soporte para recepción de fotos de comprobantes en `src/integrations/telegram_notifier.py` con OCR automático y comando `/conciliacion`.
- [ ] **T17**: Ejecutar suite completa (`pytest`, `ruff`, `mypy`) asegurando 100% verde sin errores.
- [ ] **T18**: Actualizar `memory.md` con las decisiones arquitectónicas y cerrar paquete.
