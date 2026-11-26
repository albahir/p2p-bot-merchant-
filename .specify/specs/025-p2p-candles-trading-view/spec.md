# SPEC-025: Terminal de Velas P2P, Profundidad de Libro y Predictor Estadístico (`/market`)

**Especificación de Requerimientos Funcionales y Técnicos (SDD)**  
**Paquete:** `025-p2p-candles-trading-view`  
**Estado:** APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 20 de Noviembre de 2026  
**Dependencias:** `SPEC-002`, `SPEC-016`, `SPEC-020`, `SPEC-023`

---

## 1. Propósito y Alcance (QUÉ)

Dotar a `p2p-bot-merchant` de una pestaña independiente (**`Velas P2P`** -> `/market`) sin interferir con el flujo operativo ni contable existente (`/`, `/calculator`, `/orders`, `/accounting`, `/sheets`, `/settings`), que replique y supere la experiencia de análisis técnico e intradía observada en terminales P2P profesionales:

1. **Recolector Propio de Microestructura P2P**: Captura snapshots periódicos (Top 20 Compra/Venta, mejor punta, brecha BCV, volumen/profundidad Top 5/10/20, matriz por banco y ticket en VES) en tabla `market_snapshots` con consolidación OHLC horaria en `market_hourly_rollups`.
2. **Motor Analítico Cuantitativo (`src/core/market_analytics.py`)**:
   - Agregación de velas OHLC (`1m`, `5m`, `15m`, `1h`, `4h`, `1D`) con encadenado continuo (`open[i] = close[i-1]` opcional o exacto).
   - **Filtro de Hampel MAD** (`ventana=10`, `umbral=4`) para suprimir anuncios anómalos de 1 USDT antes de formar velas.
   - **Indicadores Técnicos**: EMA9, EMA21, EMA4/12, RSI 14 de Wilder (alineado por índice), velocidad de la brecha BCV vs P2P.
   - **Microestructura y Profundidad Real**: Acumulado Top 5 / Top 10 / Top 20, desequilibrio `(demanda - oferta) / total`, detección de liquidez flaca (`< 60%` de mediana de 2h) y cálculo de **VWAP real por ticket** (*¿a qué tasa promedio llenas tu monto exacto?*).
   - **Banda Probabilística del 90% por Percentiles Ponderados**: Calculada cuando existen `>= 20` días cerrados en historial (`backtest` honesto, sin campana de Gauss ni datos inventados — Fail-Closed).
3. **Interfaz TradingView `lightweight-charts` en `/market`**:
   - 5 vistas: `USDT · Venta`, `USDT · Compra`, `Por Banco & Monto`, `Evolución P2P vs BCV` y `Brecha (%)`.
   - Tipos de gráfico: `Velas`, `Línea`, `Área`, toggle `EMA9 / EMA21`, panel sincronizado `RSI 14` (70/30), líneas de banda probable (cuando haya datos), controles de zoom / volver al presente y captura manual en vivo.

---

## 2. Reglas Innegociables
1. **Aislamiento Total**: Nuevo botón lateral independiente `/market`; cero impacto en rendimiento o diseño de las páginas actuales.
2. **Principio Fail-Closed (Constitución #2)**: Si el historial aún no alcanza el mínimo de días para banda probabilística (`20` días) o profundidad histórica (`2h`), mostrar el estado honesto (*"Recolectando historial: X lecturas / Y días"*) sin inventar predicciones ficticias.
3. **Cero Secretos**: Solo consume endpoints públicos Binance C2C y tasa BCV oficial ya existentes en `SpreadMonitor` y `BCVHistoryService`.
