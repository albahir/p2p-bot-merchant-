# Tasks 002: Conector Binance P2P

- [x] T-002.1 Configurar cliente Binance P2P y Ed25519 con credenciales de Paquete 001.
- [x] T-002.2 Implementar `get_order_book(asset, fiat, method)` en `src/core/binance_client.py`.
- [x] T-002.3 Implementar `get_order_history(start, end)` con paginación y límite de 30 días.
- [x] T-002.4 Implementar `create_ad`, `update_ad`, `pause_ad`.
- [x] T-002.5 Implementar wrapper de retry con `tenacity`.
- [x] T-002.6 Implementar monitoreo de `x-mbx-used-weight` y guardia fail-closed (> 5,000).
- [x] T-002.7 Crear tabla `orders` en PostgreSQL / SQLite (`src/data/models.py`).
- [x] T-002.8 Implementar `history_ingestor.py` para sincronización local.
- [x] T-002.9 Test unitario: backoff ante 429 y límite de 30 días.
- [x] T-002.10 Test integración: ciclo completo en sandbox / mock.
