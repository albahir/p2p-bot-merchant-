---
name: binance-p2p
description: Integración con la API oficial de Binance C2C/P2P con firma Ed25519 y monitor de weight.
---

# Binance P2P Skill

Instrucciones para agentes al trabajar con el conector de Binance P2P.

## Reglas Clave
1. Usar únicamente la API oficial con firma Ed25519 (`recvWindow=5000`).
2. Respetar el límite de peso: si `x-mbx-used-weight` > 5,000, esperar 60 segundos.
3. Paginación de historial de órdenes limitada a ventanas de 30 días.
4. Implementar siempre reintentos con backoff exponencial usando `tenacity`.
