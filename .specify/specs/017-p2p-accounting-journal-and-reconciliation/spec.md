# SPEC-017: Sistema Contable P2P — Libro Diario, Libro Mayor, Conciliación Multi-Factorial y Régimen Histórico BCV

## 1. Contexto y Justificación
En el comercio P2P de criptoactivos en Venezuela, Binance no proporciona la cédula de identidad ni el nombre legal de las contrapartes, operando con seudónimos comerciales. Ante la administración tributaria (SENIAT) y las instituciones financieras, el comprobante bancario (capture de Pago Móvil o Transferencia) constituye el soporte probatorio legal primario.

Esta especificación formaliza la arquitectura contable de partida doble, diferenciación entre Pago Móvil y Transferencias bancarias, mitigación de falsos positivos en conciliación, corrección del régimen de Fecha Valor del BCV, auto-población de tasas históricas para extractos de 6 meses, y exportación de Libro Diario y Libro Mayor en Excel y PDF.

---

## 2. Requerimientos Funcionales (RF)

### RF-01: Modelo de Datos Contable Enriquecido
- `BankVoucher` debe almacenar: banco emisor, banco destino, referencia bancaria, monto neto en bolívares, comisión bancaria debitada, monto total debitado, cédula/RIF (`S/C` si es transferencia sin cédula), teléfono (`N/A` si es transferencia), concepto/motivo del pago, fecha/hora exacta, método de pago (`PAGO_MOVIL` | `TRANSFERENCIA`), tipo de movimiento (`DEBIT` | `CREDIT`) y orden P2P asociada.
- `Order` debe almacenar `completed_at` (timestamp de finalización) y `payment_method` (banco o método de pago reportado por Binance).
- Crear modelo `BCVRateHistory` indexado por `fecha_valor` (Date) para almacenar la serie histórica oficial.
- Crear modelo `JournalEntry` para asentar cada movimiento del Libro Diario con partida doble inmutable (hash encadenado SHA-256).

### RF-02: Régimen Estricto de Fecha Valor BCV
- Las tasas oficiales del BCV deben registrarse por su `fecha_valor` legal.
- La publicación vespertina del BCV (3:00 PM a 6:00 PM UTC-4) que posee Fecha Valor del día hábil siguiente **no debe aplicarse a transacciones del día en curso**.
- Toda operación en fecha $D$ se liquida a la tasa con `fecha_valor == D`. En fines de semana o feriados bancarios, se aplica la tasa del último día hábil anterior (viernes).
- Auto-población retroactiva masiva: para archivos de 6 meses de Binance (donde la tasa viene vacía), el sistema debe consultar la tabla histórica y asignar automáticamente la tasa legal de cada fecha.

### RF-03: Extractor OCR Multimodal Adaptativo (Gemini Vision)
- Detectar automáticamente si el comprobante es Pago Móvil o Transferencia bancaria.
- Extraer concepto/motivo del capture y comisiones explícitas.
- Auto-calcular comisiones bancarias cuando no vengan detalladas:
  - Mismo banco: `0.00 VES` (gratis).
  - Interbancario emitido (compras USDT): aplicar tarifa regulada Sudeban/BCV (`0.30%`).
  - Interbancario recibido (ventas USDT): `0.00 VES` (el receptor recibe el 100% íntegro).

### RF-04: Motor de Conciliación Multi-Factorial con Score (0 a 100%)
- Descarte inmediato (0%) si no coincide la dirección de flujo (`DEBIT == BUY`, `CREDIT == SELL`) o si la fecha excede la ventana de la orden ($\pm 15$ minutos para inmediatas, 24-48h para transferencias ACH).
- Puntuación ponderada: Monto exacto con céntimos (30%), Banco/Método (30%), Referencia en chat/confirmación (40%), Titular (Bonus 15%).
- Niveles de decisión:
  - 🟢 Score $\ge 90\%$: Conciliación automática.
  - 🟡 Score $60\% - 89\%$: Sugerencia asistida en UI/Telegram con 1 clic (`Vincular` / `Rechazar`).
  - ⚪ Score $< 60\%$: Asiento independiente en Libro Diario (cero falsos positivos).

### RF-05: Libro Diario y Libro Mayor
- **Libro Diario**: Cronológico, con partida doble formal (Total Debe = Total Haber), asiento por asiento con desglose de Cédula, Teléfono, Concepto, Referencia y Comisiones bancarias.
- **Libro Mayor**: Consolidación mensual por cuentas (`1.1.01 Banco VES`, `1.1.05 Activos USDT`, `5.2.01 Comisiones Bancarias`, `5.1.02 Comisiones Binance`).
- Mostrar explícitamente:
  - **Saldo Inicial del mes**.
  - **Movimientos del período**.
  - **Saldo Final del mes**.
  - Encadenamiento patrimonial (Saldo Final mes $N$ = Saldo Inicial mes $N+1$).

### RF-06: Exportación Dual (Excel y PDF) y Sincronización Google Sheets
- Generación de archivo Excel (.xlsx) con 4 pestañas: *Libro Diario*, *Libro Mayor*, *Conciliación Bancaria*, *Liquidación Fiscal SENIAT*.
- Generación de informe formal en PDF listo para impresión fiscal con membrete y saldos.
- Sincronización en vivo con Google Sheets vía `gspread`.

---

## 3. Requerimientos No Funcionales (RNF)
- **Trazabilidad & Cero Falsos Positivos**: Ningún comprobante dudoso debe forzarse contra una orden.
- **Seguridad**: Prohibido registrar o exponer secretos bancarios o claves privadas en logs o respuestas.
- **TDD Riguroso**: Cobertura con pruebas unitarias para cada normalizador, regla de Fecha Valor y cuadre contable.
