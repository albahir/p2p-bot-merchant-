# Plan de Diseño Arquitectónico: SPEC-016 (Búsqueda en Vivo Binance P2P e Interfaz con Filtros)

## 1. Arquitectura de Módulos

```
                                  ┌─────────────────────────────┐
                                  │   Dashboard Streamlit       │
                                  │   (P2P Merchant Monitor)    │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    binance_p2p_book.py      │
                                  │   (UI con Filtros Binance)  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │      SpreadMonitor          │
                                  │ (fetch_live_quotes / calc)  │
                                  └──────────────┬──────────────┘
                                                 │
                   ┌─────────────────────────────┴─────────────────────────────┐
                   ▼                                                           ▼
    ┌─────────────────────────────┐                             ┌─────────────────────────────┐
    │     BinanceP2PClient        │                             │    MockBinanceP2PClient     │
    │  (BAPI / SAPI con filtros)  │                             │   (Simulador enriquecido)   │
    └─────────────────────────────┘                             └─────────────────────────────┘
```

## 2. Decisiones de Diseño
1. **Esquemas enriquecidos (`binance_schemas.py`)**:
   - `BinanceTradeMethod`: `payId`, `payMethodId`, `payType`, `tradeMethodName`.
   - `BinanceAdDetail.tradeMethods`: lista tipada de métodos de pago.
   - Propiedad `bank_names` en `BinanceSearchOrderItem` para filtrado y visualización rápida.
2. **Cliente P2P Universal (`BinanceP2PClient` y `MockBinanceP2PClient`)**:
   - Soporte para parámetros de filtrado avanzados: `pay_types`, `trans_amount`, `merchant_check`.
   - Implementar fallback resiliente: Si la red hacia Binance falla o da timeout, captura la excepción y retorna un libro simulado o cotización de reserva, impidiendo caídas del Dashboard.
3. **Componente Visual (`binance_p2p_book.py`)**:
   - Filtros superiores: Segmented control para Compra/Venta, Selectores para Cripto y Fíat, Input para Monto, Multiselect/Select para Bancos, y Toggle para Verificados.
   - Tarjetas de órdenes estilizadas con tema Glassmorphism / Stitch Tokens.
   - Botón interactivo de simulación rápida de trade: permite ingresar un monto de USDT o VES y desglosa comisiones bancarias, comisión Binance y ganancia neta.
4. **Ciclo TDD**:
   - Primero se escribirán las pruebas para `search_p2p_ads()` con filtros en `test_binance_client.py` y `test_spread_monitor.py`.
   - Luego se implementará el código correspondiente.
