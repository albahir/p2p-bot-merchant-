# SPEC-026: Motor Fiscal SENIAT (DPN-99025 / DPJ-99026), Conciliación Bancaria Antifraude y Mejora Visual de Pay / Salidas Binance

## 1. Objetivo
Unificar y blindar matemáticamente el cálculo fiscal venezolano (ISLR Persona Natural `DPN-99025` y Persona Jurídica `DPJ-99026`, UT = Bs. 43,00), la trazabilidad de inventario USDT (`PEPS / FIFO` y `Costo Promedio Ponderado` con saldo inicial valorado), la hora legal VET (`UTC-4`), la sincronización de entradas/salidas en Binance (`Binance Pay`, depósitos y retiros), las alertas preventivas discretas (pagos de terceros LOCDOFT/SUDEBAN y umbrales SPE `SNAT/2026/00099`), y pulir visualmente en `/accounting` las entradas de **Pay / Otros** y **Salidas en Binance** preservando íntegramente la estética actual del usuario.

## 2. Requisitos Funcionales
1. **Motor Puro ISLR y Mapeo SENIAT (`src/reporting/islr_calculator.py` / `tax_engine.py`)**:
   - Auto-detección de planilla oficial según Cédula/RIF: `V-`/`E-` (o sin RIF) $\to$ **Forma DPN-99025** (Tarifa N° 1, Art. 50 LISLR, desgravamen único `774 UT = Bs. 33.282,00` y rebaja personal `10 UT = Bs. 430,00`); `J-` $\to$ **Forma DPJ-99026** (Tarifa N° 2, Art. 52 LISLR).
   - Validación exacta de **DPJ-99026** (caso real: enriquecimiento `Bs. 2.716.569,82` $\to$ `Bs. 902.133,73` de impuesto determinado).
   - Parametrización en `UT = Bs. 43,00` (`SNAT/2025/000048`) y evaluación de umbrales **ISLR PN** (`1.000 UT` neto / `1.500 UT` bruto) y **SPE** (`SNAT/2026/00099`, G.O. N° 43.485: `600.000 / 50.000 TCMV` interior y `3.000.000 / 250.000 TCMV` Región Capital) comparados exclusivamente contra ingreso real y separados del capital rotativo bancario.
2. **Corrección de Cálculos Internos (6 Hallazgos)**:
   - Incluir `initial_usdt` e `initial_usdt_cost_ves` en `FIFOCostMethod` / `WeightedAverageCostMethod` dentro de `_build_accounting_export_context` (respetando fecha de corte) y advertir ante ventas que excedan inventario disponible en lugar de silenciar costo `0,00`.
   - Unificar Ganancia Neta (`net_profit_ves`) entre `FiscalReconciler`, `ExcelReporter` y `PDFReporter` deduciendo comisiones Exchange y Comisiones Bancarias (`5.2.01`), y unificar `fee_crypto` en `AccountingEngine.get_live_theoretical_balance`.
   - Eliminar el fallback silencioso `bcv_rate = 1.0` en `tax_engine.py` y `fiscal_reconciler.py`.
   - Unificar huso horario **VET (`UTC-4`)** en `GET /api/accounting/journal`, reportes Excel secundarios y `SheetsExporter`.
   - Permitir elegir método de costeo (`FIFO` vs `AVG`) en exportaciones `/api/accounting/export/excel` y `/export/pdf`.
   - Mejorar scoring en `P2PReconciliationEngine` y añadir detección de **"Posible pago de tercero"** (`UNIF / LOCDOFT`).
3. **Sincronización de Binance Pay, Depósitos y Salidas (Retiros) Binance**:
   - Extender `BinanceP2PClient` con métodos de solo lectura `/sapi/v1/capital/deposit/hisrec` y `/sapi/v1/capital/withdraw/history` (tolerante si la API Key no tiene permisos Spot).
   - En `/api/accounting/wallet-movements/sync-binance-pay`, sincronizar idempotente y acumulativamente Binance Pay + Depósitos + Retiros (`salidas en Binance` con comisión de red).
4. **Exportes Listos para Declarar (Excel, PDF, CSV/Órdenes y Google Sheets)**:
   - Agregar hoja **`Resumen Ejecutivo SENIAT`** en `ExcelReporter.generate_accounting_report` con casillas `703..763` (`135`/`137`, `851`, `202`, `185`, `90`), contrapartes únicas, órdenes computadas, días operados, semáforo SPE/ISLR, formato `#,##0.00`, columnas largas en `@` y leyenda obligatoria de **Papel de Trabajo Contable**. Preservar intactas las 7 pestañas previas y sus coordenadas probadas.
   - En `PDFReporter`: agregar bloque resumen `DPN-99025 / DPJ-99026` con leyenda de Papel de Trabajo y corregir texto legal IGTF (`alicuota del 0% en Bolivares por Decreto Nro. 4.972`).
   - En `/orders/export` y `SheetsExporter`: añadir columna `Banco / Método de Pago`, hora `VET (UTC-4)` y retirar columnas técnicas ruidosas en Sheets contable.
5. **Mejora Visual de Pay/Otros, Salidas Binance y Alertas Discretas en `/accounting`**:
   - Preservar íntegramente el diseño Bento actual de 3 tarjetas y 4 pestañas de `/accounting` y `/calculator`.
   - Rediseñar internamente la sub-sección `Pay / Otros` de la tarjeta `SALDO USDT` en una grilla simétrica de 2 bloques (`Entradas Pay / Dep.` y `Salidas Binance`) eliminando el truncamiento `-0..` y separando claramente comisiones P2P y de red.
   - Mejorar visualmente el modal de movimientos USDT (selectores visuales `Entrada` vs `Salida en Binance`, chips de canal y cálculo en vivo del débito total con comisión de red) y la pestaña `Movimientos USDT` (resumen superior y badges direccionales).
   - Mostrar todas las alertas fiscales, de inventario, de terceros y de umbrales SPE de forma **discreta** (pills compactas e informativas, sin saturar la interfaz).
