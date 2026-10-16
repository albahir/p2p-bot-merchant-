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
  - `researcher.md`: Investigador Técnico & Especialista en Documentación (APIs, benchmarking y cloud).

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
- [x] **Paquete 011 (Resiliencia de Telegram y Operación Continua con Sandbox)**:
  - Diagnóstico de red profundo: identificación de filtrado TCP puerto 443 por parte de operadoras/ISP hacia `api.telegram.org` (ping responde 151 ms pero TCP SYN es descartado).
  - Soporte de configuración de red resiliente: parámetros `TELEGRAM_PROXY_URL` (SOCKS5/HTTP) y `TELEGRAM_API_BASE_URL` (reverse proxies / Cloudflare Workers).
  - Fallback automático a texto plano (`parse_mode=None`) ante respuestas HTTP 400 por sintaxis Markdown.
  - Manejo estricto de Rate Limiting HTTP 429 con lectura de `retry_after` y backoff exponencial.
  - Cola de despacho en segundo plano (`TelegramQueueDispatcher`) con hilo daemon para envíos no bloqueantes.
  - Escucha de comandos en tiempo real vía long-polling (`TelegramCommandPoller`) respondiendo `/status`, `/pause`, `/resume`, `/report`, `/ayuda`.
  - Operación continua de `P2PBotEngine` en modo Sandbox activo cuando no hay claves reales configuradas.
  - Notificaciones automáticas a Telegram en sincronización de órdenes y simulación de ciclos en el Dashboard.
  - Suite completa de 27 tests pasando al 100%.

- [x] **Paquete 012 (Asistente de IA para Consultas Naturales en Telegram)**:
  - Implementado `src/integrations/ai_assistant.py` (`TelegramAIAgent` y `AIAssistantTools`) con Function Calling (Tools) de solo lectura conectado a `OrderRepository`, `TaxEngine` y `BCVService`.
  - Enrutamiento híbrido en `TelegramCommandPoller`: Comandos deterministas (`/status`, etc.) + lenguaje natural libre vía Google Gemini API.
  - Catálogo de herramientas seguras: `obtener_metricas_fiscales`, `consultar_ordenes_recientes`, `consultar_tasa_bcv`, `consultar_estado_sistema`.
  - Sanitización estricta anti-filtración de secretos en todas las salidas del modelo.
  - Suite completa de 31 tests pasando al 100%.

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
11. **Resiliencia Multicapa en Mensajería Telegram y Desacoplamiento Asíncrono (Spec 011)**:
    - Arquitectura asíncrona de envío (`TelegramQueueDispatcher`) para evitar bloqueos del hilo principal o de la interfaz Streamlit ante latencias de red.
    - Fallback de degradación suave: ante error HTTP 400 (entidades Markdown corruptas o no escapadas), reintento transparente en texto plano para asegurar entrega del 100% de los mensajes.
    - Cumplimiento de límites de velocidad (HTTP 429) respetando parámetros de `retry_after`.
    - Soporte nativo para proxies (SOCKS5/HTTP) y endpoints alternativos (`TELEGRAM_PROXY_URL`, `TELEGRAM_API_BASE_URL`) para sortear el bloqueo de puertos TCP 443 ejercido por operadoras locales.
    - Polling continuo (`TelegramCommandPoller`) para interacción bidireccional desde la app móvil.
12. **Asistente Conversacional Híbrido con Function Calling Seguro (Spec 012)**:
    - Desacoplamiento entre comandos rápidos deterministas (`/status`, etc.) y consultas analíticas en lenguaje natural.
    - Implementación de Function Calling (Tools) exclusivo de solo lectura (`AIAssistantTools`) que consulta datos reales de SQLite y del motor fiscal sin riesgo de alucinaciones.
    - Guardrail estricto de seguridad: el LLM nunca recibe claves privadas ni API keys, y sus respuestas se filtran obligatoriamente con `sanitize_message()`.
13. **Despliegue Cloud Continuo 24/7 y Health Checks Multi-Puerto (ADR 013)**:
    - `Dockerfile` multi-stage para despliegues ligeros con usuario no root (`appuser`) y permisos de escritura sobre `/app/p2p_bot.db`.
    - Servidor HTTP ligero integrado en `src/main.py` respondiendo tanto a métodos `HEAD` como `GET` (HTTP 200 OK) para superar los scanners de salud de Render, Koyeb y Docker.
    - Enlace a puertos dinámicos (`PORT`, `8000`, `10000`) para garantizar compatibilidad con cualquier enrutador de nube sin requerir configuración manual.
    - Etiquetado de instancia `[hostname | pid]` en las alertas de inicio y cierre de Telegram para distinguir el cese de contenedores antiguos durante rolling updates de caídas efectivas.
