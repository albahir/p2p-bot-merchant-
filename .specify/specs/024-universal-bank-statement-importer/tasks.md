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

## Fase 6: Motor Geométrico Universal (`pdfplumber`), Multi-Formato Real y Deduplicación de Impresión Bancaria
- [x] T24.11: Actualizar `requirements.txt`, `pyproject.toml` (`pdfplumber>=0.11.4,<0.11.11`) y mejorar `detect_bank_from_text` en `src/reporting/normalizers.py` para identificar códigos SUDEBAN enmascarados (`0102****3046`).
- [x] T24.12: Escribir pruebas TDD en rojo (`tests/unit/test_statement_importer.py`) cubriendo formato BDV real (`Referencia | Descripción | Fecha | Mov | Débito | Crédito | Saldo`), celdas centradas verticalmente, filas partidas entre saltos de página, filas duplicadas de impresión BDV con saldo idéntico (`delta == 0`), formatos estilo Provincial/Mercantil/Banesco con doble columna de fecha o monto único + columna `Tipo`, PDFs >60 páginas y respaldo IA por lotes en PDFs escaneados.
- [x] T24.13: Implementar motor geométrico universal con `pdfplumber` en `src/integrations/statement_importer.py` (clustering + cabeceras flexibles, ensamblado multilínea vertical/inter-página, filtro anti-duplicado matemático, límites `150 págs / 5,000 filas`, fallback IA en lotes de 4 páginas) pasando todas las pruebas en verde.
- [x] T24.14: Validar `pytest`, `ruff`, `mypy`, `security-review`, `venezuela-tax-cpa` y documentar ADR 069 en `MEMORY.md`.

## Fase 7: Motor Dual-OCR Local (`RapidOCR` + `Tesseract 5`) con Árbitro de Conciliación Matemática y Soporte de Imágenes
- [x] T24.15: Registrar dependencias OCR gratuitas (`rapidocr-onnxruntime`, `onnxruntime`, `pytesseract`, `tesseract-ocr`, `tesseract-ocr-spa`) en `requirements.txt`, `pyproject.toml` y `docker/Dockerfile.api`.
- [x] T24.16: Escribir pruebas TDD en rojo (`tests/unit/test_statement_importer.py`) cubriendo validación Fail-Closed de imágenes (`.png`/`.jpg`/`.webp`), arbitraje Dual-OCR cuando un motor descuadra o falla (`balance_verified` gana), rescate fila-a-fila por consenso matemático y extracción end-to-end con `RapidOCR` local sobre imagen generada.
- [x] T24.17: Implementar soporte de imágenes y motor Dual-OCR local en `src/integrations/statement_importer.py` (`RapidOCR` + `Tesseract 5` con preprocesado 2x `Pillow`, coincidencia difusa de cabeceras OCR, arbitraje por puntuación matemática y consenso fila-a-fila).
- [x] T24.18: Ampliar `frontend/src/app/accounting/page.tsx` (`accept` con `.png,.jpg,.jpeg,.webp`) y verificar extracción sobre capturas reales (Banesco, BNC, Mercantil).
- [x] T24.19: Ejecutar batería completa (`pytest`, `ruff`, `mypy`, `tsc`, `pip check`), auditorías `security-review` y `venezuela-tax-cpa`, y documentar ADR 071 en `MEMORY.md`.

## Fase 8: Hardening de Ingesta Segura Anti-Backdoor / DoS Sin Fricción para el Usuario
- [x] T24.20: Escribir pruebas TDD en rojo (`tests/unit/test_file_security_guards.py` y `tests/unit/test_statement_importer.py`) cubriendo rechazo de PDF con `/JS`/`/Launch`/`/EmbeddedFiles` (sin falsos positivos en `/URI`/`/OpenAction` zoom), `.xlsx` con macros VBA/XXE/ZIP-bomb, `.xls` ejecutable vs HTML bancario válido, bombas de píxeles 144 MP vs capturas móviles largas (`1080x12500`), pixel-wash EXIF, entorno limpio de subproceso OCR y límites HTTP en `/vouchers/upload`, `/orders/upload` y `/statements/preview`.
- [x] T24.21: Implementar `src/security/file_guards.py` e integrarlo en `src/integrations/statement_importer.py`, `src/api/routes/accounting.py`, `src/api/routes/orders.py`, `src/core/binance_history_syncer.py`, `frontend/src/app/accounting/page.tsx` y `docker/docker-compose.yml` (hardening de contenedores `cap_drop`, `no-new-privileges`, `mem_limit`, `pids_limit`).
- [x] T24.22: Ejecutar suite completa (`pytest`, `ruff`, `mypy`, `tsc`, `pip check`), auditorías `security-review` y `venezuela-tax-cpa` y actualizar `MEMORY.md` (ADR 072).
