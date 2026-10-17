---
name: binance-p2p
description: Integración con la API oficial de Binance C2C/P2P con firma Ed25519 y monitor de weight.
---

# Binance P2P Skill

Instrucciones para agentes al trabajar con el conector de Binance P2P y módulos de reportería fiscal.

## 📖 Documentación Oficial de Referencia
* [Binance Developer Documentation](https://developers.binance.com/en/docs/introduction)
* [Binance API Catalog](https://developers.binance.com/en/docs/catalog)

## 🛡️ Reglas Clave de Integración
1. **Firma Criptográfica**: Usar únicamente la API oficial con firma Ed25519, RSA o HMAC (`recvWindow=5000`).
2. **Monitor de API Weight**: Respetar el límite de peso: si `x-mbx-used-weight` > 5,000, pausar peticiones 60 segundos.
3. **Paginación Controlada**: Ventanas máximas de 30 días para historial P2P y 90 días para depósitos/retiros.
4. **Resiliencia de Red**: Implementar siempre reintentos con backoff exponencial usando `tenacity`.
5. **Reconstrucción Contable P2P**: Consultar [`.agents/rules/p2p-fiscal-rules.md`](file:///c:/p2p-bot-merchant/.agents/rules/p2p-fiscal-rules.md) para la consolidación de los 3 reportes base:
   - `C2C Trade History`: `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory`
   - `Deposit History`: `GET /sapi/v1/capital/deposit/hisrec`
   - `Withdrawal History`: `GET /sapi/v1/capital/withdraw/history`
   - `Convert Trade Flow`: `GET /sapi/v1/convert/tradeFlow`
   - `Asset Dividend / Rewards`: `GET /sapi/v1/asset/assetDividend`