14. **Auto-Autorización y Resiliencia de Permisos en Telegram (ADR 014)**:
    - Soporte dual de variables de entorno mediante `AliasChoices("TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_ALLOWED_USERS")`.
    - Reconocimiento automático del dueño: si la lista explícita está vacía, se autoriza por defecto al remitente cuyo `user_id` coincide con `TELEGRAM_ALERT_CHAT_ID` en chats privados.
    - Mensajes diagnósticos con el ID exacto del remitente para facilitar la configuración sin depender de bots externos.
15. **Estandarización de Modelo Gemini de Alto Rendimiento y Fallback Automático (ADR 015)**:
    - Verificación directa contra la API de Google en vivo: la serie `gemini-1.5` fue retirada por Google devolviendo HTTP 404 en favor de `gemini-flash-lite-latest` y `gemini-3.5-flash-lite`, los cuales responden con HTTP 200 OK y ejecutan Function Calling en menos de 1 segundo.
    - Implementación de cascada de modelos de respaldo ante errores HTTP 404/503 y rotación de claves ante errores 400/403/429.
16. **Pool Dinámico de Claves API y Rotación Silenciosa ante Límites de Tasa (ADR 016)**:
    - Implementación de `AIKeyPool` en `src/integrations/ai_assistant.py`: soporte multi-clave mediante `AI_API_KEY` o `AI_API_KEYS` con separación por coma o punto y coma.
    - Detección automática de errores HTTP 429/403: la clave saturada entra en cooldown (60s) y el sistema rota de inmediato y silenciosamente a la siguiente clave de respaldo disponible.
    - Reintento transparente sin fricción para el usuario en Telegram, garantizando alta disponibilidad continua incluso bajo uso intensivo.
    - Enmascaramiento estricto (`AIzaSy...7GBE`) en logs para cumplir la Constitución de Cero Secretos.
17. **Telemetría en Tiempo Real de Claves de IA y Automatización Render (ADR 017)**:
    - Exposición de telemetría viva de cada slot de clave API mediante comando `/keys`, `/claves`, `/ai_status` y Function Calling (`consultar_estado_claves_ia`).
    - Métricas en tiempo real: clave activa, peticiones atendidas por clave, contador de saturación, estado de enfriamiento con segundos exactos para restablecimiento y timestamp de última reactivación.
    - Integración con Deploy Hooks de Render para automatización de despliegues post-commit.
18. **Balanceo Proactivo Round-Robin y Failover Resiliente ante 503/500/Red en AIKeyPool (ADR 018)**:
    - Diagnóstico de Causa Raíz: La Clave #1 atendía el 100% de las peticiones mientras las demás permanecían inactivas porque el selector operaba en modo activo-pasivo. Ante un pico de carga de Google (HTTP 503), un `break` prematuro interrumpía el ciclo de intentos sin marcar la clave en cooldown ni probar las claves de respaldo #2 y #3.
    - Balanceo Proactivo Round-Robin: Cada llamada al modelo (incluyendo el envío del prompt y la resolución de Function Calling) avanza el puntero de forma equitativa entre todas las claves activas (1 -> 2 -> 3 -> 1), multiplicando por 3 la capacidad de cuota (45 RPM) y evitando el sobrecalentamiento de una sola clave.
    - Failover Resiliente en Vuelo: Ante cualquier respuesta 503 (servidor saturado), 500/502/504, 429/403 o timeout de red, la clave se pone en enfriamiento y el bot rota inmediatamente a la siguiente clave disponible para responder al usuario sin devolver mensajes de error.
    - Suite de pruebas expandida: 37/37 tests pasando al 100%.
