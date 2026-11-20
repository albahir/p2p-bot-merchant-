---
name: venezuela-tax-cpa
description: Auditoría contable y tributaria bajo normativa venezolana (SENIAT, LISLR, LIVA, LIGTF, BCV, BA VEN-NIF N° 12). Obligatorio invocar y ejecutar ante modificaciones en cálculo fiscal, tasas BCV, motor contable, exportaciones Excel/PDF/CSV/Sheets o conciliación bancaria.
---

# Contador Público Colegiado en Venezuela (`venezuela-tax-cpa`)

Skill de revisión técnica, contable y tributaria para garantizar que los cálculos, registros en partida doble y archivos exportados cumplan con la normativa venezolana vigente antes de entregarlos al contribuyente o a un fiscal del SENIAT.

## Marco Legal y Contable Obligatorio

Consultar detalle normativo completo en [references/normativa-venezuela.md](references/normativa-venezuela.md). Resumen de reglas operativas:

1. **Principio de Enriquecimiento Neto (LISLR Art. 1, 4, 27)**:
   - El **ISLR grava la utilidad real realizada**: `Ingresos por Ventas (VES) - Costo de Adquisición (PEPS o Costo Promedio) - Gastos/Comisiones Deducibles (VES)`.
   - **PROHIBIDO** confundir flujo de efectivo bancario (`Entradas - Salidas` de la cuenta Banco `1.1.01`) con ingresos brutos o utilidad fiscal gravable. El volumen rotado en arbitraje P2P no es ganancia.
2. **Control de Inventario de Criptoactivos (Reglamento LISLR Art. 177 y BA VEN-NIF N° 12)**:
   - Los criptoactivos propios no son efectivo ni equivalentes de efectivo (`BA VEN-NIF N° 12`, FCCPV).
   - Todo cierre mensual/anual debe demostrar la ecuación de inventario tanto en unidades cripto (**USDT**) como en moneda funcional (**VES**):
     `Inventario Inicial + Compras - Costo de Ventas (PEPS/Promedio) = Inventario Final`.
3. **Moneda Funcional y Tasa Oficial BCV**:
   - Toda obligación tributaria y contabilidad formal ante el SENIAT debe expresarse en **Bolívares (VES)** y utilizar la **tasa oficial del BCV** para contravalor en divisas, sin mezclar tasa paralela/P2P como referencia legal tributaria.
4. **Hora Legal de Venezuela (`VET = UTC-4`)**:
   - Todo reporte fiscal, corte mensual de órdenes P2P, Libro Diario, Mayor y cierre contable debe convertirse y mostrarse en **hora de Venezuela (UTC-4)**. Un cierre hecho a las 21:00 VET de fin de mes corresponde al mes venezolano vigente, nunca al mes siguiente en UTC.
5. **IGTF y Cruce Bancario SUDEBAN–SENIAT (LIGTF, Decreto 4.972, Providencia SNAT/2026/00099)**:
   - Documentar de forma separada las operaciones liquidadas íntegramente en Bolívares vía banca nacional (no sujetas al 3% de pagos en divisas en comercios SPE) de cualquier pago directo en cripto/divisas a Sujetos Pasivos Especiales (**3% IGTF**, jamás mezclado con base imponible de IVA).
   - Mantener trazabilidad de titularidad bancaria (`Banco`, `Referencia`, `Cédula/RIF`) para defender origen lícito y separar capital de trabajo vs ganancia ante revisiones por **Providencia SNAT/2026/00099**.
6. **Integridad Formal de Libros y Exportes (COT, Código de Comercio, Providencia SNAT/2011/00071)**:
   - **Partida Doble y Sumas Iguales**: Todo Libro Diario y Mayor debe cerrar con `SUM(Debe) == SUM(Haber)` al pie del documento.
   - **Completitud de PDF**: Prohibido truncar asientos (ej. limitar a `[:15]`). Un reporte PDF legal debe paginar automáticamente la totalidad de los asientos del período con encabezado repetido (Titular/Razón Social, RIF, Período) y totales de cierre.
   - **Formatos numéricos y de texto en Excel/CSV**: Referencias bancarias, cédulas/RIF y números de orden largos deben exportarse como texto (para preservar ceros iniciales y evitar notación científica `2.026E+19`), y los montos en moneda nacional con 2 decimales (`#,##0.00`).

---

## Protocolo Obligatorio de Revisión (Checklist CPC)

Ejecutar **siempre** tras modificar `src/reporting/*`, `src/core/binance_history_syncer.py`, `src/api/routes/accounting.py`, `src/api/routes/fiscal.py` o `src/api/routes/orders.py`:

### Paso 1 — Verificar Base Imponible y Fórmulas Fiscales
- Confirmar que ninguna liquidación fiscal ni resumen ISLR derive ingresos o ganancia neta desde flujos bancarios (`1.1.01`).
- Confirmar deducción separada de comisiones verificables (`Binance fee` + `Comisión bancaria`).
- Confirmar existencia de tabla o sección de Kardex / Inventario (`Inicial + Compras - Costo de Ventas = Final`).

### Paso 2 — Auditar Huso Horario y Tasas Oficiales
- Confirmar que las fechas impresas en reportes legales de órdenes, diario y PDF/Excel usen `UTC-4` (`VET`, `America/Caracas`).
- Confirmar que los valores referenciales en USD utilicen exclusivamente `bcv_rate` oficial.

### Paso 3 — Auditar Integridad y Presentación de Archivos Exportados
- **Excel (`.xlsx`)**: Verificar pestañas obligatorias (`Resumen / Estado de Resultados / Liquidación Fiscal SENIAT`, `Libro Diario`, `Libro Mayor`, `Kardex Inventario USDT`, `Conciliación Bancaria`), presencia de fila de **Sumas Iguales** en Diario y ausencia de columnas técnicas ruidosas bloqueando la vista contable principal (hashes técnicos pueden ir al final o en pestaña de auditoría).
- **PDF (`.pdf`)**: Verificar **multipágina** (sin recorte arbitrario de asientos), presencia de titular/RIF/período, hora VET, estado de resultados fiscal real (PEPS) y **Sumas Iguales**.
- **Órdenes (`.xlsx` / `.csv`)**: Verificar inclusión de `Tasa BCV`, `Equivalente USD (BCV)` y fecha `VET (UTC-4)`.

### Paso 4 — Reportar Dictamen CPC
Al finalizar cambios contables o fiscales, incluir un breve resumen bajo `### Auditoría Contable Venezuela (venezuela-tax-cpa)` indicando:
1. Validación de cálculo de base imponible (PEPS/Promedio vs flujo de caja).
2. Verificación de formato, hora VET, tasa BCV, Sumas Iguales y completitud multipágina.
3. Cualquier brecha normativa o limitación pendiente según el tipo de contribuyente (Persona Natural vs Jurídica / Sujeto Pasivo Especial / IVA).
