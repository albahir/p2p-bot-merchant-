# MEMORY.md — Memoria Persistente del Proyecto P2P Bot

## 📊 Estado del Proyecto por Paquetes y Tareas

### ✅ Entorno y Verificación Local (ACTIVO)
- **Telegram Configurado**: Chat ID y Allowed User ID configurados como `6326947793`, sesión persistente con connection pooling.
- **Entorno Virtual**: `.venv` configurado y verificado con Python 3.13.
- **Base de Datos**: `p2p_bot.db` (SQLite local) activo y poblado.
- **Punto de Entrada Central**: `src/main.py` (`P2PBotEngine`).
- **Agentes del Sistema (`.github/agents/`)**:
  - `pm.md`: Product Manager.
  - `architect.md`: Arquitecto de Software.
  - `backend.md`: Desarrollador Backend.
  - `frontend.md`: Desarrollador Frontend y UI/UX (Streamlit).
  - `security.md`: Ingeniero de Ciberseguridad y Auditor Criptográfico.
  - `qa.md`: QA Tester.
  - `devops.md`: DevOps y Pipelines CI/CD.

### ✅ Paquetes Completados
- [x] **Paquete 001 (Fundación de Seguridad)**: Cifrado AES-256-GCM, auditoría append-only SHA-256, permisos de IP y tests completos (9/9).
- [x] **Paquete 002 (Conector Binance P2P)**: Cliente Ed25519, monitor de weight, límite de 30 días, anuncios e ingesta (10/10).
- [x] **Paquete 005 (Motor Fiscal e Historial)**: FIFO y Promedio ponderado, tasa BCV, exportador Excel de dos pestañas (9/9).
- [x] **Paquete 006 (Notificaciones Telegram)**: Alertas sanitizadas y comandos `/status`, `/pause`, `/resume`, `/report` (6/6).
- [x] **Paquete 007 (Dashboard y Reportes)**: Dashboard Streamlit base con métricas, órdenes y auditoría (6/6).
- [x] **Paquete 008 (CI/CD e Infraestructura)**: Pipelines GitHub Actions, Dockerfiles y Docker Compose (7/7).
- [x] **Paquete 009 (Panel de Control y UI de Operaciones - Mission Control)**: Implementada UI completa en Streamlit para operar tareas sin comandos de consola (7/7).
- [x] **Paquete 010 (Seguridad Avanzada de API, Concurrencia y Resiliencia)**:
  - Modelos Pydantic fuertemente tipados para todas las respuestas de Binance C2C (`src/core/binance_schemas.py`).
  - Sincronización de hora del servidor (`/api/v3/time`) y compensación automática de clock drift para evitar error `-1021`.
  - Gestor de concurrencia e idempotencia (`src/core/concurrency.py`) para evitar llamadas duplicadas.
  - Validador estricto de formato PEM Ed25519/RSA (`src/security/key_validator.py`).
  - Detección y bloqueo fail-closed inmediato ante errores 401/403/WAF para proteger la IP de bloqueos.
  - Simulador de Sandbox realista (`src/core/binance_mock.py`) con libros de órdenes activos en VES/USDT, anunciantes venezolanos, spreads comerciales reales y discriminación de órdenes COMPLETED vs CANCELLED.
  - Ingesta bidireccional (`trade_type="ALL"`) en `HistoryIngestor` para registrar simultáneamente compras y ventas.
  - Prueba de integración y E2E completa (`tests/e2e/test_sandbox_metrics.py`) verificando realismo, idempotencia, población de tasas BCV, cálculo fiscal FIFO / Promedio Ponderado y actualización dinámica de métricas ante nuevos trades.
  - Suite completa de 23 tests automatizados pasando al 100%.

### ⏸️ Paquetes Pausados
- ⏸️ **Paquete 003 (Motor de Estrategias)**: Pausado temporalmente por el usuario.
- ⏸️ **Paquete 004 (Verificación Bancaria)**: Pausado temporalmente por el usuario.

---

## 📐 Decisiones Clave de Arquitectura (ADRs)

