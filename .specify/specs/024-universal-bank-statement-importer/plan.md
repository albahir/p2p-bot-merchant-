# PLAN-024: Arquitectura del Importador Universal de Estados de Cuenta

**Paquete:** `024-universal-bank-statement-importer`  
**Basado en:** `SPEC-024` y `constitution.md`

---

## 1. Arquitectura General

El flujo se divide en dos pasos explícitos (**Preview -> Commit**) para garantizar comportamiento **Fail-Closed**:

```text
[Archivo PDF / XLSX / CSV / TXT]
        │
        ▼
  Validación de Archivo (tamaño <= 10MB, magic bytes, mime/extensión)
        │
        ├─► Tabular (CSV/TXT/XLSX/XLS): pandas/openpyxl + detector universal de cabeceras (o column_mapping manual)
        └─► PDF Nativo (pypdf layout + visitor_text X/Y / pdfplumber opcional): extracción espacial por coordenadas X/Y + multiline merge
                 └─► Fallback IA (si 0 filas / PDF escaneado y clave Gemini disponible): extracción JSON página por página
        │
        ▼
[Balance & Direction Verifier]
  - Detección automática orden ascendente / descendente por saldo
  - Inferencia Crédito vs Débito por variación de saldo si viene en columna única
  - Chequeo fila a fila: Saldo_prev + Crédito - Débito == Saldo_actual (tolerancia Bs 0.02)
        │
        ▼
[Reconciliation & Classification Preview Engine]
  - Normalización de banco (catálogo completo SUDEBAN 20+ bancos) y fecha VET (UTC-4)
  - Deduplicación contra BankVoucher del user_id (banco + referencia + tipo + monto + fecha ±2d)
  - Emparejamiento automático contra Order (COMPLETED, mismo user_id, fiat_amount ±0.05, fecha VET ±2d)
  - Sugerencia automática de comisiones (COMISION, PAGO MOVIL, I.D.B., ITF, MANTENIMIENTO)
        │
        ▼
  POST /api/accounting/statements/preview  ──►  Vista Previa Interactiva en /accounting (Next.js)
        │
        ▼ (Revisión y aprobación del usuario)
  POST /api/accounting/statements/commit   ──►  Persistencia transaccional en BankVoucher + AccountingEngine (SHA-256)
```

---

## 2. Componentes a Crear / Modificar

### 2.1 Dependencias y Normalización
- [`pyproject.toml`](file:///c:/p2p-bot-merchant/pyproject.toml): Agregar `pypdf>=5.0.0` (lector PDF ligero puro en Python con `extraction_mode="layout"` y `visitor_text` X/Y).
- [`src/reporting/normalizers.py`](file:///c:/p2p-bot-merchant/src/reporting/normalizers.py):
  - Ampliar `normalize_bank_name` con todas las entidades bancarias venezolanas y códigos SUDEBAN de 4 dígitos (`0102`..`0191`).
  - Agregar helper `detect_bank_from_text(text)` para identificar el banco emisor automáticamente desde encabezados de estados de cuenta PDF/CSV.

### 2.2 Servicio de Parseo Universal y Conciliación de Extractos
- `src/integrations/statement_importer.py` (nuevo módulo desacoplado):
  - `ParsedStatementRow`, `StatementPreviewResult`, `StatementRowDecision`, `StatementCommitResult`.
  - `BankStatementImporter`:
    - `parse_bytes(...)`: Despacho seguro según magic bytes / extensión (`.pdf`, `.xlsx`, `.xls`, `.csv`, `.txt`).
    - `_parse_tabular_dataframe(...)`: Detector heurístico de fila de encabezados, mapeo flexible multilingüe y soporte `column_mapping` explícito para layouts atípicos.
    - `_parse_pdf_bytes(...)`: Extracción con `pdfplumber` por coordenadas `x`/`y`, clasificación débito/crédito por posición horizontal de cabecera + inferencia por delta de saldo, unión de conceptos multilínea y fallback opcional con Gemini (`AIKeyPool`) ante PDFs escaneados.
    - `_verify_running_balances(...)`: Detección automática ascendente/descendente y marcado por fila de `balance_ok` / `balance_discrepancy`.
    - `build_preview(...)`: Deduplicación en BD, emparejamiento 1-a-1 con órdenes P2P no vinculadas usando proximidad temporal VET (`UTC-4`), y clasificación previa (`P2P_MATCH`, `BANK_FEE`, `DUPLICATE_EXISTING`, `UNMATCHED_REVIEW`).
    - `commit_import(...)`: Verificación de período cerrado (`FiscalPeriodSnapshot`), creación idempotente de `BankVoucher` y asiento contable en `AccountingEngine` (incluyendo asientos directos de comisiones bancarias `5.2.01` vs `1.1.01`, aportes/retiros de capital propio o exclusión `IGNORE_NON_P2P` sin tocar BD).

### 2.3 Contratos REST FastAPI ([`src/api/routes/accounting.py`](file:///c:/p2p-bot-merchant/src/api/routes/accounting.py))
- `POST /api/accounting/statements/preview`:
  - `multipart/form-data`: `file` (PDF/XLSX/XLS/CSV/TXT), `bank_name` opcional, `column_mapping_json` opcional, `year_hint` opcional.
  - Retorna metadata detectada (banco, fechas, cabeceras detectadas, cuadre de saldo global, total filas, filas clasificadas).
- `POST /api/accounting/statements/commit`:
  - Recibe lista de filas revisadas con su decisión (`action`: `P2P_MATCH` | `P2P_UNMATCHED` | `BANK_FEE` | `INTERNAL_TRANSFER` | `IGNORE`, `order_number` opcional, etc.).
  - Ejecuta persistencia atómica y retorna conteos exactos (`created_vouchers`, `matched_orders`, `bank_fees_recorded`, `skipped_duplicates`, `ignored_rows`, `journal_entries_created`).

### 2.4 Frontend Next.js ([`frontend/src/lib/api.ts`](file:///c:/p2p-bot-merchant/frontend/src/lib/api.ts), [`frontend/src/app/accounting/page.tsx`](file:///c:/p2p-bot-merchant/frontend/src/app/accounting/page.tsx))
- Agregar tipos y funciones `previewBankStatement` y `commitBankStatement`.
- En `/accounting`: añadir botón **"Importar estado (.pdf / .csv / .xlsx)"** junto a la conciliación, que abre un modal institucional amplio de **Previsualización Universal**:
  - Indicador de banco detectado (editable), estado de verificación matemática de saldo (`Saldo Cuadrado` / `Diferencia detectada en X filas`), y mapeador rápido de columnas si aplica.
  - Tabla de movimientos con selección masiva/individual de acción (`Orden P2P`, `Comisión`, `Traspaso propio`, `Ignorar gasto personal`, `Duplicado`) y selector de orden P2P sugerida.
  - Botón final de confirmación para asentar todo en un clic y recargar saldos, Diario y Mayor.

---

## 3. Verificación y Auditorías
1. **TDD estricto**: Escribir pruebas unitarias e integración en rojo en `tests/unit/test_statement_importer.py` antes de implementar `src/integrations/statement_importer.py`.
2. **Suite Completa**: Verificar `pytest`, `ruff`, `mypy`, `tsc --noEmit`.
3. **Auditorías Obligatorias**: `security-review` (archivos subidos, magic bytes, tenant isolation, límites anti-DoS) y `venezuela-tax-cpa` (VET `UTC-4`, comisiones deducibles, aislamiento de gastos personales, integridad de Libro Diario).
