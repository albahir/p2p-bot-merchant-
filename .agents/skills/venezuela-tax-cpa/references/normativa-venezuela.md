# Marco Normativo Venezolano para Comercio P2P y Criptoactivos (Actualizado Nov 2026)

Referencia técnica y legal verificada para contabilidad, conciliación bancaria y cumplimiento tributario de comerciantes P2P en Venezuela.

---

## 1. Impuesto Sobre la Renta (LISLR y Reglamento)

- **Base legal**: Ley de Impuesto Sobre la Renta (LISLR, Arts. 1, 4, 27, 50, 52) y Reglamento de la LISLR (Art. 177).
- **Hecho imponible**: Grava exclusivamente el **enriquecimiento neto** anual disponible y territorial:
  `Ingresos Brutos por Ventas (VES) − Costo de Adquisición (PEPS o Costo Promedio) − Gastos/Comisiones Deducibles (VES)`.
- **Unidad Tributaria (UT) vigente**: **Bs. 43,00** según **Providencia Administrativa N° SNAT/2025/000048** (*Gaceta Oficial N° 43.140*). Su aplicación es restrictiva para tributos nacionales administrados por el SENIAT (para ISLR anual se aplica la UT vigente al cierre del ejercicio fiscal).
- **Umbrales de declaración obligatoria (Persona Natural residente)**:
  - Enriquecimiento global neto anual superior a **1.000 UT** (**Bs. 43.000,00**), **o**
  - Ingresos brutos anuales superiores a **1.500 UT** (**Bs. 64.500,00**).
  - **Desgravamen único**: **774 UT** (**Bs. 33.282,00**) para personas naturales residentes que no opten por desgravámenes detallados.
  - **Plazo ordinario**: Hasta el **31 de marzo** del año calendario siguiente al cierre del ejercicio fiscal.
  - *Aclaración sobre el mito de "40 USDT mensuales"*: No existe ninguna norma que fije un umbral en USDT. Esa cifra provino de cálculos periodísticos aproximados dividiendo `1.500 UT (Bs. 64.500)` entre 12 meses y una tasa referencial; legalmente el parámetro se mide siempre en **UT / Bolívares**.
- **Formularios electrónicos vigentes en el portal `www.seniat.gob.ve`**:
  - **Forma DPN-99025**: Declaración Definitiva Electrónica de ISLR para **Personas Naturales** *(las planillas impresas DPN-25 / DPN-R-25 en taquillas IPOSTEL quedaron en desuso operativo)*.
  - **Forma DPJ-99026**: Declaración Definitiva Electrónica de ISLR para **Personas Jurídicas** *(no es una planilla de pago de persona natural)*.
  - **Compromiso de Pago electrónico**: Generado automáticamente por el portal del SENIAT cuando la declaración arroja impuesto a pagar.
  - **Comprobante AR-C**: Emitido por agentes de retención de ISLR únicamente si el contribuyente percibió sueldos, honorarios o servicios sujetos a retención.
- **Control de Inventarios (Art. 177 Reglamento LISLR)**: Exige registro cronológico de entradas, salidas y existencias al cierre con método consistente (**PEPS/FIFO** o **Costo Promedio Ponderado**). En comercio P2P de *stablecoins* (USDT), cada compra completada entra al costo real en bolívares y cada venta descarga costo según el método adoptado.
- **Error típico prohibido**: Calcular ingresos gravables o utilidad restando salidas bancarias de entradas bancarias (`1.1.01`) o asignar costo `0,00 Bs.` a ventas de inventario previo sin registrar saldo inicial.

---

## 2. Principios Contables Venezolanos — BA VEN-NIF N° 12 (FCCPV)

- Boletín de Aplicación **BA VEN-NIF N° 12** (*Tenencia de Criptoactivos Propios*, Federación de Colegios de Contadores Públicos de Venezuela):
  - Los criptoactivos propios **no son efectivo ni equivalentes de efectivo** ni instrumentos financieros tradicionales; deben presentarse en rubro separado del efectivo en bancos (`1.1.05` vs `1.1.01`).
  - Reconocimiento inicial al costo de adquisición expresado en moneda funcional (**Bolívares — VES**), utilizando **tasas oficiales del Banco Central de Venezuela (BCV)** para todo contravalor referencial en divisas.
  - Separación estricta entre **ganancia realizada por enajenación** (gravable en ISLR) y variaciones no realizadas de inventario mantenido al cierre.

