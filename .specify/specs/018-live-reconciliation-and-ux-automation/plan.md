# Plan de Implementación: SPEC-018 Automatización de Conciliación y UX Operativa

## Fase 1: Motor Contable Dinámico y Multi-Banco
- [ ] Incorporar cálculo de `TheoreticalBalance` en `AccountingEngine` (`initial + inflows - outflows`).
- [ ] Soporte para desglose de balance inicial multi-banco en `AccountingEngine` y schemas Pydantic.
- [ ] Endpoint `GET /api/accounting/balances/live`.

## Fase 2: Reconciliación Asíncrona de Comprobantes Huérfanos
- [ ] Implementar `reconcile_orphan_vouchers()` en `BankReceiptOCR` y `BankVoucherRepository`.
- [ ] Trigger automático de reconciliación de huérfanos al importar órdenes de Binance (API o CSV).
- [ ] Endpoint `POST /api/accounting/vouchers/reconcile-orphans`.

## Fase 3: Telegram UX & Botones Interactivos
- [ ] Botones táctiles inline al procesar fotos con dudas de Débito/Crédito (`/voucher_type:<id>:DEBIT|CREDIT`).
- [ ] Handler de callback queries para actualizar comprobante y asentar en el Libro Diario + Google Sheets al hacer clic.
- [ ] Alertas con telemetría dual: `USD Real` + `Base Fiscal BCV en VES`.

## Fase 4: Frontend y Verificación
- [ ] Mostrar en `frontend/src/app/accounting/page.tsx` el Saldo Teórico Actual vs Saldo Inicial sin exigir Saldo Final hasta cierre.
- [ ] Tests unitarios y de integración TDD.
