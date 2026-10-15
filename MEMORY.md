# MEMORY.md — Memoria Persistente del Proyecto P2P Bot

## 📊 Estado del Proyecto por Paquetes y Tareas

### ✅ Paquete 001: Fundación de Seguridad (COMPLETADO: 9/9 tareas)
- [x] **T-001.1**: Creado `config/settings.py` con validación fail-closed vía `pydantic-settings`.
- [x] **T-001.2**: Definida tabla `security_events` y script `scripts/init_db.py`.
- [x] **T-001.3**: Implementado `src/security/api_key_manager.py` con cifrado AES-256-GCM y descifrado en memoria volátil.
- [x] **T-001.4**: Implementado `src/security/audit_logger.py` con encadenamiento criptográfico SHA-256 (append-only).
- [x] **T-001.5**: Implementada validación fail-closed de IP en `src/security/permissions.py`.
- [x] **T-001.6**: Test unitario `test_api_key_manager.py` validando que las claves no aparecen en logs.
- [x] **T-001.7**: Test integración `test_rotation.py` validando rotación in-place.
- [x] **T-001.8**: Test unitario validando bloqueo de arranque ante clave maestra ausente o corta.
- [x] **T-001.9**: Documentado procedimiento de rotación y respuesta en `docs/runbook.md`.

### ✅ Paquete 002: Conector Binance P2P (COMPLETADO: 10/10 tareas)
- [x] **T-002.1**: Conector configurado con soporte Ed25519 y secrets de Paquete 001.
- [x] **T-002.2**: Implementado `get_order_book(asset, fiat, method)` en `src/core/binance_client.py`.
- [x] **T-002.3**: Implementado `get_order_history()` con control fail-closed de ventana máxima de 30 días.
- [x] **T-002.4**: Implementados `create_ad`, `update_ad` y `pause_ad` en `src/core/binance_client.py`.
- [x] **T-002.5**: Integrado wrapper de reintentos exponencial con `tenacity`.
- [x] **T-002.6**: Monitoreo de `x-mbx-used-weight` con umbral de seguridad en 5,000 y pausa de 60s.
- [x] **T-002.7**: Tabla `orders` creada en `src/data/models.py`.
- [x] **T-002.8**: Ingesta idempotente implementada en `src/core/history_ingestor.py`.
- [x] **T-002.9**: Test unitario `test_binance_client.py` verificando ventana de 30 días y control de weight.
- [x] **T-002.10**: Test E2E de ciclo de órdenes en `tests/e2e/test_full_p2p_cycle.py`.

### ⏸️ Paquete 003: Motor de Estrategias y Anuncios
- *Estado*: **Pausado / Diferido** por especificación del usuario. Los contratos existentes permiten retomarlo sin afectar los módulos vigentes.

### ⏸️ Paquete 004: Verificación de Pagos Bancarios
- *Estado*: **Pausado / Diferido** por especificación del usuario.

### ✅ Paquete 005: Motor Fiscal e Historial (COMPLETADO: 9/9 tareas)
- [x] **T-005.1**: Implementadas clases `FIFOCostMethod` y `WeightedAverageCostMethod` en `src/reporting/tax_engine.py`.
- [x] **T-005.2**: Consumo y procesamiento de órdenes para cálculo de costo de adquisición y ganancia neta.
- [x] **T-005.3**: Campos `bcv_rate` y `fee_fiat` soportados en el modelo `Order`.
- [x] **T-005.4**: Servicio de consulta de tasa oficial en `src/reporting/bcv_service.py`.
- [x] **T-005.5**: Generador Excel de dos pestañas (*Detalle* y *Resumen*) en `src/reporting/excel_reporter.py`.
- [x] **T-005.6**: Exportador a Google Sheets en `src/reporting/sheets_exporter.py`.
- [x] **T-005.7**: Test unitario en `test_tax_engine.py` validando matemática contable FIFO vs Promedio.
- [x] **T-005.8**: Test de generación de Excel verificando integridad de las hojas.
- [x] **T-005.9**: Documentación de metodología contable en `docs/tax-methodology.md`.

### ✅ Paquete 006: Notificaciones Telegram (COMPLETADO: 6/6 tareas)
- [x] **T-006.1**: Credenciales configuradas y protegidas vía settings.
- [x] **T-006.2**: Envío de alertas con sanitización anti-fugas en `src/integrations/telegram_notifier.py`.
- [x] **T-006.3**: Verificación de remitente en lista blanca `TELEGRAM_ALLOWED_USER_IDS`.
- [x] **T-006.4**: Dispatcher de comandos `/status`, `/pause`, `/resume` y `/report`.
- [x] **T-006.5**: Test unitario `test_telegram_notifier.py` confirmando censura de secretos en mensajes.
- [x] **T-006.6**: Test unitario confirmando bloqueo de usuarios no autorizados.

### ✅ Paquete 007: Dashboard y Reportes (COMPLETADO: 6/6 tareas)
- [x] **T-007.1**: Repositorios de lectura de métricas en `src/data/repositories.py`.
- [x] **T-007.2**: Aplicación Streamlit en `src/reporting/dashboard/app.py`.
- [x] **T-007.3**: Tarjetas KPI y tabla de órdenes recientes en `kpi_cards.py`.
- [x] **T-007.4**: Botón interactivo de generación y descarga de reporte fiscal en Excel.
- [x] **T-007.5**: Visualizador de eventos de seguridad append-only en tiempo real.
- [x] **T-007.6**: Modo solo lectura garantizado para no bloquear la ingesta.

### ✅ Paquete 008: CI/CD e Infraestructura (COMPLETADO: 7/7 tareas)
- [x] **T-008.1**: Pipeline CI en `.github/workflows/ci.yml`.
- [x] **T-008.2**: Auditoría de seguridad continua en `.github/workflows/security.yml`.
- [x] **T-008.3**: Pipeline CD en `.github/workflows/cd.yml`.
- [x] **T-008.4**: Dockerfile multi-stage para motor de trading en `docker/Dockerfile.engine`.
- [x] **T-008.5**: Dockerfile para Dashboard Streamlit en `docker/Dockerfile.dashboard`.
- [x] **T-008.6**: Orquestación de servicios en `docker/docker-compose.yml`.
- [x] **T-008.7**: Configuración de exclusiones en `.dockerignore`.

---

## 📐 Decisiones Clave de Arquitectura (ADRs)

1. **Autenticación Ed25519 en Binance**: Menor latencia y recomendación oficial frente a RSA.
2. **Aislamiento del Motor Fiscal (Spec 005)**: Módulo contable puro en `src/reporting/` sin acoplamiento al motor de trading.
3. **Pausado de Paquetes 003 y 004**: Se desacopló la lógica de órdenes y fiscalidad para permitir operar directamente sobre el histórico y órdenes sin requerir la pasarela bancaria externa ni el algoritmo automatizado de precios en esta fase.
4. **Cero Secretos & Sanitización**: Detección y censura previa en alertas de Telegram y en eventos de auditoría.
5. **Protocolo Estricto de Agentes**: Obligación de marcar `[x]` en `tasks.md` y actualizar `memory.md` en cada iteración.

---

## 🎯 Próximo Paso Recomendado
Ejecutar la suite de tests en el entorno con `pytest -v tests/` o `make test` y configurar las credenciales en `config/.env`.