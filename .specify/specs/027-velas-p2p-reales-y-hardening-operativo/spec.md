# SPEC-027: Velas P2P Verídicas Multi-Ticket, Filtros Reales, Blindaje Multi-Usuario y Retención NVMe

**Estado:** EN PROGRESO (SDD + TDD)  
**Fecha:** 26 de Noviembre de 2026  
**Dependencias:** `SPEC-020`, `SPEC-022`, `SPEC-025`, `SPEC-013`

---

## 1. Propósito (QUÉ)

Corregir las brechas detectadas tras la auditoría integral del repositorio y del módulo **Velas P2P** (`/market`) para garantizar:
1. **Cero datos inventados o disfrazados (Fail-Closed real)**: Ningún endpoint ni gráfico puede mostrar datos globales (`*`) cuando se filtra por banco específico, ni usar constantes hardcoded (`1005.0`, `820.0`) ni cotizaciones simuladas (`get_market_quotes`) fuera de Sandbox.
2. **Filtros reales funcionales en Velas P2P**:
   - Corrección integral de alias bancarios (`BBVA Banco Provincial` / `BBVA Provincial`, `BNC` / `BNC Banco Nacional de Crédito`, `Banco de Venezuela` / `SpecificBank`, `Pago Móvil`, `Mercantil`, `Banesco`, `Bancamiga`).
   - Recolección y graficación real para **3 tramos de ticket en Bs**: `250.000 Bs`, `1.000.000 Bs` y `5.000.000 Bs`, reflejados tanto en el histórico de velas como en la tarjeta VWAP en vivo.
   - Eliminación del KPI innecesario `Rango Histórico Esperado (0/20 días)` y ocultamiento opcional de indicadores bursátiles (`EMA 9/21`, `RSI 14`) bajo modo técnico avanzado.
3. **Seguridad y Tráfico Multi-Usuario (5+ operadores)**:
   - Exigir autenticación JWT en `POST /api/market/collect` e impedir que una captura con filtro contamine la serie global `*`.
   - Limpiar cachés de sesión y `localStorage` específico de usuario ante 401/logout/login.
   - Retirar la recarga masiva en bucle cada 45s de `warmAuthenticatedSession()` en `TelemetryProvider` y conectar broadcasting real mínimo o heartbeat limpio.
4. **Sostenibilidad 100 GB NVMe y Alineación Documental**:
   - Purga automática de `market_snapshots > 30 días` conservando `market_hourly_rollups`.
   - Rotación de logs en `docker/docker-compose.yml` y limpieza de imágenes en `scripts/deploy_vps.sh`.
   - Marcar formalmente `SPEC-023` como pendiente (`0/26`) y corregir `memory.md`.
