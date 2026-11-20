# Tasks: SPEC-024 Importador Universal de Estados de Cuenta Bancarios (PDF / Excel / CSV)

## Fase 1: Dependencias, Normalización Bancaria Universal y Especificación
- [x] T24.1: Validar estructura SDD (`spec.md`, `plan.md`, `tasks.md` creados) e instalar/registrar `pypdf>=5.0.0` en `pyproject.toml`.
- [x] T24.2: Ampliar `normalize_bank_name` y agregar `detect_bank_from_text` en `src/reporting/normalizers.py` con catálogo completo de bancos venezolanos (20+ entidades y códigos SUDEBAN `0102`-`0191`) preservando bancos desconocidos.

## Fase 2: Motor Universal de Parseo y Cuadre Matemático (TDD Red -> Green)
- [x] T24.3: Escribir pruebas unitarias e integración en rojo (`tests/unit/test_statement_importer.py`) cubriendo:
  - Extracción tabular universal (CSV `;` / `,`, XLSX con filas previas de título, formato numérico venezolano `1.500,50` e internacional `1,500.50`, columna única con signo y columnas separadas Cargo/Abono).
  - Extracción PDF nativa multi-banco (PDFs generados en memoria simulando diseños estilo Banesco/BDV/Mercantil/genérico con orden ascendente y descendente y conceptos multilínea).
  - Verificación matemática de saldo acumulado (`balance_ok` verde vs `balance_discrepancy` rojo al corromper un monto).
  - Respaldo mockeado con Gemini AI para PDF escaneado sin capa de texto.
  - Clasificación y deduplicación contra `BankVoucher` existentes, emparejamiento por monto + ventana VET (`UTC-4`), aislamiento de `IGNORE_NON_P2P` (no crea asientos ni contamina ISLR), detección de `BANK_FEE`, y rechazo Fail-Closed de archivos inválidos o períodos cerrados (`FiscalPeriodSnapshot`).
- [x] T24.4: Implementar `src/integrations/statement_importer.py` (`BankStatementImporter`) pasando en verde todos los tests unitarios de T24.3.

## Fase 3: Endpoints REST y Asientos Contables Especializados
- [x] T24.5: Agregar `record_bank_fee_voucher` y `record_capital_transfer_voucher` (o manejo explícito en `AccountingEngine`) en `src/reporting/accounting_engine.py` garantizando partida doble SHA-256 (`SUM(Debe) == SUM(Haber)`).
- [x] T24.6: Exponer `POST /api/accounting/statements/preview` y `POST /api/accounting/statements/commit` en `src/api/routes/accounting.py` con validación estricta de archivo, tenant isolation (`user_id`), verificación de período cerrado y pruebas de integración.

## Fase 4: Interfaz Frontend Multi-Banco en `/accounting`
- [x] T24.7: Agregar tipos y clientes `previewBankStatement` y `commitBankStatement` en `frontend/src/lib/api.ts`.
- [x] T24.8: Implementar botón e interfaz/modal de previsualización, mapeo opcional de columnas, semáforo de cuadre de saldo y clasificación de movimientos en `frontend/src/app/accounting/page.tsx` y `frontend/src/components/statement-import-modal.tsx`.

## Fase 5: Verificación Final, Auditorías y Documentación
- [x] T24.9: Ejecutar batería completa `pytest`, `ruff check .`, `mypy src/ scripts/` y `tsc --noEmit`.
- [x] T24.10: Ejecutar auditorías obligatorias `security-review` y `venezuela-tax-cpa` y actualizar `memory.md` (ADR 061).
