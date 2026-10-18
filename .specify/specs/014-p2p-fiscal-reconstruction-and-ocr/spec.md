# Spec 014: Reconstrucción Contable P2P de 6 Piezas, Parser Binance y OCR Bancario con Gemini Vision

## 1. QUÉ (Objetivo del Paquete)
Construir un subsistema integral de reconstrucción contable y fiscal para comerciantes P2P en Venezuela, alineado con las regulaciones tributarias (SENIAT / ISLR / BCV) y los estándares de auditoría de Binance (My Tax Hub / SUMM).
El sistema procesa los reportes base de Binance (`.csv` y `.xlsx`), ejecuta la ecuación contable de 6 piezas, extrae comprobantes bancarios en bolívares mediante OCR inteligente con Google Gemini Vision (aprovechando el pool de 3 API Keys con round-robin), y consolida los reportes auditados en Excel (4 pestañas) y Google Sheets.

---

## 2. REQUISITOS FUNCIONALES

### RF-01: Ingesta y Parser Robusto de Archivos Binance (`.csv` y `.xlsx`)
- **RF-01.1**: Parsear el archivo de **Historial de Órdenes C2C** de Binance en español e inglés:
  - Encabezados: `Número de Pedido`, `Tipo de orden`, `Activo`, `Tipo de Fiat`, `Precio Total`, `Precio`, `Cantidad`, `Tarifa de creador`, `Comisión de tomador`, `Contraparte`, `Estado`, `Hora de creación`.
- **RF-01.2**: Parsear el archivo de **Historial de Depósitos**:
  - Encabezados: `Hora`, `Moneda`, `Red`, `Cantidad`, `Dirección`, `ID de transacción (TXID)`, `Estado`.
- **RF-01.3**: Parsear el archivo de **Historial de Retiros**:
  - Encabezados: `Hora`, `Moneda`, `Red`, `Cantidad`, `Tarifa`, `Dirección`, `ID de transacción (TXID)`, `Estado`.
- **RF-01.4**: Manejo automático de encabezados de metadatos en archivos `.xlsx`: Detección dinámica de la fila de cabecera saltando las filas informativas iniciales (`Nombre`, `ID de usuario`, `Período`).
- **RF-01.5**: Idempotencia total: Evitar duplicados de depósitos, retiros y órdenes ya registradas en la base de datos local.

### RF-02: Capa Bancaria en Bolívares con OCR (Gemini Vision)
- **RF-02.1**: Servicio `BankReceiptOCR` con soporte para imágenes (PNG, JPG, JPEG, WEBP):
  - Invocación multimodal a Google Gemini API (`inline_data` base64).
  - Reutilización del pool existente `AIKeyPool` (3 claves en rotación round-robin y failover automático ante 429/503).
- **RF-02.2**: Extracción estructurada en JSON con los campos:
  - `bank_name` (ej. Banco de Venezuela, Banesco, Mercantil, Provincial, Bancamiga, BNC).
  - `reference_number` (referencia de la transacción o últimos dígitos).
  - `amount_ves` (monto numérico en bolívares).
  - `sender_cedula` / `receiver_cedula` (cédula o RIF detectado).
  - `sender_name` / `receiver_name` (nombre del titular).
  - `date_time` (timestamp del pago).
  - `payment_method` (`PAGO_MOVIL` o `TRANSFERENCIA`).
- **RF-02.3**: Auto-conciliación inteligente (*Auto-Matching*):
  - Asociar el comprobante extraído con la orden P2P correspondiente en la base de datos comparando:
    1. Monto en VES ($\pm 0.05$ bolívares de tolerancia).
    2. Rango de fecha y hora.
    3. Cédula o nombre de la contraparte verificado con `IdentityService`.

### RF-03: Motor de Reconstrucción Contable de 6 Piezas y Snapshots
- **RF-03.1**: Ecuación de Consistencia de Inventario:
  $$\text{Saldo Inicial} + \text{Entradas} - \text{Salidas} = \text{Saldo Final Esperado}$$
- **RF-03.2**: Clasificación contable estricta:
  - *Saldo Inicial*: Obtenido del snapshot del cierre previo o ingresado por el usuario.
  - *Entradas*: Depósitos on-chain + Compras P2P completadas.
  - *Salidas*: Retiros on-chain + Ventas P2P completadas.
  - *Volumen*: Volumen total comercializado por activo (USDT, BTC).
  - *Comisiones*: Sumatoria de fees P2P (maker/taker) + comisiones de red blockchain.
  - *Saldo Final*: Snapshot real de billeteras vs. Saldo Final Calculado.
- **RF-03.3**: Detección y reporte de discrepancias: Si $|\text{Saldo Real} - \text{Saldo Calculado}| > 0.01$, generar alerta con diagnóstico de posibles mermas.
- **RF-03.4**: Integración de saldo inicial en el motor FIFO: Los lotes del inventario inicial se valoran a la tasa oficial BCV del día de inicio para su cómputo en el costo de adquisición.

### RF-04: Reportes Consolidados Multi-Pestaña (Excel y Google Sheets)
- **RF-04.1**: Generar libro contable de **4 pestañas** tanto en archivo local `.xlsx` como en Google Sheets:
  - **Pestaña 1 (`Resumen Reconstrucción Fiscal`)**: Cuadro de 6 piezas, volumen USDT, ingresos brutos VES, costo FIFO VES, ganancia neta gravable VES/USD y margen operativo %.
  - **Pestaña 2 (`Detalle P2P`)**: Listado cronológico de órdenes P2P con fecha/hora UTC, ID de orden, contraparte, cédula, tasa oficial BCV y utilidad neta.
  - **Pestaña 3 (`Depósitos y Retiros`)**: Entradas y salidas blockchain con fecha, moneda, cantidad, red, comisión y TXID.
  - **Pestaña 4 (`Conciliación Bancaria`)**: Comprobantes de Pago Móvil y transferencias en bolívares conciliados con su orden P2P y referencia bancaria.

### RF-05: Canales de Usuario (Dashboard Streamlit y Telegram)
- **RF-05.1**: En Dashboard Streamlit:
  - Nueva vista de Reconstrucción Fiscal con semáforo contable de balance.
  - Drag & drop de archivos de Binance (`.csv` y `.xlsx`).
  - Uploader de capturas bancarias con previsualización de datos extraídos por OCR.
  - Botón de sincronización con Google Sheets y descarga de Excel.
- **RF-05.2**: En Telegram Notifier:
  - Envío de fotos de comprobantes bancarios al bot con procesamiento OCR y confirmación de auto-conciliación en tiempo real.
  - Comando `/conciliacion [YYYY-MM]` para recibir el reporte de 6 piezas y el archivo `.xlsx` de 4 pestañas adjunto.

---

## 3. REQUISITOS NO FUNCIONALES

- **RNF-01 (Fail-Closed y Resiliencia)**: Si el servicio OCR falla o una imagen no es legible, el sistema no bloquea la contabilidad; registra el comprobante como `PENDING_REVIEW` y alerta al operador.
- **RNF-02 (Cero Secretos y Privacidad)**: Las claves de API de Gemini nunca se loguean. Las capturas bancarias se procesan en memoria volátil sin persistir datos bancarios sensibles fuera de la base de datos protegida.
- **RNF-03 (Rendimiento)**: El parser de archivos debe procesar más de 10,000 filas por segundo mediante `pandas` y `openpyxl`.
- **RNF-04 (Compatibilidad)**: El código debe pasar con 0 errores `ruff` y 100% de tipado en `mypy`.
