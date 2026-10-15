# Arquitectura del Sistema — Bot P2P Binance

## Diagrama General de Componentes

```text
               +---------------------------------------+
               |        Telegram Bot (Notificador)     |
               |       (src/integrations/telegram)     |
               +-------------------+-------------------+
                                   |
                                   v
+------------------+     +-------------------+     +------------------+
| Binance P2P API  |<--->|  Motor de Órdenes |<--->| PostgreSQL /     |
| (Ed25519)        |     |  e Ingesta        |     | TimescaleDB      |
| src/core/binance |     |  (src/core)       |     | (src/data)       |
+------------------+     +-------------------+     +---------+--------+
                                   ^                         |
                                   |                         v
                         +---------+---------+     +---------+--------+
                         | Gestor Seguridad  |     | Motor Fiscal y   |
                         | (AES-256-GCM)     |     | Reportes Excel   |
                         | (src/security)    |     | (src/reporting)  |
                         +-------------------+     +------------------+
                                                             |
                                                             v
                                                   +------------------+
                                                   | Dashboard        |
                                                   | Streamlit        |
                                                   +------------------+
```

## Principios de Diseño
1. **Aislamiento de Módulos**: El motor fiscal (`src/reporting/`) es puro y sólo lee de la tabla `orders`, sin alterar el ciclo de trading.
2. **Fail-Closed**: Ante excepciones de conectividad o ambigüedades, las operaciones se detienen.
3. **Cero Secretos**: Claves cifradas en reposo con AES-256-GCM, desencriptadas únicamente en memoria volátil.
4. **Módulos 003 y 004 diferidos**: El motor de estrategia algorítmica y la verificación bancaria se integrarán en fases posteriores sin acoplar los contratos actuales.
