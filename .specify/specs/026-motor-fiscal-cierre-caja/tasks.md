# TASKS-026: Checklist Atómico de Implementación (SDD + TDD)

- [x] **T26.0** Crear especificación SDD `026-motor-fiscal-cierre-caja` (`spec.md`, `plan.md`, `tasks.md`).
- [x] **T26.1 [TDD-Rojo]** Escribir suite unitaria en `tests/unit/test_spec026_islr_and_exports.py` validando Tarifa 1 (DPN-99025), Tarifa 2 (DPJ-99026 real `2.716.569,82 -> 902.133,73`), SPE en TCMV, ausencia de `bcv_rate=1.0`, saldo inicial en exportes, deducción unificada de comisiones bancarias/cripto, alerta pago tercero, sincronización Binance Pay/Depósitos/Retiros y hojas Excel/PDF/VET.
- [x] **T26.2** Implementar `src/reporting/islr_calculator.py` (UT Bs. 43, Tarifa 1/2, DPN-99025 / DPJ-99026, SPE `SNAT/2026/00099`, detector de pago de tercero).
- [x] **T26.3** Corregir `src/reporting/tax_engine.py` (eliminar `bcv_rate=1.0`, advertencia de inventario insuficiente, soporte `initial_inventory` consistente en FIFO/AVG).
- [x] **T26.4** Corregir `src/reporting/fiscal_reconciler.py` (unificar descuento `bank_vouchers_fees` en ganancia neta, BCV real sin `1.0`) y `src/reporting/accounting_engine.py` (descontar `p2p_crypto_fees` en `get_live_theoretical_balance`).
- [x] **T26.5** Actualizar `src/reporting/reconciliation_engine.py` y `src/integrations/statement_importer.py` (recalibración de scoring OCR sin romper sugeridos + bandera discreta `third_party_alert`).
- [x] **T26.6** Extender `src/core/binance_client.py` (`get_deposit_history`, `get_withdraw_history`) y `src/api/routes/accounting.py` (sync integral Pay+Dep+Retiros, VET UTC-4 en `/journal`, `initial_usdt_cost_ves` + `cost_method` en `_build_accounting_export_context` / exportes).
- [x] **T26.7** Actualizar `src/reporting/excel_reporter.py` (nueva pestaña `Resumen Ejecutivo SENIAT`, formato `#,##0.00` + `@`, leyenda papel de trabajo, VET en reportes secundarios) y `src/reporting/pdf_reporter.py` (bloque DPN/DPJ, corrección Decreto IGTF `0%`).
- [x] **T26.8** Actualizar `src/core/binance_history_syncer.py`, `src/api/routes/orders.py` (`Banco / Método de Pago` y filtros en export) y `src/reporting/sheets_exporter.py` (hora VET y limpieza técnica).
- [x] **T26.9** Pulir frontend en `frontend/src/lib/api.ts`, `frontend/src/app/accounting/page.tsx`, `frontend/src/components/statement-import-modal.tsx` y `frontend/src/app/orders/page.tsx` (Pay/Otros + Salidas Binance visuales sin romper diseño Bento, modal mejorado, selector FIFO/AVG, alertas discretas).
- [x] **T26.10** Ejecutar verificación integral (`pytest`, `ruff`, `mypy`, `npm run build`), auditorías `venezuela-tax-cpa` + `security-review` y actualizar `memory.md`.
