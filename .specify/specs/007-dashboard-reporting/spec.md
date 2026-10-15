# Spec 007: Dashboard y Reportes

## QUÉ
Un panel de control web con métricas operativas, fiscales y de seguridad en tiempo real.

## Requisitos Funcionales
- RF-01: Mostrar P&L neto, curva de rendimiento y ganancia fiscal acumulada del año.
- RF-02: Mostrar tasa de éxito de órdenes, volumen en fíat (VES) y USDT.
- RF-03: Mostrar latencia de API de Binance y peso consumido (`x-mbx-used-weight`).
- RF-04: Botón de descarga de informe fiscal en Excel y sincronización a Google Sheets.
- RF-05: Monitor de eventos de seguridad (auditoría de accesos a credenciales).

## Requisitos No Funcionales
- RNF-01: El dashboard opera en modo solo lectura sobre PostgreSQL/TimescaleDB.
- RNF-02: Las consultas del dashboard nunca deben bloquear transacciones de ingesta de órdenes.

## Criterios de Aceptación
- [ ] Test verifica que el dashboard lee sin emitir bloqueos de tabla.
- [ ] Test verifica que la descarga genera un archivo Excel íntegro y validado.
