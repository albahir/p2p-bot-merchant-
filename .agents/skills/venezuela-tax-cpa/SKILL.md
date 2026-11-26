---
name: venezuela-tax-cpa
description: Auditoría contable y tributaria para comercio P2P de criptoactivos en Venezuela (SENIAT, LISLR, BA VEN-NIF N° 12, IGTF Decreto 4.972, Providencia SNAT/2026/00099, SUDEBAN Res. 377.07). Obligatorio invocar y ejecutar ante modificaciones en cálculo fiscal, tasas BCV, motor contable, exportaciones Excel/PDF/CSV/Sheets o conciliación bancaria.
---

# Contador Público Colegiado en Venezuela (`venezuela-tax-cpa`)

Skill de auditoría técnica, contable y tributaria enfocada exclusivamente en **operadores y comerciantes P2P de criptoactivos en Venezuela** (Binance P2P + banca nacional), para garantizar que los cálculos, la conciliación bancaria, el cierre de caja y los papeles de trabajo exportados cumplan la normativa venezolana vigente antes de entregarlos al contador público o ante una revisión del SENIAT.

> **Alcance depurado**: Este skill cubre únicamente los tributos y soportes que inciden en la compraventa P2P de criptoactivos y cuentas bancarias en Venezuela (**ISLR**, **IGTF**, **IVA en comisiones/intermediación**, **SPE** y **conciliación bancaria SUDEBAN–SENIAT**). Excluye obligaciones ajenas a esta operativa (nómina, parafiscales laborales o trámites SUNACRIP inactivos para personas naturales) y descarta mitos virales sin sustento legal (no existe impuesto especial al P2P ni umbral legal en USDT).

---

## Marco Legal y Parámetros Oficiales Vigentes (2026)

Consultar detalle normativo completo y citas de Gaceta Oficial en [references/normativa-venezuela.md](references/normativa-venezuela.md). Reglas operativas obligatorias:

1. **Principio de Enriquecimiento Neto e ISLR (LISLR Art. 1, 4, 27, 50, 52)**:
   - El **ISLR grava únicamente la ganancia neta realizada**:
     `Ingresos Brutos por Ventas (VES) − Costo de Adquisición (PEPS o Costo Promedio) − Comisiones Deducibles Verificables (Exchange + Bancarias en VES)`.
   - **PROHIBIDO** confundir volumen rotado o entradas bancarias (`1.1.01`) con ingresos brutos o enriquecimiento neto gravable.
   - **Unidad Tributaria vigente**: **Bs. 43,00** (`Providencia SNAT/2025/000048`, G.O. N° 43.140 — uso exclusivo tributos nacionales SENIAT).
   - **Umbrales de declaración obligatoria ISLR (Persona Natural residente)**: enriquecimiento neto anual **> 1.000 UT (Bs. 43.000,00)** o ingresos brutos anuales **> 1.500 UT (Bs. 64.500,00)**; desgravamen único de **774 UT (Bs. 33.282,00)**; plazo habitual hasta el **31 de marzo** del año siguiente.
   - **Formularios electrónicos vigentes en `www.seniat.gob.ve`**:
     - **Forma DPN-99025**: Declaración Definitiva Electrónica de ISLR — **Persona Natural** *(las planillas físicas DPN-25/IPOSTEL están en desuso operativo)*.
     - **Forma DPJ-99026**: Declaración Definitiva Electrónica de ISLR — **Persona Jurídica** *(no confundir con planilla de pago)*.
     - **AR-C**: Comprobante de retención de ISLR *(solo cuando el contribuyente además percibió sueldos o servicios con retención)*.
   - **Guardia contra ganancia ficticia por inventario faltante**: Si una venta `SELL` consume más USDT que el inventario disponible (`initial_inventory + compras`), **nunca** silenciosamente valorar ese faltante a costo `0,00 Bs.` sin advertencia explícita; exigir/arrastrar el saldo inicial y costo de apertura del período.

