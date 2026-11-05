# Tasks: SPEC-018 Automatización de Conciliación en Vivo y UX Operativa

## Fase 1: Motor Contable y Saldo Teórico Dinámico
- [x] T18.1: Escribir tests unitarios para cálculo de Saldo Teórico en tiempo real (`tests/unit/test_accounting_live_balance.py`).
- [x] T18.2: Implementar método `get_live_theoretical_balance()` en `src/reporting/accounting_engine.py` desglosado por banco y USDT.
- [x] T18.3: Agregar endpoint `GET /api/accounting/balances/live` en `src/api/routes/accounting.py` y schemas en `src/api/schemas/accounting.py`.



## Fase 2: Reconciliación Asíncrona de Comprobantes Huérfanos
- [x] T18.4: Escribir tests para auto-conciliación de comprobantes desfasados (`tests/unit/test_orphan_vouchers_reconciliation.py`).
- [x] T18.5: Implementar `reconcile_orphan_vouchers()` en `src/integrations/receipt_ocr.py` con ventana de coincidencia de 24-48h por monto en VES.
- [x] T18.6: Conectar trigger de reconciliación en la importación de órdenes y endpoint `POST /api/accounting/vouchers/reconcile-orphans`.


## Fase 3: Telegram UX con Botones Inline
- [x] T18.7: Escribir tests unitarios para botones inline de comprobante en Telegram (`tests/unit/test_telegram_voucher_actions.py`).
- [x] T18.8: Extender `process_receipt_photo` en `src/integrations/telegram_notifier.py` para responder con botones táctiles `[🟢 Venta]` / `[🔴 Compra]`.
- [x] T18.9: Manejar callback queries de asignación rápida (`/vtype:<id>:<action>`) y sincronizar automáticamente a Google Sheets tras el toque.
- [x] T18.10: Añadir telemetría dual `(USD Real | BCV Fiscal)` en notificaciones de órdenes de Telegram.



## Fase 4: Frontend y Validación Integral
- [x] T18.11: Actualizar `frontend/src/app/accounting/page.tsx` para mostrar "Saldo Teórico en Curso" y botón "Cerrar Mes".
- [x] T18.12: Ejecutar validación de cobertura (`pytest`, `ruff check`, `tsc --noEmit`) y documentar en `memory.md`.

