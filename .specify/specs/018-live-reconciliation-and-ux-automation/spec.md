# SPEC-018: Automatización de Conciliación en Vivo, UX Operativa y Saldo Teórico Dinámico

## 1. Visión y Objetivos
Optimizar la experiencia del trader en el flujo diario de registro y conciliación contable sin fricción manual:
1. **Botones Inline en Telegram para OCR**: Al enviar una foto de comprobante, si no se auto-identifica con 100% de certeza si es Compra o Venta, Telegram presenta botones interactivos (`[ 🟢 Venta (Recibí VES) ]` / `[ 🔴 Compra (Pagué VES) ]`) para clasificar en un solo toque.
2. **Saldo Final Teórico Dinámico**: El saldo final no debe ser obligatorio al inicio del mes. Se calcula en tiempo real `Saldo Teórico = Saldo Inicial + Entradas - Salidas` y se habilita un botón "Cerrar Mes y Fijar Saldo Final" el último día del período.
3. **Desglose Multi-Banco del Saldo Inicial**: Permitir declarar saldos iniciales separados por banco (BDV, Banesco, Mercantil, Efectivo/Otros).
4. **Auto-matching Asíncrono de Comprobantes Huérfanos**: Cuando se sincronicen órdenes de Binance (API o CSV) o se suba un capture previo a la orden, un proceso en background reconcilia automáticamente comprobantes huérfanos con órdenes en una ventana temporal de 24-48h.
5. **Telemetría Dual en Telegram**: Mostrar en cada alerta o consulta de orden: `Ganancia Real ($ USD)` y `Base Fiscal SENIAT (VES a tasa BCV del día)`.

## 2. Plan de Arquitectura y Contratos

### A. Botones Interactivos Telegram (`src/integrations/telegram_notifier.py`)
- Extender `process_receipt_photo` para que devuelva `reply_markup` con `InlineKeyboardMarkup` si el comprobante queda en estado `UNMATCHED` o requiere confirmación de movimiento (`DEBIT` vs `CREDIT`).
- Agregar callbacks `/voucher_set_type:<voucher_id>:DEBIT` y `/voucher_set_type:<voucher_id>:CREDIT`.

### B. Saldo Teórico Dinámico y Multi-Banco (`src/reporting/accounting_engine.py` & `src/api/routes/accounting.py`)
- Endpoint `GET /api/accounting/balances/live?year=YYYY&month=MM` que calcula en caliente el saldo teórico por banco y en cripto.
- Soporte para desglosar saldos iniciales bancarios en la base de datos o en la sesión del trader.

### C. Reconciliación Asíncrona de Huérfanos (`src/integrations/receipt_ocr.py` & `src/data/repositories.py`)
- Método `reconcile_orphan_vouchers(db: Session, trader_id: int)` que barre comprobantes `UNMATCHED` y los empareja con órdenes recién ingresadas.
