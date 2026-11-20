# SPEC-024: Importador Universal de Estados de Cuenta Bancarios (PDF / Excel / CSV)

**Especificación de Requerimientos Funcionales y Técnicos (SDD)**  
**Paquete:** `024-universal-bank-statement-importer`  
**Estado:** APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 19 de Noviembre de 2026  
**Dependencias:** `SPEC-001`, `SPEC-014`, `SPEC-017`, `SPEC-021`, `SPEC-022`

---

## 1. Visión General y Propósito (QUÉ)

### 1.1 Problema a Resolver
Los comerciantes P2P operan en múltiples bancos venezolanos (Banesco, Banco de Venezuela, Mercantil, Bancamiga, BBVA Provincial, BNC, Exterior, Tesoro, Banplus, BFC, etc.) y bancos internacionales. Al cierre de mes, la mayoría de cuentas naturales solo entregan su estado de cuenta oficial en **PDF** (y en banca empresa/web en **Excel/CSV/TXT**). Subir comprobantes uno por uno resulta inviable cuando existen decenas o cientos de movimientos mensuales.

### 1.2 Solución Propuesta
Construir un **Importador Universal de Estados de Cuenta Bancarios** agnóstico al banco que:
1. Acepte archivos **PDF** (texto nativo vectorial con respaldo multimodal IA opcional para PDFs escaneados o atípicos), **Excel (`.xlsx` / `.xls`)**, **CSV** y **TXT delimitado**.
2. Funcione para **cualquier entidad bancaria** mediante detección de cabeceras, alineación espacial por columnas (`x`-coordinates), inferencia de dirección por variación de saldo y mapeo manual de columnas cuando sea necesario.
3. Aplique **verificación matemática Fail-Closed** fila a fila sobre el saldo acumulado (`Saldo Anterior + Crédito - Débito == Saldo Siguiente`), detectando automáticamente orden cronológico ascendente o descendente.
4. Ejecute **previsualización interactiva antes de persistir**, cruzando con órdenes Binance P2P en horario **VET (`UTC-4`)**, deduplicando contra comprobantes ya subidos por OCR/Telegram, detectando comisiones bancarias (`0,30%` / `I.D.B.` / mantenimiento) y permitiendo excluir gastos personales o traspasos propios para no contaminar la contabilidad fiscal SENIAT.

---

## 2. Historias de Usuario

- **HU-01 (Carga Multi-Banco Universal)**: Como operador de cualquier banco (BDV, Banesco, Mercantil, Bancamiga, Provincial, BNC o cualquier otro), quiero subir mi estado de cuenta PDF o Excel/CSV del mes y ver cada movimiento normalizado sin depender de un banco específico.
- **HU-02 (Cuadre Matemático de Saldo)**: Como contador/operador, quiero que el sistema valide si los créditos, débitos y saldos del documento cuadran exactamente fila por fila, advirtiéndome al instante si una fila fue leída incorrectamente antes de tocar el Libro Diario.
- **HU-03 (Previsualización, Deduplicación y Aislamiento Fiscal)**: Como usuario P2P que usa su cuenta bancaria también para gastos personales, quiero revisar una vista previa donde el sistema ya emparejó las órdenes P2P de Binance, marcó comprobantes ya registrados (sin duplicar), identificó comisiones deducibles y me deje excluir gastos personales o traspasos propios antes de confirmar.
- **HU-04 (Aislamiento Multi-Tenant y Bloqueo de Períodos Cerrados)**: Como usuario de plataforma multi-cuenta, quiero que mis estados de cuenta se crucen únicamente con mis órdenes y comprobantes (`user_id`), y que el sistema impida importar movimientos sobre un mes cuyo cierre (`FiscalPeriodSnapshot`) ya fue sellado.

---

## 3. Reglas Funcionales y Normativas Obligatorias

1. **Horario Legal VET (`UTC-4`)**: Las fechas bancarias sin hora (`DD/MM/YYYY`) se normalizan en zona `America/Caracas` (`UTC-4`) para asegurar que operaciones nocturnas del último día del mes pertenezcan al mes fiscal correcto.
2. **Tolerancia Numérica Universal**: Soporte transparente de separadores venezolanos (`1.234.567,89`) e internacionales (`1,234,567.89`) mediante [`parse_monetary_amount`](file:///c:/p2p-bot-merchant/src/reporting/normalizers.py).
3. **Regla Fail-Closed (Constitución #2)**:
   - Rechazar archivos vacíos, corruptos, con extensión/magic bytes incompatibles o superiores al límite seguro (10 MB / 50 páginas / 2,000 filas).
   - Nunca asentar automáticamente movimientos no P2P como ingresos/costos de criptoactivos; requieren confirmación o quedan excluidos (`IGNORE_NON_P2P`).
   - Impedir `commit` si el período contable ya tiene snapshot cerrado, salvo que las filas pertenezcan a otro período abierto o el cierre no exista.
4. **Seguridad y Privacidad (`security-review`)**:
   - Sin logs de montos privados ni descripciones bancarias completas en `logging`.
   - Aislamiento estricto por `current_user.id` en vista previa, detección de duplicados y guardado.
   - Validación estricta de entrada Pydantic y protección contra inyección de fórmulas Excel/CSV (`=`, `+`, `-`, `@` al exportar textos importados).
