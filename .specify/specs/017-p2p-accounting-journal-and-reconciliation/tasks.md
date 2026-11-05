# Tareas Atómicas: SPEC-017 (Libro Diario, Libro Mayor, Conciliación Multi-Factorial y Régimen Histórico BCV)

## 📌 Lista de Tareas Atómicas (Ciclo TDD)

### Fase 1: Capa de Normalización, Sanitización y Seguridad de Datos
- [x] **T01**: Crear módulo `src/reporting/normalizers.py` con `normalize_text`, `normalize_bank_name`, `normalize_cedula`, `normalize_phone`, `normalize_reference` y `parse_monetary_amount` (resiliencia a comas, puntos y símbolos).
- [x] **T02**: Escribir pruebas unitarias en `tests/unit/test_normalizers.py` cubriendo todos los casos de texto sucio, mayúsculas/minúsculas, tildes, prefijos y decimales.

### Fase 2: Modelos de Datos y Repositorios Contables
- [x] **T03**: Actualizar `BankVoucher` en `src/data/models.py` con `destination_bank`, `concept`, `sender_phone`, `bank_fee_ves`, `total_debited_ves`, `payment_method`, `movement_type`, `reconciliation_score`.
- [x] **T04**: Actualizar `Order` en `src/data/models.py` con `completed_at` y `payment_method`.
- [x] **T05**: Crear modelo `BCVRateHistory` y `JournalEntry` (con hash encadenado SHA-256) en `src/data/models.py`.
- [x] **T06**: Implementar `BCVHistoryRepository` y `JournalEntryRepository` en `src/data/repositories.py`.
- [x] **T07**: Escribir y verificar pruebas unitarias de persistencia en `tests/unit/test_accounting_models.py`.

### Fase 3: Motor de Tasas BCV con Fecha Valor y Backfill Histórico
- [x] **T08**: Implementar `BCVHistoryService` en `src/reporting/bcv_history_service.py` con resolución estricta de Fecha Valor (hora local VE UTC-4, regla de fin de semana al viernes previo, y bloqueo de activación de la tasa de mañana antes de medianoche).
- [x] **T09**: Implementar método de auto-población masiva retroactiva para órdenes históricas de Binance en `BCVHistoryService.backfill_orders()`.
- [x] **T10**: Escribir y verificar pruebas unitarias en `tests/unit/test_bcv_history_service.py`.

### Fase 4: OCR Adaptativo (Gemini Vision) y Clasificación Bancaria
- [x] **T11**: Actualizar `BankReceiptOCR` en `src/integrations/receipt_ocr.py` para extraer `concept`, `phone_number`, `destination_bank`, distinguir `PAGO_MOVIL` vs `TRANSFERENCIA` y auto-calcular comisiones (0% mismo banco, 0.3% interbancario emitido, 0% recibido).
- [x] **T12**: Escribir y verificar pruebas unitarias en `tests/unit/test_receipt_ocr_enhanced.py`.

### Fase 5: Motor de Conciliación Multi-Factorial con Score (0-100%)
- [x] **T13**: Implementar `P2PReconciliationEngine` en `src/reporting/reconciliation_engine.py` con filtros excluyentes de flujo/hora, matriz de scoring y niveles de decisión (Verde $\ge 90\%$, Amarillo $60-89\%$, Gris $<60\%$).
- [x] **T14**: Escribir y verificar pruebas unitarias en `tests/unit/test_reconciliation_engine.py`.

### Fase 6: Motor Contable (Libro Diario y Libro Mayor)
- [x] **T15**: Implementar `AccountingEngine` en `src/reporting/accounting_engine.py` con generación de asientos de partida doble (Debe = Haber) con hash SHA-256 y cálculo mensual de saldos iniciales y finales para Banco VES, Activos USDT y Comisiones.
- [x] **T16**: Escribir y verificar pruebas unitarias en `tests/unit/test_accounting_engine.py`.

### Fase 7: Exportadores (Excel Multi-Pestaña y PDF Contable)
- [x] **T17**: Actualizar `ExcelReporter` en `src/reporting/excel_reporter.py` para generar las 4 pestañas: *Libro Diario*, *Libro Mayor*, *Conciliación Bancaria*, *Liquidación Fiscal SENIAT*.
- [x] **T18**: Implementar `PDFReporter` en `src/reporting/pdf_reporter.py` para generar reportes oficiales imprimibles con membrete fiscal.
- [x] **T19**: Actualizar `SheetsExporter` para sincronizar las nuevas columnas de Libro Diario y Libro Mayor.
- [x] **T20**: Escribir pruebas unitarias de exportación en `tests/unit/test_accounting_exporters.py`.

### Fase 8: API REST y Rutas FastAPI
- [x] **T21**: Implementar rutas en `src/api/routes/accounting.py` (`GET /journal`, `GET /ledger`, `GET /export/excel`, `GET /export/pdf`, `POST /vouchers/upload`, `POST /vouchers/{id}/match`).
- [x] **T22**: Registrar el nuevo router en `src/api/main.py`.
- [x] **T23**: Escribir y verificar pruebas de integración de API en `tests/integration/test_api_accounting.py`.

### Fase 9: Interfaz de Usuario (Next.js 14)
- [x] **T24**: Crear o actualizar la vista contable en `frontend/src/app/accounting/` (o integración en `/fiscal`) con selector de mes, tarjetas de Saldo Inicial/Final, tabla de Libro Diario con filtros, visor de Libro Mayor y zona de arrastre masiva (Dropzone).
- [x] **T25**: Compilar con `npm run build` y verificar 0 errores de TypeScript y renderizado.

### Fase 10: Verificación Final y Documentación
- [x] **T26**: Ejecutar suite completa (`pytest`, `mypy src/`, `ruff check .`) garantizando 100% pruebas en verde y 0 errores.
- [x] **T27**: Registrar formalmente el avance en `tasks.md` y documentar el ADR 052 en `memory.md`.
