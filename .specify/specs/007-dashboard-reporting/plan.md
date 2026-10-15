# Plan 007: Dashboard y Reportes

## Stack
- Streamlit (dashboard web interactivo).
- TimescaleDB / PostgreSQL (series temporales y métricas).
- Plotly / Altair (gráficos de rendimiento y volumen).

## Arquitectura
- `src/reporting/dashboard/app.py`: punto de entrada Streamlit.
- `src/reporting/dashboard/components/`: widgets modulares (KPIs, gráficos, descargas).
- Repositorios dedicados de lectura en `src/data/repositories.py`.

## Decisiones
- **Por qué Streamlit**: desarrollo rápido en Python nativo, fácil integración con los modelos existentes.
- **Consultas con timeout y replica/read-only**: protege la base de datos principal de sobrecargas.

## Dependencias
- Paquete 002 (datos de órdenes).
- Paquete 005 (cálculos fiscales).