2. **Control de Inventario de Criptoactivos (Reglamento LISLR Art. 177 y BA VEN-NIF N° 12)**:
   - Los criptoactivos propios **no son efectivo ni equivalentes de efectivo** (`BA VEN-NIF N° 12`, FCCPV); deben presentarse separados de `Bancos Nacionales (VES)` en el Balance General.
   - Todo cierre debe cuadrar el **Kardex** tanto en unidades (**USDT**) como al costo en moneda funcional (**VES**):
     `Saldo Inicial + Compras P2P + Depósitos/Pay − Ventas P2P − Retiros/Pay − Comisiones Cripto = Saldo Final Teórico`.
   - Excluir estrictamente órdenes `CANCELLED` / `CANCELLED_BY_SYSTEM` / `EXPIRED` de inventario, volumen, utilidad y conciliación.

3. **Moneda Funcional, Tasa Oficial BCV y Hora Legal VET (`UTC-4`)**:
   - Toda cifra tributaria y libro contable ante el SENIAT se expresa en **Bolívares (VES)**; el contravalor referencial en USD usa **exclusivamente la tasa oficial del BCV** correspondiente a la fecha de la operación (jamás dividir por `1.0` como fallback silencioso ni usar tasa paralela como base tributaria).
   - Toda fecha de corte, agrupación mensual, Libro Diario, Kardex y archivo exportado (Excel, PDF, CSV, Google Sheets) debe usar **Hora Legal de Venezuela (`VET = UTC-4`, `America/Caracas`)**.

4. **Sujetos Pasivos Especiales (`SNAT/2026/00099`, G.O. N° 43.485) y Cruce Bancario SENIAT–SUDEBAN**:
   - Vigente desde el **1 de noviembre de 2026** (deroga `SNAT/2023/00005`). Unifica umbrales de calificación SPE para personas naturales y jurídicas usando el **TCMV** (Tipo de Cambio Oficial de la Moneda de Mayor Valor publicada por el BCV):
     - **Gerencias Regionales (Interior)**: ingresos brutos anuales **≥ 600.000 × TCMV** (últimas 2 declaraciones ISLR) o ventas mensuales **> 50.000 × TCMV** (últimas 3 declaraciones IVA).
     - **Región Capital**: ingresos brutos anuales **≥ 3.000.000 × TCMV** o ventas mensuales **> 250.000 × TCMV**.
     - **Exclusiones expresas**: nuevos emprendimientos inscritos en el **RNE** (primeros 3 años), sujetos con `< 1 año` de operación y actividades agrícolas/primarias específicas.
   - **Cruce automatizado SENIAT–SUDEBAN y Resolución SUDEBAN N° 377.07 (G.O. N° 38.820)**: El secreto bancario no es oponible al SENIAT (COT). Conservar los **estados de cuenta bancarios mensuales** conciliados contra el historial Binance P2P (`Banco`, `Referencia`, `Fecha VET`, `Monto`, `Titular / Cédula-RIF`) es indispensable para demostrar que el volumen bancario es **capital de trabajo rotativo** y evitar recalificaciones erróneas como SPE o bloqueos bancarios (evitar pagos de terceros).

5. **IGTF (Decreto N° 4.972, G.O. Ext. N° 6.821) e IVA / Facturación Digital (`SNAT/2026/00093`)**:
   - **IGTF**: Alícuota del **0%** para operaciones liquidadas en **Bolívares** por SPE (sin pago efectivo) y **3%** para pagos en divisas o criptoactivos distintos al soberano realizados ante/por SPE. Jamás mezclar IGTF con la base imponible de **IVA (16%)**.
   - **Facturación Digital (`SNAT/2024/000102`, `SNAT/2026/00084` que derogó `000121`, y `SNAT/2026/00093`, G.O. N° 43.484)**: Aplica solo a quienes facturan comercialmente bienes o servicios/comisiones de intermediación gravados con IVA. No existe una "factura P2P" obligatoria para compraventa por cuenta propia; el soporte legal es el **Papel de Trabajo Contable** + historial Binance + estados de cuenta bancarios.

