# Skill: Integración con Binance P2P API

## Capacidades
- Conexión a la API C2C/P2P oficial de Binance utilizando firma criptográfica Ed25519 con passphrase.
- Consulta de order book P2P por filtros: activo (USDT, BTC), divisa fíat (VES) y canal de pago.
- Lectura de historial de órdenes con paginación máxima de 30 días.
- Monitoreo activo de tasa de consumo: inspección del header `x-mbx-used-weight` (pausa preventiva si supera 5,000).
- Estrategia de reintentos exponencial con `tenacity` ante códigos HTTP 429 y 5xx.
