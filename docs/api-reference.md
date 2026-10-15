# Referencia de API y Endpoints

## Binance P2P API Endpoints
- `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory`:
  - Ventana máxima por petición: 30 días.
  - Firma obligatoria con par Ed25519.
  - Parámetros requeridos: `tradeType`, `startTimestamp`, `endTimestamp`, `page`, `rows`.
- `GET /sapi/v1/c2c/orderMatch/search`:
  - Consulta de order book P2P por fíat y activo.
- `POST /sapi/v1/c2c/ads/update`:
  - Actualización o cambio de estado de anuncios.

## Manejo de Rate Limits
- Header a monitorear: `x-mbx-used-weight`.
- Si `x-mbx-used-weight` > 5,000 (de 6,000 máx), el cliente pausa automáticamente 60 segundos.
