# Spec 002: Conector Binance P2P

## QUÉ
Un cliente que autentica y comunica con la API P2P de Binance
para leer el order book, crear/actualizar anuncios y consultar órdenes.

## Requisitos Funcionales
- RF-01: Autenticar con Ed25519 + passphrase.
- RF-02: Consultar order book de P2P por activo, fíat y método de pago.
- RF-03: Crear, actualizar y pausar anuncios propios.
- RF-04: Consultar historial de órdenes con paginación mensual (máx. 30 días por llamada).
- RF-05: Respetar y monitorear `x-mbx-used-weight`.
- RF-06: Reintentos con backoff exponencial ante 429 y 5xx.

## Requisitos No Funcionales
- RNF-01: Timeout de 10s por llamada.
- RNF-02: Si `x-mbx-used-weight` supera 5,000, pausar 60s.
- RNF-03: Toda llamada firmada debe llevar `recvWindow` de 5,000ms.

## Criterios de Aceptación
- [ ] Un test verifica que el backoff se dispara ante 429.
- [ ] Un test verifica que el parser de historial maneja correctamente el corte de 30 días.
- [ ] Un test de integración simula el ciclo completo orden→anuncio→cancelación.
