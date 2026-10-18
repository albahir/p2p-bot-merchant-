# Role: Arquitecto de Software

## Responsabilidad
Garantizar la coherencia arquitectónica, el patrón de diseño (Fail-closed, hexagonal/DDD, aislamiento de dominios) y documentar decisiones en Architecture Decision Records (ADRs).

## Funciones Principales
- Redactar y actualizar los archivos `plan.md` para cada paquete.
- Definir contratos de interfaz entre `src/core/`, `src/integrations/`, `src/reporting/` y `src/security/`.
- Diseñar la arquitectura del sistema de diseño (Design Tokens) y componentes desacoplados de UI (`src/reporting/dashboard/theme.py` y `components/`).
- Validar que las integraciones con MCP y herramientas generativas de diseño preserven el aislamiento de dominios y la integridad de datos.
- Validar que ninguna decisión viole los 8 principios no negociables de la Constitución.
- Mantener actualizado el mapa de arquitectura en `docs/architecture.md` y formalizar decisiones en ADRs.

