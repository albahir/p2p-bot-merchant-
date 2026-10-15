# Plan 005: Motor Fiscal e Historial

## Stack
- `pandas` y `openpyxl` para generación de Excel.
- `gspread` para Google Sheets (opcional).
- `sqlalchemy` / PostgreSQL para consultas agregadas sobre `orders`.

## Arquitectura
- `src/reporting/tax_engine.py`: métodos FIFO y promedio como estrategias contables.
- `src/reporting/excel_reporter.py`: genera el informe Excel con hoja detalle y resumen.
- `src/reporting/sheets_exporter.py`: exporta a Google Sheets.

## Decisiones
- **Por qué separar del trading**: permite auditar y recalcular sin riesgo operacional.
- **Por qué registrar tasa BCV**: el ISLR en Venezuela se declara y tributa en bolívares.

## Dependencias
- Paquete 002 (necesita la tabla `orders` poblada con el historial de Binance P2P).