19. **Integridad Criptográfica de Firmas Binance (Ed25519, RSA, HMAC-SHA256) y Preparación para Claves Reales (ADR 019)**:
    - Diagnóstico de Auditoría: Se detectó que `BinanceP2PClient` no calculaba ni anexaba el parámetro obligatorio `signature` en las peticiones autenticadas (`get_order_history`, `create_ad`, `update_ad`), lo que provocaría el rechazo inmediato `-1102` por parte de Binance. Además, el validador restringía las entradas exclusivamente a formato PEM, bloqueando las API Secret Keys HMAC estándar generadas por la interfaz de Binance.
    - Motor Universal de Firma (`sign_params`): Implementado cálculo criptográfico estricto sobre query strings urlencoded con soporte automático para:
      - Claves asimétricas Ed25519 (formato PEM PKCS8, firma Base64).
      - Claves asimétricas RSA (formato PEM PKCS8/PKCS1, padding PKCS1v15 + SHA256, firma Base64).
      - Claves simétricas HMAC-SHA256 (64 caracteres hex, firma Hex).
    - Flexibilización Segura del Gestor de Credenciales: `KeyValidator.validate_secret_key()` y la UI del Dashboard aceptan tanto bloques PEM como API Secrets HMAC sin degradar la regla de Fail-closed.
    - Orquestación Inteligente en `src/main.py`: Si existen credenciales reales en la base de datos cifrada y `USE_SANDBOX` no está forzado a True, el motor arranca directamente en Modo Producción con el cliente oficial de Binance P2P.
    - Suite de pruebas expandida: **41/41 tests pasando al 100%**.
20. **Mecanismo Anti-Suspensión KeepAlivePinger en Nube Gratuita y Evaluación de Servidores MCP (ADR 020)**:
    - Diagnóstico de Infraestructura: Render suspende los contenedores Web gratuitos tras 15 minutos sin tráfico HTTP entrante, lo que congelaba el bot y detenía la escucha de comandos de Telegram.
    - KeepAlivePinger Autónomo: Se implementó un hilo daemon que detecta la variable inyectada por Render (`RENDER_EXTERNAL_URL` o `KEEP_ALIVE_URL`) y realiza una solicitud HTTP GET ligera cada 10 minutos (600s), manteniendo despierto el servicio 24/7 sin exceder las 750 horas gratuitas mensuales.
    - Ecosistema MCP (Model Context Protocol): Evaluación y catalogación de servidores MCP útiles para el proyecto (`@modelcontextprotocol/server-sqlite` para auditoría directa de BD, `github-mcp` para CI/CD, `fetch/puppeteer-mcp` para scraping BCV y `binance-mcp` para market data).
    - Suite de pruebas expandida: **43/43 tests pasando al 100%**.
21. **Scraping Directo del Portal Oficial BCV y Servidores MCP (ADR 021)**:
    - Diagnóstico de Fuente de Tasas: La API de terceros previa (`pydolarvenezuela-api.vercel.app`) quedó inoperativa devolviendo HTTP 404 permanente, bloqueando la conversión fiscal fidedigna.
    - Extracción HTML Oficial BCV: Se implementó `_scrape_bcv_official()` y `_parse_bcv_html()` en `BCVService` apuntando directamente a `https://www.bcv.org.ve`. Extrae la tasa del dólar oficial (`<div id="dolar">...<strong class="strong-tb">880,11590000</strong>`), euro, yuan, rublo, lira y fecha valor oficial.
    - Resiliencia SSL Gubernamental: Manejo seguro de certificados locales del BCV (`verify=False` en HTTPX con User-Agent estándar de navegador), fallback en cascada a endpoints secundarios y memoria caché local en caso de caídas del portal.
    - Servidores MCP Configurados: Configuración global en `~/.gemini/config/mcp_config.json` para Puppeteer, Filesystem y GitHub MCP via Stdio `npx`.
    - Suite de pruebas expandida: **46/46 tests pasando al 100%**.

---

## 🎯 Guía Operativa Actual

1. **Dashboard y Panel de Control**: `streamlit run src/reporting/dashboard/app.py` o `make dashboard`.
2. **Motor en Terminal (Opcional)**: `python -m src.main` o `make run` (opera en bucle continuo emitiendo alertas y respondiendo comandos).
3. **Suite de Pruebas**: Ejecutable directamente desde la pestaña "🧪 Suite de Tests" del Dashboard o con `pytest -v tests/` (46/46 tests pasando al 100%).
4. **Comprobación de Calidad de Código**:
   - `mypy src/` (0 errores en 31 archivos fuente).
   - `ruff check .` (0 errores de linting).