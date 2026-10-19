# SPEC-016: Conexión de Precios en Vivo Binance P2P e Interfaz con Filtros Estilo Binance

## 1. Visión General y Justificación
Actualmente el bot calcula márgenes y rentabilidad usando una instantánea estática calibrada en `SpreadMonitor.get_market_quotes()`. El usuario requiere:
1. Conectar la búsqueda de precios reales de Binance P2P por banco y método de pago en tiempo real.
2. Incorporar en el Dashboard una interfaz idéntica a la de Binance P2P que incluya los filtros oficiales (Comprar/Vender, Criptoactivo, Fíat, Monto, Bancos/Métodos de pago y Comerciantes verificados) y muestre el libro de órdenes con anunciantes, precios, límites, métodos de pago y calculadora de ciclo.
3. Mantener arquitectura Fail-closed y fallback transparente al modo Sandbox/Simulación en caso de desconexión o cuando esté habilitado el entorno de pruebas.

## 2. Requisitos Funcionales
- **RF-01**: Ampliar esquemas de datos (`BinanceAdDetail`, `BinanceSearchOrderItem`) para soportar métodos de pago (`tradeMethods`, `payMethods`, nombres de bancos).
- **RF-02**: Implementar cliente de búsqueda P2P con soporte para endpoint público BAPI (`https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search`) y SAPI oficial de Binance con filtros:
  - `tradeType`: BUY / SELL
  - `asset`: USDT, BTC, ETH, etc.
  - `fiat`: VES, USD, etc.
  - `payTypes`: Métodos de pago bancarios (`SpecificBank`, `PagoMovil`, `Banesco`, `Mercantil`, `Bancamiga`, `BBVABancoProvincial`, `BancoNacionaldeCredito`, `BancoActivo`).
  - `transAmount`: Monto mínimo/máximo en moneda fíat.
  - `merchantCheck`: Filtrar solo comerciantes verificados.
- **RF-03**: En `MockBinanceP2PClient`, sincronizar la firma de `search_p2p_ads()` para devolver anuncios mock enriquecidos con bancos reales venezolanos y filtros compatibles.
- **RF-04**: Integrar en `SpreadMonitor` el método `fetch_live_quotes()` que consulta Binance P2P en vivo por banco, con caché temporal (TTL de 30s) y fallback seguro a cotizaciones calibradas.
- **RF-05**: Crear componente Streamlit `binance_p2p_book.py` con:
  - Selector Comprar/Vender con `st.segmented_control`.
  - Barra de filtros estilo Binance: Fíat, Cripto, Monto en Bs, Método de pago / Banco, y Check de Comerciante.
  - Renderizado de anuncios estilo Binance P2P con Nickname, % de finalización, precio destacado, límites, badges de bancos y simulador de ciclo de compra/venta.
- **RF-06**: Integrar el componente en la pestaña `📈 Monitor & Arbitraje P2P` del Dashboard Streamlit.

## 3. Requisitos No Funcionales y Seguridad
- **RNF-01**: Cumplir estrictamente la Constitución: Cero Secretos en UI o logs, fail-closed ante timeouts o errores de red.
- **RNF-02**: Compatibilidad total con Streamlit 2026: usar `width="stretch"`, `st.segmented_control`, `st.container(border=True)` y Material Symbols `:material/...:`.
- **RNF-03**: Cobertura de pruebas unitarias al 100% en las nuevas funcionalidades bajo ciclo TDD.