---

## 3. Sujetos Pasivos Especiales (Providencia SNAT/2026/00099 — G.O. N° 43.485)

- **Vigencia**: Dictada el 22 de octubre de 2026, publicada en **Gaceta Oficial N° 43.485**, vigente desde el **1 de noviembre de 2026** (deroga `SNAT/2023/00005`).
- **Naturaleza real**: **NO crea un impuesto especial sobre criptoactivos ni sobre comercio P2P**. Redefine los criterios económicos para calificar y controlar a los **Sujetos Pasivos Especiales (SPE)**, unificando los umbrales para personas naturales y jurídicas en múltiplos del **TCMV** (*Tipo de Cambio Oficial de la Moneda de Mayor Valor* publicada por el BCV):
  - **Gerencias Regionales de Tributos Internos (Interior)**:
    - Ingresos brutos anuales **≥ 600.000 × TCMV** (según las últimas 2 declaraciones de ISLR), **o**
    - Ventas o prestaciones de servicios mensuales **> 50.000 × TCMV** (según las últimas 3 declaraciones de IVA).
  - **Gerencia de Contribuyentes Especiales de la Región Capital**:
    - Ingresos brutos anuales **≥ 3.000.000 × TCMV**, **o**
    - Ventas o prestaciones de servicios mensuales **> 250.000 × TCMV**.
- **Exclusiones expresas**:
  - Nuevos emprendimientos inscritos en el **Registro Nacional de Emprendimiento (RNE)** durante sus primeros **3 años**.
  - Contribuyentes con **menos de 1 año** de inicio de operaciones (salvo sectores específicos como hidrocarburos o minería).
  - Determinadas actividades agrícolas primarias, forestales y pesqueras.
- **Consecuencias de ser calificado SPE** (siempre tras notificación formal / actualización de RIF en el portal del SENIAT): calendario especial de declaraciones y pagos electrónicos, obligación de anticipos (ISLR/IVA según aplique) y rol de agente de retención de IVA / percepción de IGTF.

---

## 4. Cruce Bancario SENIAT–SUDEBAN y Soporte Bancario (Resolución SUDEBAN N° 377.07)

- **Resolución SUDEBAN N° 377.07** (*Gaceta Oficial N° 38.820*): Obliga a las instituciones bancarias a emitir estados de cuenta mensuales detallados a sus clientes.
- **Convenio Marco de Interconexión SENIAT–SUDEBAN (2026)** y **Código Orgánico Tributario (COT)**: El secreto bancario no es oponible al SENIAT; el intercambio automatizado permite contrastar flujos de Pago Móvil y transferencias en cuentas personales y jurídicas contra las declaraciones fiscales.
- **Por qué los estados de cuenta bancarios son obligatorios en P2P**:
  1. **Defensa fiscal**: Permiten probar que los millones de bolívares movilizados en cuentas bancarias son **rotación del mismo capital de trabajo** y no ingresos brutos ni utilidades multiplicadas, evitando recalificaciones erróneas como SPE o determinaciones presuntivas de ISLR.
  2. **Soporte de deducciones**: Respaldan las comisiones bancarias deducibles (ej. `0,30%` Pago Móvil / transferencias interbancarias, cuenta `5.2.01`).
  3. **Prevención de bloqueos bancarios (legitimación de capitales)**: Operar únicamente con titulares coincidentes con la orden Binance (nunca pagos de terceros) y conservar la traza `Banco + Referencia + Cédula/RIF + Orden P2P` en **Hora Legal de Venezuela (`VET = UTC-4`)**.

---

## 5. IGTF (Ley de IGTF — Decreto Presidencial N° 4.972)