6. **Integridad Formal de Exportes, Papeles de Trabajo y UX Sin Saturación**:
   - **Leyenda obligatoria de Papel de Trabajo**: Todo Excel/PDF fiscal debe declarar expresamente: *"Papel de trabajo contable e insumo para Declaración ISLR (Forma DPN-99025 PN / DPJ-99026 PJ). No sustituye la declaración oficial ante el SENIAT ni el dictamen de un Contador Público Colegiado (CPC)."*
   - **Partida Doble y Completitud**: Libro Diario con `SUM(Debe) == SUM(Haber)` (**Sumas Iguales**); PDF multipágina completo (jamás truncar asientos); referencias bancarias, cédulas/RIF y números de orden largos formateados como **texto (`@`)** para evitar pérdida de ceros o notación científica (`2.026E+19`), y montos VES con `#,##0.00`.
   - **Separación Operador vs Contador**: La interfaz diaria del comerciante debe enfocarse en un **Cierre de Caja claro** (Apertura, Entradas/Salidas, Arqueo Real vs Teórico, Ganancia Neta y descarga en 1 clic), manteniendo el detalle técnico contable (Libro Diario, Mayor, códigos de cuenta y hashes) en los archivos exportables y en una vista secundaria colapsable para el contador.

---

## Protocolo Obligatorio de Revisión (Checklist CPC)

Ejecutar **siempre** tras modificar `src/reporting/*`, `src/core/binance_history_syncer.py`, `src/integrations/statement_importer.py`, `src/api/routes/accounting.py`, `src/api/routes/fiscal.py` o `src/api/routes/orders.py`:

### Paso 1 — Verificar Base Imponible, Inventario y Conciliación
- Confirmar que ninguna cifra de ISLR derive ingresos o ganancia desde flujo bancario (`1.1.01`).
- Confirmar coherencia entre saldo teórico USDT (considerando `fee_crypto`), costo de ventas (`PEPS` o `Promedio` con inventario inicial) y deducción completa de comisiones (`Binance` + `Bancarias 5.2.01`) sin doble conteo ni omisiones.
- Confirmar exclusión estricta de órdenes `CANCELLED` / `EXPIRED` y verificación de sentido bancario (`DEBIT → BUY`, `CREDIT → SELL`).

### Paso 2 — Auditar Huso Horario VET y Tasas Oficiales BCV
- Confirmar que toda fecha de consulta, corte mensual, visualización y exportación (Excel, PDF, CSV, Sheets) use `VET (UTC-4)` y nunca `UTC` sin convertir.
- Confirmar que los equivalentes en USD usen exclusivamente `bcv_rate > 0` oficial (nunca fallback `1.0`).

### Paso 3 — Auditar Formatos de Exportación y Cumplimiento Formal
- **Excel Contable (`.xlsx`)**: Verificar leyenda *"Papel de trabajo — DPN-99025 / DPJ-99026"*, pestañas completas (Resumen/Liquidación SENIAT, Estado de Resultados, Balance General VEN-NIF 12, Kardex USDT, Conciliación Bancaria, Libro Diario con Sumas Iguales, Libro Mayor), columnas largas en texto `@` y montos `#,##0.00`.
- **PDF Contable (`.pdf`)**: Verificar multipágina sin truncar, titular/RIF/período, hora VET, tasa BCV, precisión legal IGTF (`0%` en VES por Decreto 4.972), Sumas Iguales y bloque de firmas.
- **Órdenes (`.xlsx` / `.csv`) y Google Sheets**: Verificar fecha `VET`, `Banco / Método de Pago`, `Tasa BCV`, `Equivalente USD (BCV)` y ausencia de columnas técnicas ruidosas bloqueando al usuario.

### Paso 4 — Reportar Dictamen CPC
Al finalizar cambios contables o fiscales, incluir un resumen conciso bajo `### Auditoría Contable Venezuela (venezuela-tax-cpa)` indicando:
1. Validación de cálculo de base imponible (PEPS/Promedio, comisiones e inventario inicial).
2. Verificación de hora VET, tasa BCV, formatos de archivo, Sumas Iguales y leyenda de papel de trabajo.
3. Cualquier brecha normativa o alerta de umbral (ISLR `1.000/1.500 UT`, SPE `SNAT/2026/00099` en `TCMV`, o Persona Natural vs Jurídica).
