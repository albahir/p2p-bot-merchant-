# Reglas Contables y Fiscales para Comerciantes P2P en Venezuela

Este documento define la normativa técnica, fiscal y de auditoría contable para la declaración y reconstrucción de la actividad comercial P2P en Binance dentro del marco legal y cambiario de Venezuela.

---

## 1. Los Tres Reportes Base de Binance (My Tax Hub / SUMM)

Para una declaración y reconstrucción contable fidedigna, el sistema debe consolidar o auditar tres flujos independientes de datos proporcionados por la API y los informes oficiales de Binance:

### A. Historial de Transacciones (Transaction History)
Utilizado para auditar los cambios en el inventario de criptoactivos:
* **Campos obligatorios**: Fecha y hora (UTC/Local), tipo de operación, activo/moneda, cantidad, precio/valor equivalente, comisión, estado, ID de transacción o referencia.
* **Clasificación contable**:
  - Compras P2P (`BUY`).
  - Ventas P2P (`SELL`).
  - Conversiones directas de inventario (`/sapi/v1/convert/tradeFlow`).
  - Recompensas, airdrops y comisiones devueltas (`/sapi/v1/asset/assetDividend`).
  - Transferencias internas entre billeteras (Spot, Funding/Fondos, Futuros).

### B. Historial de Depósitos (Deposit History)
Evidencia formal de entradas externas de inventario cripto y fondos:
* **Campos obligatorios**: Fecha y hora, activo/cripto, monto bruto, red blockchain utilizada (ej. TRC20, BSC, Polygon), estado de confirmación, TXID / Hash en cadena / Referencia.
* **Endpoint API Oficial**: `GET /sapi/v1/capital/deposit/hisrec` (`USER_DATA`, requiere firma Ed25519/HMAC).

### C. Historial de Retiros (Withdrawal History)
Evidencia formal de salidas externas de fondos y transferencias a contrapartes o billeteras frías:
* **Campos obligatorios**: Fecha y hora, activo/cripto, monto solicitado, comisión de red deducida, monto neto transferido, red blockchain, estado, TXID / Hash en cadena.
* **Endpoint API Oficial**: `GET /sapi/v1/capital/withdraw/history` (`USER_DATA`, requiere firma Ed25519/HMAC).

---

## 2. Las Seis Piezas de la Reconstrucción Contable P2P

Para estructurar la declaración de ingresos brutos, costos de adquisición y renta neta gravable (ISLR) de un comerciante P2P, el motor fiscal debe construir:

1. **Saldo Inicial del Período**: Inventario de criptoactivos disponible al minuto `00:00:00` del primer día del mes/año fiscal.
2. **Entradas de Cripto (Inflows)**: Sumatoria de depósitos externos + compras P2P completadas + transferencias entrantes + conversiones recibidas.
3. **Salidas de Cripto (Outflows)**: Sumatoria de retiros externos + ventas P2P completadas + transferencias salientes + conversiones entregadas.
4. **Volumen Operado**: Agregado transaccional total por criptoactivo (ej. USDT comprados vs. USDT vendidos).
5. **Costos y Comisiones Visibles**: Registro discriminado de comisiones de plataforma Binance (maker/taker fees) y comisiones de red blockchain.
6. **Saldo Final del Período y Ecuación de Consistencia**:
   $$\text{Saldo Inicial} + \text{Entradas} - \text{Salidas} = \text{Saldo Final Esperado}$$
   Cualquier discrepancia entre el saldo final calculado y el balance real en Binance (`/sapi/v1/asset/wallet/balance`) debe alertar al operador por posibles comisiones no registradas o mermas operativas.

---

## 3. Conciliación con la Capa Externa Fiat / Bancaria en Venezuela

Binance audita el movimiento cripto en custodia, pero **no registra los soportes bancarios en bolívares (VES)**. Por normativa fiscal y bancaria en Venezuela (SUDEBAN / SENIAT), el comerciante debe cruzar la información con:

* **Soportes Bancarios en VES**: Comprobantes de transferencias y Pago Móvil (número de referencia bancaria, banco emisor/receptor, titular y cédula/RIF de la contraparte).
* **Tasa Oficial de Valoración (BCV)**: Toda operación en moneda extranjera o criptoactivos debe convertirse a bolívares según la tasa de cambio oficial del Banco Central de Venezuela (`bcv.org.ve`) a la fecha de la transacción para el cálculo de ingresos brutos y costo fiscal (FIFO / Costo Promedio Ponderado).
* **Control de Spread y Ganancia Cambiaria**: Discriminación entre el precio pactado en el libro P2P (VES/USDT) y la tasa oficial BCV.
* **Gastos Operativos Deducibles**: Comisiones bancarias, IGTF, gastos de servidor/infraestructura e impuestos municipales si aplica.

---

## 4. Políticas de Descarga, Archivo y Resiliencia de API

* **Ventanas de Paginación en API**:
  - Histórico P2P (`/sapi/v1/c2c/orderMatch/listUserOrderHistory`): Ventana máxima de 30 días por petición.
  - Historial de Depósitos/Retiros (`deposit/hisrec`, `withdraw/history`): Ventana máxima de 90 días por petición.
* **Vigencia de Exportaciones Web**: Los enlaces de descarga generados manualmente desde el portal de Binance expiran a los 7 días. El bot debe almacenar de forma permanente y local los registros en SQLite/PostgreSQL.
* **Cero Secretos**: Prohibido registrar credenciales, números de tarjeta o identificadores sensibles de cuentas bancarias en texto plano no autorizado.

---

## 5. Referencias Oficiales de la API de Binance

* **Documentación Principal**: [Binance Developer Documentation](https://developers.binance.com/en/docs/introduction)
* **Catálogo Completo de Endpoints**: [Binance API Catalog](https://developers.binance.com/en/docs/catalog)
* **C2C Order Matching API**: `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory`
* **Capital Deposit History API**: `GET /sapi/v1/capital/deposit/hisrec`
* **Capital Withdraw History API**: `GET /sapi/v1/capital/withdraw/history`
* **Convert Trade Flow API**: `GET /sapi/v1/convert/tradeFlow`
* **Asset Dividend API**: `GET /sapi/v1/asset/assetDividend`
* **Wallet Balance API**: `GET /sapi/v1/asset/wallet/balance`