- **Decreto N° 4.972** (*Gaceta Oficial Extraordinaria N° 6.821*, vigente desde el 15 de julio de 2024 y aplicable en 2026):
  - **Bolívares (VES)**: Fija la alícuota en **0%** para operaciones en moneda nacional realizadas por Sujetos Pasivos Especiales (sin pago efectivo al fisco; jurídicamente es alícuota 0%, no exención formal).
  - **Divisas y Criptoactivos (USDT, BTC, etc.)**: Mantiene vigente la alícuota del **3%** sobre pagos en moneda extranjera o criptoactivos distintos a los emitidos por la República cuando intervienen Sujetos Pasivos Especiales / agentes de percepción.
- **Separación contable obligatoria**: Documentar que las operaciones P2P liquidadas 100% en Bolívares vía banca nacional no están sujetas al 3%, y jamás mezclar IGTF con la base imponible de **IVA (16%)**.

---

## 6. IVA y Facturación Digital (Evolución 2024–2026)

- **Régimen general y facturación digital**:
  - **Providencia SNAT/2011/00071**: Normas generales de emisión de facturas y Libros de Compras/Ventas (fecha, RIF, N° factura, N° control, base imponible, alícuota, retenciones).
  - **Providencia SNAT/2024/000102** (G.O. N° 43.032): Facturación digital mediante Imprentas Digitales Autorizadas (resguardo de trazabilidad por 10 años) para quienes venden bienes o prestan servicios exclusivamente por medios electrónicos.
  - **Providencia SNAT/2026/00084** (ago 2026): Derogó la obligatoriedad de software homologado exclusivo (`SNAT/2024/000121`).
  - **Providencia SNAT/2026/00093** (G.O. N° 43.484, oct 2026): Flexibiliza la elección entre medios digitales/electrónicos y máquinas fiscales.
- **Aplicación en P2P**: La compraventa de criptoactivos por cuenta propia distingue claramente entre el **principal intercambiado** (regido por inventario/costo y ganancia en ISLR) y eventuales **comisiones facturadas por servicios de intermediación a terceros** (las cuales sí requerirían facturación formal y tratamiento de IVA si el comerciante presta servicios facturables).

---

## 7. Expediente de Respaldo y Papel de Trabajo (Orden Cronológico)

Para cerrar un período mensual o anual y entregarlo al Contador Público Colegiado (CPC) o tenerlo listo ante fiscalización del SENIAT, el sistema debe producir y conservar en este orden:

1. **Insumos primarios**:
   - Historial de órdenes completadas de Binance P2P (API hasta 180 días o `.csv`/`.xlsx` anual para 365+ días) + movimientos Binance Pay / Depósitos / Retiros.
   - Estados de cuenta bancarios mensuales en PDF/Excel/CSV emitidos por cada banco (`Res. SUDEBAN 377.07`).
2. **Conciliación y Cierre de Caja**:
   - Cruce 1-a-1 de órdenes completadas contra movimientos bancarios (`DEBIT → BUY`, `CREDIT → SELL`), clasificación de comisiones bancarias (`5.2.01`) y traspasos propios (`3.1.01`), y arqueo de cierre (Saldo Teórico vs Saldo Real en Bancos y Binance).
3. **Papel de Trabajo Contable y Fiscal (Excel `.xlsx` + PDF `.pdf`)**:
   - Debe portar la leyenda expresa: *"Papel de trabajo contable e insumo para Declaración ISLR (Forma DPN-99025 PN / DPJ-99026 PJ). No sustituye la declaración oficial ante el SENIAT ni el dictamen de un Contador Público Colegiado."*
   - Incluye: Resumen Ejecutivo / Liquidación SENIAT, Estado de Resultados (PEPS o Promedio), Balance General `BA VEN-NIF 12`, Kardex USDT (`Art. 177 Rgto. LISLR`), Conciliación Bancaria, Libro Diario con **Sumas Iguales** y Libro Mayor.
4. **Declaración Oficial (fuera del sistema, en `www.seniat.gob.ve`)**:
   - El contribuyente o su contador carga las cifras definitivas del papel de trabajo en el portal del SENIAT para emitir la **Forma DPN-99025** (PN) o **DPJ-99026** (PJ) y archiva el certificado electrónico junto con el expediente de respaldo (plazo de resguardo tributario: **6 a 10 años** según COT/normativa vigente).
