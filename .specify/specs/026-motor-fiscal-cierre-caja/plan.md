# PLAN-026: Arquitectura de Ejecución por Fases (TDD)

## Fase 1 — Motor Puro Fiscal, Conciliación y Conectores (Backend)
1. **`src/reporting/islr_calculator.py` (Nuevo módulo puro)**:
   - Constantes vigentes Nov 2026: `UT_VES = 43.0`, desgravamen único `774 UT` (`Bs. 33.282,00`), rebaja personal `10 UT` (`Bs. 430,00`), tablas Art. 50 (Tarifa 1) y Art. 52 (Tarifa 2) LISLR, umbrales `SNAT/2026/00099` (`600k/50k TCMV` interior, `3M/250k TCMV` Capital) y helper `is_third_party_counterparty_mismatch`.
   - `compute_islr_estimation()` usando aritmética `Decimal` con truncamiento/precisión oficial SENIAT de 2 decimales (`ROUND_DOWN` en cálculo de impuesto determinado para coincidencia exacta con portal `DPJ-99026` `Bs. 902.133,73`).
   - `build_seniat_casillas()` devolviendo mapeo completo de casillas Sección E + Sección C/G + semáforo SPE/ISLR.
2. **`src/reporting/tax_engine.py`**:
   - Agregar `inventory_shortfall_crypto: float = 0.0` y `unmatched_inventory_warning: str | None = None` en `TradeResult` / propiedades `warnings` en `FIFOCostMethod` y `WeightedAverageCostMethod`.
   - Eliminar fallback `1.0` cuando `bcv_rate <= 0`: intentar tasa `fallback_bcv_rate` (> 0) u última tasa válida vista; si no existe, dejar `bcv_rate = 0.0` y `net_profit_usd = 0.0` con advertencia explícita.
3. **`src/reporting/fiscal_reconciler.py`**:
   - Descontar `bank_vouchers_fees` en `net_profit_ves` (y ajustar `net_profit_usd` con tasa BCV válida) para unificar exactamente con `ExcelReporter` y `PDFReporter`.
   - Evitar fallback `1.0` usando `BCVHistoryService` o `0.0` sin dividir por 1.0.
   - Exponer campos `bank_fees_ves`, `p2p_fees_ves`, `third_party_alerts_count`, `inventory_warnings`, `unique_counterparties`.
4. **`src/reporting/accounting_engine.py`**:
   - Descontar `p2p_crypto_fees` en `get_live_theoretical_balance` y exponer `p2p_fee_usdt` en `LiveBalanceSummary` / `LiveBalanceResponse`.
5. **`src/reporting/reconciliation_engine.py` & `src/integrations/statement_importer.py`**:
   - Calibrar scoring en `P2PReconciliationEngine` para permitir `AUTO_MATCHED` (>= 90%) por monto + banco + titular o proximidad horaria cuando Binance no provee referencia bancaria, manteniendo `SUGGESTED` para monto + banco sin señales adicionales.
   - Agregar detección de `"Posible pago de tercero"` en `P2PReconciliationEngine` y en `BankStatementImporter` (`third_party_alert`, `third_party_detail`).
6. **`src/core/binance_client.py` & `src/api/routes/accounting.py`**:
   - Agregar `get_deposit_history` y `get_withdraw_history` en `BinanceP2PClient`.
   - Unificar en `POST /api/accounting/wallet-movements/sync-binance-pay` la ingesta opcional de depósitos y retiros USDT además de Binance Pay con tolerancia a llaves sin permisos Spot.
   - Corregir VET (`UTC-4`) en `GET /api/accounting/journal` y pasar `initial_usdt_cost_ves`, `cost_method` e historial previo en `_build_accounting_export_context` / `/export/excel` / `/export/pdf`.

## Fase 2 — Exportadores Listos para Declarar (Excel, PDF, Órdenes y Sheets)
1. **`src/reporting/excel_reporter.py`**:
   - Añadir pestaña `"Resumen Ejecutivo SENIAT"` al inicio de `generate_accounting_report` con leyenda legal, KPIs ejecutivos, mapeo completo DPN-99025 / DPJ-99026 y semáforo SPE/ISLR, más formatos numéricos `#,##0.00` y texto `@`.
   - Agregar filas resumen DPN/DPJ, método de costeo real y semáforo SPE en `"Liquidación Fiscal SENIAT"` manteniendo claves existentes.
   - Incorporar `Fecha y Hora (VET)` y columna de titularidad en `Conciliación Bancaria` y reportes secundarios (`generate_fiscal_reconstruction_report`, `generate_compliance_report`).
2. **`src/reporting/pdf_reporter.py`**:
   - Corregir texto IGTF a alícuota `0%` por Decreto N° 4.972.
   - Añadir bloque de Papel de Trabajo `DPN-99025 / DPJ-99026` y método dinámico `PEPS` vs `Costo Promedio Ponderado`.
3. **`src/core/binance_history_syncer.py` & `src/api/routes/orders.py`**:
   - Incluir columna `"Banco / Método de Pago"` en `generate_orders_df` y filtros opcionales en `/api/orders/export`.
4. **`src/reporting/sheets_exporter.py`**:
   - Agregar columna `Fecha y Hora (VET)` en todas las hojas exportadas y remover `Hash SHA-256` en `export_accounting`.

## Fase 3 — UI `/accounting` Pulida (Sin Alterar Diseño Actual)
1. **`frontend/src/lib/api.ts` & `frontend/src/app/accounting/page.tsx`**:
   - Actualizar tipos (`LiveBalanceState`, `SyncBinancePayResponse`, `StatementPreviewRow`, `downloadAccountingExcel/Pdf` con `cost_method`).
   - Transformar `Pay / Otros` en Card 2 (`SALDO USDT`) en sub-tarjetas simétricas (`Entradas Pay / Dep.` vs `Salidas Binance`) sin truncamientos, con subtítulo discreto de comisiones P2P y botones claros `[+ Mov.]` y `[Pay / Retiros]`.
   - Enriquecer modal de movimientos USDT con toggle visual `Entrada (+ USDT)` / `Salida en Binance (- USDT)`, chips de canal y previsualización de total debitado incluyendo comisión de red.
   - Enriquecer tab `Cuadre mensual` con selector `FIFO / Promedio`, estimación referencial DPN-99025 / DPJ-99026 y alertas discretas (título de tercero, faltante de inventario, umbral SPE).
   - Mostrar badge discreto `⚠ Tercero` por fila en `StatementImportModal` cuando exista discordancia real de titularidad.
