# Plan 002: Conector Binance P2P

## Stack
- `binance-sdk-c2c` (SDK oficial) / `httpx` (firma Ed25519, timeouts y retries)
- `tenacity` (backoff exponencial)
- `sqlalchemy` (persistencia de órdenes)

## Arquitectura
- `src/core/binance_client.py`: cliente principal con Ed25519 y monitor de weight.
- `src/core/history_ingestor.py`: job programado para ingesta mensual.
- `src/data/models.py`: modelos SQLAlchemy para tabla `orders`.

## Endpoints Clave
- `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory` — historial.
- `GET /sapi/v1/c2c/orderMatch/search` — order book.
- `POST /sapi/v1/c2c/ads/update` — actualizar anuncio.

## Decisiones
- **Por qué Ed25519**: recomendado por Binance, más rápido que RSA, misma seguridad.
- **Por qué paginación mensual**: la ventana máxima es 30 días por llamada.
- **Por qué job programado**: la API solo da 6 meses; persistimos para tener historial completo.

## Dependencias
- Paquete 001 (necesita API Keys cifradas).
