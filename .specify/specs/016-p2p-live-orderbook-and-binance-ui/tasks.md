# Tareas Atómicas: SPEC-016 (Búsqueda en Vivo Binance P2P e Interfaz con Filtros)

## 📌 Lista de Tareas

### Fase 1: Esquemas de Datos y Modelos Tipados
- [x] **T01**: Extender `src/core/binance_schemas.py` con `BinanceTradeMethod`, campo `tradeMethods` en `BinanceAdDetail` y propiedad `bank_names` en `BinanceSearchOrderItem`.
- [x] **T02**: Crear pruebas unitarias para validación de anuncios con métodos de pago bancarios en `tests/unit/test_binance_client.py`.

### Fase 2: Conector de Búsqueda P2P con Filtros Avanzados
- [x] **T03**: Actualizar `BinanceP2PClient.search_p2p_ads()` en `src/core/binance_client.py` para soportar `pay_types`, `trans_amount`, `merchant_check` con soporte para BAPI pública y SAPI.
- [x] **T04**: Actualizar `MockBinanceP2PClient` en `src/core/binance_mock.py` para implementar `search_p2p_ads()` con bancos reales venezolanos (Banesco, Mercantil, BDV, Pago Móvil, Bancamiga, Provincial, BNC, Banco Activo) y filtrado de montos y comercios.
- [x] **T05**: Ejecutar y validar pruebas en `tests/unit/test_binance_client.py`.

### Fase 3: Conexión de Cotizaciones en Vivo en SpreadMonitor
- [x] **T06**: Escribir pruebas unitarias en `tests/unit/test_spread_monitor.py` para `fetch_live_quotes()`.
- [x] **T07**: Implementar `fetch_live_quotes()` y mapeo bancario en `src/core/spread_monitor.py` con fallback resiliente a `get_market_quotes()`.

### Fase 4: Componente de Libro de Órdenes e Interfaz Estilo Binance en Streamlit
- [x] **T08**: Implementar `src/reporting/dashboard/components/binance_p2p_book.py` con:
  - Selector de Acción (Comprar / Vender con `st.segmented_control`).
  - Barra de filtros: Cripto, Fíat, Monto, Bancos / Métodos de pago, Solo Verificados.
  - Vista de anuncios estilo Binance P2P con métricas de comerciante, precio destacado, límites, badges de bancos y simulador de operación en vivo.
- [x] **T09**: Integrar `binance_p2p_book.py` en la pestaña `render_spread_tab()` de `src/reporting/dashboard/app.py`.
- [x] **T10**: Escribir pruebas unitarias de renderizado para el componente en `tests/unit/test_dashboard_components.py`.

### Fase 5: Verificación Integral y Documentación
- [x] **T11**: Ejecutar suite completa (`pytest`, `ruff check .`, `mypy src/`) y verificar 0 errores.
- [x] **T12**: Registrar tareas completadas en `tasks.md` y actualizar `memory.md` con ADR 038.