1. **Investigación de Esquemas Oficiales Binance C2C**: Se integraron todos los campos oficiales devueltos por `listUserOrderHistory` (`orderNumber`, `advNo`, `tradeType`, `asset`, `fiat`, `fiatSymbol`, `amount`, `totalPrice`, `unitPrice`, `orderStatus`, `createTime`, `advertisementRole`, `takerCommission`, `commission`).
2. **Validación Previa Criptográfica (Spec 010)**: Antes de cifrar con AES-256-GCM, la clave privada se valida sintácticamente con `cryptography` para asegurar que cumple con el estándar PEM Ed25519/RSA.
3. **Control de Concurrencia (Mutex Singleton)**: `SyncLockManager` asegura que solo una tarea de red opere con Binance a la vez, liberando bloqueos huérfanos tras 30-60 segundos.
4. **Compensación de Clock Drift**: El bot consulta `/api/v3/time` y calcula el desfase horario en milisegundos para evitar el fallo de `recvWindow` ante desajustes del reloj del sistema operativo.
5. **No-Retry ante Fallos de Autenticación**: Respuestas 401, 403, `-2014` y `-2015` detienen inmediatamente las peticiones para no saturar el WAF de Binance ni arriesgar baneo de IP (HTTP 418).
6. **Simulación Realista de Arbitraje P2P**: El mock de Binance emula compras y ventas con spread comerciante (~2.5% a 3.0%), comisiones maker/taker y conversión oficial BCV. La ingesta es estrictamente idempotente.
7. **Interactividad del Sandbox y Ordenación en UI**: La tabla de transacciones de la UI se ordena por `Order.id.desc()` para que los registros recién insertados aparezcan siempre en la primera fila. Se añadieron controles para generar ciclos comerciales en vivo (`➕ Simular Nuevo Ciclo`) y limpiar historial (`🗑️ Limpiar Historial de Prueba`).
8. **Erradicación de Blind Exceptions (BLE001)**: Sustitución de cláusulas genéricas `except Exception` por excepciones acotadas de base de datos (`SQLAlchemyError`), red (`httpx.RequestError`), criptografía (`InvalidTag`, `UnsupportedAlgorithm`), y validación de tipos (`ValueError`, `TypeError`, `OSError`), garantizando observabilidad y pasando el linter estático de CI en verde.
9. **Sincronización Total del Entorno Virtual (`.venv`)**: Se generó [`requirements.txt`](file:///c:/p2p-bot-merchant/requirements.txt) y se instalaron todas las dependencias en `.venv` junto al paquete local en modo editable (`pip install -e .`), garantizando resolución inmediata de rutas `src` y `config` en VS Code y PyCharm.
10. **Tipado Estático Riguroso (Mypy 0 Errores en CI)**: Corrección integral de los 52 errores de tipado reportados por `mypy src/` en 8 módulos:
    - [`src/reporting/tax_engine.py`](file:///c:/p2p-bot-merchant/src/reporting/tax_engine.py): Conversiones explícitas `float()` y `str()` de campos de columnas ORM SQLAlchemy hacia dataclasses (`TaxLot`, `TradeResult`), eliminando incompatibilidades `Column[Any]` vs primitivos.
    - [`src/core/concurrency.py`](file:///c:/p2p-bot-merchant/src/core/concurrency.py): Anotaciones explícitas de clase para `_is_locked`, `_lock_timestamp` y `_current_task` en el singleton `SyncLockManager`.
    - [`src/core/binance_client.py`](file:///c:/p2p-bot-merchant/src/core/binance_client.py): Casteo tipado `cast(dict[str, Any], response.json())` y anotación estricta de parámetros en `get_order_history`.
    - [`src/core/history_ingestor.py`](file:///c:/p2p-bot-merchant/src/core/history_ingestor.py): Bifurcación tipada (`isinstance(item, dict)` vs modelo `BinanceOrderMatchItem`) para evitar llamadas `get()` sobre esquemas Pydantic.
    - [`src/reporting/sheets_exporter.py`](file:///c:/p2p-bot-merchant/src/reporting/sheets_exporter.py): Construcción tipada de matrices `data_to_write: list[list[Any]]` para `worksheet.append_rows()`.
    - [`src/data/repositories.py`](file:///c:/p2p-bot-merchant/src/data/repositories.py): Filtros y asignaciones tipadas de modelos SQLAlchemy compatibles con Ruff (`B010`) y Mypy.
    - [`pyproject.toml`](file:///c:/p2p-bot-merchant/pyproject.toml): Activación de `ignore_missing_imports = true` para dependencias de terceros sin stubs empaquetados.

---

## 🎯 Guía Operativa Actual

1. **Dashboard y Panel de Control**: `streamlit run src/reporting/dashboard/app.py` o `make dashboard`.
2. **Motor en Terminal (Opcional)**: `python -m src.main` o `make run`.
3. **Suite de Pruebas**: Ejecutable directamente desde la pestaña "🧪 Suite de Tests" del Dashboard o con `pytest -v tests/` (23/23 tests pasando).
4. **Comprobación de Calidad de Código**:
   - `mypy src/` (0 errores en 30 archivos fuente).
   - `ruff check .` (0 errores de linting).