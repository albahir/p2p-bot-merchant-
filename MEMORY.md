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

- [x] **Paquete 014 (Reconstrucción Fiscal P2P de 6 Piezas, Parser Inteligente Binance y OCR Bancario Multimodal)**:
  - Persistencia en SQLAlchemy con modelos `WalletMovement`, `BankVoucher` y `FiscalPeriodSnapshot` y repositorios con inserción idempotente.
  - `BinanceFileParser`: procesa Órdenes C2C, Depósitos y Retiros (.csv y .xlsx), saltando automáticamente metadatos en Excel y reconociendo encabezados en español e inglés.
  - `BankReceiptOCR`: Extracción inteligente multimodal con Gemini Vision aprovechando `AIKeyPool` (3 claves API con rotación round-robin) y auto-matching con órdenes P2P ($\pm 24\text{ h}$, tolerancia $\pm 0.05\text{ VES}$).
  - `FiscalReconciler`: ejecuta la ecuación patrimonial de 6 piezas ($\text{Saldo Inicial} + \text{Entradas} - \text{Salidas} - \text{Comisiones} = \text{Saldo Final Teórico}$), detecta mermas/discrepancias e integra `FIFOCostMethod` extendido con inventario inicial valorado a tasa BCV.
  - Exportación multi-pestaña auditada en `ExcelReporter` y `SheetsExporter`: genera las 4 pestañas *Resumen Fiscal*, *Detalle P2P*, *Depósitos y Retiros*, y *Conciliación Bancaria*.
  - Panel interactivo en Streamlit (`fiscal_reconstruction_view.py`) con subida drag-and-drop de archivos de Binance y fotos de comprobantes bancarios, tarjetas de 6 piezas, liquidación ISLR y descarga directa.
  - Integración con Telegram: comando `/conciliacion` y soporte para fotos de comprobantes bancarios vía OCR en tiempo real.
  - Suite completa de 84 tests pasando al 100% (64 previos + 20 nuevos).

- [x] **Paquete 015 (Control de Acceso RBAC, Aislamiento de Invitados y Búsqueda Criptográfica MetaP2P)**:
  - Modelo de datos `User` y `UserRepository` en SQLAlchemy para control de usuarios, roles (`ADMIN`, `TRADER`, `INVITADO`), contraseñas cifradas y asociación con IDs de Telegram.
  - `AuthService` con algoritmo PBKDF2-HMAC-SHA256 (100,000 iteraciones), salting criptográfico, verificación en tiempo constante, tokens de sesión firmados con HMAC-SHA256 y auto-creación del Administrador principal.
  - Conector `MetaP2PClient` (`https://api.metap2p.io/api`): autenticación con `POST /api/login`, almacenamiento volátil de JWT Bearer en memoria, auto-renovación ante expiración (HTTP 401) y consulta de DNI con formato normalizado.
  - Integración en `IdentityService` como fallback prioritario antes de SENIAT y CNE.
  - Aislamiento estricto de roles en Telegram:
    - `INVITADO`: Menú móvil y teclado persistente reducido a 3 botones (`📈 Spreads P2P`, `🏛️ Tasa BCV`, `❓ Ayuda`). Bloqueo de comandos sensibles (`/cedula`, `/conciliacion`, `/cierre`, `/sheets`, etc.) con respuesta Fail-closed.
    - `TRADER`: Acceso operativo y de auditoría (órdenes, conciliación, comprobantes OCR, búsqueda de cédulas), con prohibición estricta de pausar/reanudar el bot o modificar usuarios.
    - `ADMIN`: Comandos de gestión de accesos `/usuarios`, `/autorizar`, `/revocar`, control de bot y aprobación interactiva de nuevos solicitantes con botones táctiles.
  - Vista de Login Glassmorphism en Streamlit (`src/reporting/dashboard/views/login_view.py`) y renderizado condicional de pestañas en `app.py` según el rol (`INVITADO` solo visualiza Spreads y Mercado P2P).
  - Suite de pruebas expandida a **119/119 tests pasando al 100%**.

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
22. **Inyección de Dependencias en Ingestor, Aislamiento Determinista de CI y Node.js Portable (ADR 022)**:
    - Diagnóstico de Causa Raíz en CI: En GitHub Actions, `BCVService` consultó el portal oficial en vivo obteniendo 880.1159 VES/USD. El dataset de prueba en sandbox maneja operaciones a ~36.5-38.0 VES/USDT con ganancia de 317.38 VES. Al dividir 317.38 / 880.1159 = 0.3606 USD, la prueba falló la aserción estática `> 5.0` (la cual asumía una tasa antigua de 36.5 VES/USD).
    - Inyección de BCVService en HistoryIngestor: Se refactorizó `HistoryIngestor` para aceptar `bcv_service: Any = None` como parámetro inyectable, evitando consultas externas durante pruebas y eliminando instanciaciones repetitivas en bucles de ingesta.
    - Determinismo en Pruebas E2E: En `test_sandbox_metrics.py` se desacopla la prueba del scraping en vivo inyectando una tasa controlada (36.50 VES/USD) y se verifica la coherencia matemática de conversión fiat a USD mediante `pytest.approx()`.
    - Node.js LTS Portable: Descargado e instalado Node.js v20.18.0 LTS y npx 10.8.2 en `c:\p2p-bot-merchant\.bin\nodejs`, incorporado al PATH de usuario y referenciado en `mcp_config.json`.
23. **Estrategia de IP Estática y Hoja de Ruta para Despliegue en VPS (ADR 023)**:
    - Diagnóstico de Red en Render: Render opera con IPs de salida dinámicas y compartidas que cambian en cada reinicio o deploy. La Regla #1 de la Constitución y la API oficial de Binance exigen IP Whitelist estricta para operar P2P en producción con claves reales.
    - Solución Primaria (VPS Dedicada): Migración del stack completo vía Docker Compose (`docker/docker-compose.yml`) a una VPS con IPv4 fija garantizada (ej. Hetzner, DigitalOcean, AWS Lightsail), asegurando operación 24/7 sin suspensiones y con IP fija permanente para Binance.
    - Solución Alternativa (Egress Proxy Estático): Canalización de peticiones salientes a Binance a través de proxy con IP fija (`BINANCE_PROXY_URL`) mientras el bot permanezca en Render.
    - Detección de IP Pública en Startup: Notificación automática en Telegram con la IP saliente detectada al arrancar el motor.
24. **Conexión de Alta Fidelidad con Google Sheets y Comando /sheets (ADR 024)**:
    - Exportador Multi-Pestaña (`SheetsExporter`): Implementada sincronización en dos pestañas estructuradas:
      1. `Detalle Fiscal`: Órdenes individuales con precio venta, ingreso, costo FIFO, comisiones, tasa oficial BCV y ganancia neta en VES y USD.
      2. `Resumen Ejecutivo`: Métricas agregadas (volumen USDT, ingreso total, costos, comisiones, ganancia neta consolidada, margen % y timestamp de sincronización).
    - Soporte Flexible de Credenciales: Compatibilidad dual con `GOOGLE_SERVICE_ACCOUNT_JSON` (string JSON en variable de entorno para entornos Cloud como Render) y `config/google_credentials.json` (archivo en disco).
    - Interfaz Streamlit & Bot de Telegram: Añadido botón de sincronización de 1-clic y enlace al documento en la pestaña fiscal del Dashboard. Incorporado comando `/sheets` y `/sync_sheets` en `TelegramNotifier` para consultar el enlace directo y disparar la exportación remota.
    - Suite de Pruebas: Ampliada a **51/51 tests pasando al 100%**.
25. **Diagnóstico Detallado de Permisos en Google Sheets y Hoja de Ruta SPEC-013 (ADR 025)**:
    - Diagnóstico de Causa Raíz: Al interactuar con `/sheets` y sincronizar, si la cuenta de servicio de Google no tiene permisos de edición sobre la hoja o falta el archivo de credenciales, el error era genérico y no indicaba la cuenta exacta que requería acceso.
    - Extracción y Exposición de `client_email`: `SheetsExporter` inspecciona las credenciales configuradas (`GOOGLE_SERVICE_ACCOUNT_JSON` o `google_credentials.json`), extrae el correo de la cuenta de servicio (`client_email`) y tipifica los fallos de Google Drive/Sheets API:
      - HTTP 403 (Permiso Denegado): Informa el correo exacto (ej. `bot-p2p@...iam.gserviceaccount.com`) al que se le debe compartir la hoja como "Editor".
      - HTTP 404 (Hoja No Encontrada): Informa que el `sheet_id` configurado no existe o no es accesible.
      - Credenciales Faltantes: Notifica claramente la ausencia de `GOOGLE_SERVICE_ACCOUNT_JSON` o del archivo en disco.
    - Notificación en UI y Telegram: Tanto la respuesta a `/sheets` / `/sync_sheets` como el botón de sincronización en el Dashboard muestran de forma transparente `exporter.last_error`.
    - Formalización de SPEC-013: Creada especificación exhaustiva en `.specify/specs/013-sheets-vps-stitch-enhancements/` abarcando Google Sheets, despliegue VPS para IP Whitelist fija en Binance, modernización con Google Stitch UI (MCP) y monitor de spread P2P vs BCV.
    - Suite de Pruebas: Ampliada a **52/52 tests pasando al 100%**.
26. **Resiliencia de Carga de Configuración en Telegram y Fixture Global CI (ADR 026)**:
    - Diagnóstico de Causa Raíz en CI: Al invocar `/sheets` en entornos sin `config/.env` ni `MASTER_ENCRYPTION_KEY` explícita (como runners efímeros de GitHub Actions), la instanciación de `Settings()` fallaba con `ValueError` por validación de clave maestra, retornando un error genérico ("No se pudo cargar la configuración") en lugar del mensaje específico "Google Sheets no está configurado".
    - Resiliencia y Fallback Suave en `_handle_sheets_sync`: Si `Settings()` falla su validación de arranque, `TelegramNotifier` degrada suavemente a lectura directa de variables de entorno (`os.getenv("GOOGLE_SHEET_ID")`). Si la variable no está presente, devuelve limpiamente el mensaje explicativo para el usuario.
    - Fixture Global en `tests/conftest.py`: Creado fixture autouse que inyecta una clave maestra de prueba cuando no existe en el entorno, protegiendo todos los tests unitarios ejecutados en CI.
    - Suite de Pruebas: Ampliada a **53/53 tests pasando al 100%**.
27. **Fecha/Hora en Detalle Fiscal, Cierre Mensual a Telegram y Verificación de Cédula (ADR 027)**:
    - Inclusión de Fecha y Hora en Detalle Fiscal: `TradeResult` propaga `created_at` desde el modelo `Order` hacia `ExcelReporter` y `SheetsExporter`. Se agregó la columna "Fecha y Hora (UTC)" como primer campo del Detalle Fiscal.
    - Cierre Fiscal Mensual Automatizado (`MonthlyFiscalCloser`): Genera el libro contable de ventas de cualquier mes calendario, calcula métricas acumuladas (órdenes, volumen USDT, ingresos brutos, costos de adquisición FIFO, comisiones, ganancia neta en VES y USD, y margen operativo %).
    - Envío de Documentos Binarios en Telegram: Implementado `send_document()` en `TelegramNotifier` con `multipart/form-data`, reintentos, rate limit (429) y sanitización estricta del caption. Permite al bot despachar el archivo `.xlsx` directamente al chat privado vía comando `/cierre [YYYY-MM]`.
    - Servicio de Identidad con Triple Fallback (`IdentityService`):
      1. Caché Local SQLite (`identities`): Consulta instantánea a 0 ms.
      2. SENIAT XML API (`/getContribuyente/getrif`): Obtención de nombre oficial y RIF.
      3. CNE Scraping (`/web/registro_electoral/ce.php`): Extracción de nombres y apellidos oficiales del registro electoral.
      - Extracción de cédula desde métodos de pago P2P (`extract_cedula_from_payment_details`) con normalización de puntos.
      - Integrado en Telegram (`/cedula V12345678`) y en las herramientas del Asistente de IA de Google Gemini (`consultar_titular_cedula`).
    - Suite de Pruebas: Ampliada a **61/61 tests pasando al 100%**.
28. **Endurecimiento de Pipelines CI/CD, Smoke Testing Operacional y Cumplimiento Legal KYC con Verifik y Didit (ADR 028)**:
    - Rama de Trabajo Dedicada: Creada y conmutada la rama `feature/ci-security-hardening` para aislar los cambios de infraestructura y pipelines.
    - Endurecimiento de `ci.yml`:
      - Permisos de menor privilegio declarados (`permissions: contents: read`).
      - Control de concurrencia (`concurrency: cancel-in-progress: true`) para ahorrar minutos de cómputo en pushes sucesivos.
      - Caché de pip optimizada en todos los jobs (`cache: "pip"`).
      - Exportación de reporte estructurado JUnit XML (`--junitxml=test-results/junit.xml`) y subida automática como artefacto.
    - Endurecimiento Constitucional de `security.yml`:
      - Principio Fail-Closed estricto: Eliminado `continue-on-error: true` de Gitleaks; cualquier secreto detectado bloquea inmediatamente el pipeline.
      - Integrado escaneo SAST semántico oficial de GitHub (**CodeQL**) para Python.
      - `pip-audit` configurado para exportar reporte JSON y fallar la integración si detecta vulnerabilidades con severidad `HIGH` o `CRITICAL`.
      - Permiso explícito `security-events: write` para publicar alertas en la pestaña *Security* de GitHub.
    - Endurecimiento de `cd.yml`:
      - Erradicados los comandos falsos `echo`.
      - Construcción de imágenes Docker con Buildx y escaneo de vulnerabilidades en contenedores con **Aquasecurity Trivy**.
      - Ejecución de Smoke Tests reales mediante `scripts/smoke_test.py` en staging y producción.
      - Reglas de protección de entorno (`environment: production`) con aprobación humana obligatoria (*Manual Approval Gate*).
    - Script de Smoke Testing Autónomo (`scripts/smoke_test.py`):
      - Valida en caliente las primitivas criptográficas (AES-256-GCM y Ed25519).
      - Comprueba la importación limpia del grafo de módulos (`src.core`, `src.security`, `src.reporting`, `src.integrations`).
      - Inicializa esquemas de Base de Datos.
      - Verifica la sincronización horaria contra la API de Binance para prevenir el rechazo `-1021 INVALID_TIMESTAMP`.
      - Verifica el endpoint de salud de Streamlit (`/_stcore/health`).
    - Automatización Preventiva:
      - Creado `.github/dependabot.yml` para actualizaciones semanales automáticas de `github-actions` y dependencias `pip`.
      - Creado `.pre-commit-config.yaml` para validar formato y secretos localmente antes de hacer commit.
    - Cumplimiento Legal y Regulación KYC/AML en `IdentityService`:
      - Descartado y eliminado el enfoque de volcados de padrón electoral (`padron.db`, `scripts/import_padron.py`) por inviabilidad e infracción de leyes de protección de datos (Habeas Data).
      - Integrados proveedores autorizados y regulados de verificación de identidad: **Verifik** (`api.verifik.co`) y **Didit** (`api.didit.me`).
      - Arquitectura en cascada ética y legal: 1) Caché local de contrapartes legítimas, 2) Verifik KYC API, 3) Didit KYC API, 4) SENIAT Oficial RIF, 5) CNE Consulta Ciudadana.
    - Suite de Pruebas: Ampliada y actualizada a **64/64 tests pasando al 100%**.
29. **Reglas Contables y Fiscales para Declaración P2P en Venezuela y Mapeo API Oficial Binance (ADR 029)**:
    - Formalización de Reglas Contables en [`.agents/rules/p2p-fiscal-rules.md`](file:///c:/p2p-bot-merchant/.agents/rules/p2p-fiscal-rules.md):
      - Definidos los 3 reportes base requeridos por Binance My Tax Hub / SUMM: Transaction History, Deposit History y Withdrawal History.
      - Definidas las 6 piezas clave de reconstrucción contable para comerciantes P2P: Saldo inicial, Entradas cripto, Salidas cripto, Volumen operado, Comisiones y Saldo final (verificado mediante la ecuación $\text{Saldo Inicial} + \text{Entradas} - \text{Salidas} = \text{Saldo Final Esperado}$).
      - Definida la conciliación obligatoria con la capa bancaria externa en Venezuela (comprobantes de transferencias y Pago Móvil en VES, tasa oficial diaria del BCV y control de gastos operativos/IGTF).
    - Mapeo oficial contra la Documentación de Desarrolladores de Binance ([developers.binance.com/en/docs/introduction](https://developers.binance.com/en/docs/introduction) y [developers.binance.com/en/docs/catalog](https://developers.binance.com/en/docs/catalog)):
      - Historial de órdenes P2P/C2C: `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory` (Signed `USER_DATA`, paginación en ventanas de 30 días).
      - Historial de depósitos cripto: `GET /sapi/v1/capital/deposit/hisrec` (Signed `USER_DATA`, Weight: 1).
      - Historial de retiros cripto: `GET /sapi/v1/capital/withdraw/history` (Signed `USER_DATA`, Weight: 1).
      - Historial de conversiones spot directas: `GET /sapi/v1/convert/tradeFlow`.
      - Historial de airdrops/recompensas: `GET /sapi/v1/asset/assetDividend`.
      - Balance consolidado de billeteras: `GET /sapi/v1/asset/wallet/balance`.
    - Actualización de reglas globales en [`.agents/rules/global-rules.md`](file:///c:/p2p-bot-merchant/.agents/rules/global-rules.md) y skill [`.agents/skills/binance-p2p/SKILL.md`](file:///c:/p2p-bot-merchant/.agents/skills/binance-p2p/SKILL.md).
30. **Arquitectura de Reconstrucción Fiscal P2P de 6 Piezas, Parser Binance y OCR Bancario Multimodal con Gemini Vision (SPEC-014 / ADR 030)**:
    - Formalización de SDD: Creados los artefactos de especificación [`.specify/specs/014-p2p-fiscal-reconstruction-and-ocr/spec.md`](file:///c:/p2p-bot-merchant/.specify/specs/014-p2p-fiscal-reconstruction-and-ocr/spec.md), [`plan.md`](file:///c:/p2p-bot-merchant/.specify/specs/014-p2p-fiscal-reconstruction-and-ocr/plan.md) y [`tasks.md`](file:///c:/p2p-bot-merchant/.specify/specs/014-p2p-fiscal-reconstruction-and-ocr/tasks.md) estructurados en 6 fases y 18 tareas atómicas TDD.
    - Consenso de Agentes del Sistema:
      - **PM**: Resuelve la conciliación fiscal y la dificultad operativa de procesar comprobantes bancarios en bolívares.
      - **Architect**: Diseña el aislamiento de la ingesta de archivos (`src/core/file_parser.py`), el servicio OCR (`src/integrations/receipt_ocr.py`) y el motor de 6 piezas (`src/reporting/fiscal_reconciler.py`).
      - **Security**: Prohíbe almacenamiento inseguro de comprobantes bancarios y procesa Base64 exclusivamente en búfer de memoria volátil.
      - **Backend**: Establece pruebas unitarias e idempotencia estricta en tablas `wallet_movements`, `bank_vouchers` y `fiscal_period_snapshots`.
      - **Frontend**: Diseña el panel visual de 6 piezas con semáforo de balance y uploader drag-and-drop.
      - **QA**: Valida fixtures basados en los archivos reales exportados de Binance en español.
    - Evaluación de Capacidad de Gemini Vision: Las 3 API keys configuradas en `AIKeyPool` con balanceo round-robin proporcionan 45 peticiones/minuto y 4,500 peticiones/día, superando con creces la carga requerida para el volumen de comprobantes P2P.
31. **Implementación y Cierre de Reconstrucción Fiscal P2P de 6 Piezas, Parser Binance y OCR Multimodal (ADR 031)**:
    - **Ecuación de Consistencia Patrimonial**: Ejecutada en `FiscalReconciler` (`src/reporting/fiscal_reconciler.py`) bajo la fórmula contable estricta: $\text{Saldo Inicial} + \text{Depósitos} + \text{Compras P2P} - \text{Retiros} - \text{Ventas P2P} - \text{Comisiones Cripto} = \text{Saldo Final Esperado}$.
    - **Apertura de Inventario FIFO**: Extensión de `FIFOCostMethod` (`src/reporting/tax_engine.py`) para admitir inventario inicial valorado al tipo de cambio oficial del BCV al primer día del mes, garantizando liquidaciones de costo de adquisición fidedignas ante el SENIAT.
    - **OCR Resiliente con Gemini Vision**: `BankReceiptOCR` (`src/integrations/receipt_ocr.py`) rota automáticamente en fallback (`gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-flash-lite-latest`) y auto-vincula comprobantes de Pago Móvil / Transferencias bancarias con órdenes P2P dentro de una ventana de $\pm 24\text{ h}$ y tolerancia de $\pm 0.05\text{ VES}$.
    - **Exportación Integral de 4 Pestañas**: `ExcelReporter` y `SheetsExporter` sincronizan las 4 hojas de auditoría fiscal (*Resumen Fiscal*, *Detalle P2P*, *Depósitos y Retiros*, y *Conciliación Bancaria*).
    - **Control Visual y Conversacional**: Implementada pestaña interactiva en Streamlit (`fiscal_reconstruction_view.py`) y comando `/conciliacion` junto a procesamiento automático de fotos de comprobantes en Telegram (`TelegramCommandPoller`).
    - **Modernización de Base Declarativa ORM**: Migrado `Base = declarative_base()` a `class Base(DeclarativeBase): pass` en `src/data/database.py`, eliminando falsos positivos en Mypy para todas las clases entidad.
32. **Alineación de Agentes y Arquitectura de Terminal P2P con Tokens de Google Stitch y MCP (ADR 032)**:
    - **Revisión Interdisciplinaria de Fase 3 (SPEC-013)**: Participación activa de `PM`, `Architect`, `Frontend`, `Researcher`, `Security` y `QA` para diseñar la modernización visual y operativa del Dashboard sin comprometer la Constitución Fail-closed.
    - **Expansión de Perfiles de Agente**:
      - `frontend.md`: Especializado en Streamlit 2026 (`width="stretch"`, `st.container(border=True)`, Material Symbols), tokens de diseño Glassmorphism de Google Stitch y arquitectura modular de componentes.
      - `researcher.md`: Especializado en especificaciones de servidores MCP (`mcp_config.json`), protocolos stdio/SSE y documentación técnica de Stitch.
      - `architect.md`: Incorpora gobernanza de sistemas de diseño (`theme.py`), contratos de componentes modulares y desacoplamiento de capas UI/Servicios.
      - `security.md`: Auditoría de sanitización CSS/HTML (`st.html`), control memory-only para subida de comprobantes en UI y prevención de inyección en llamadas de herramientas MCP.
    - **Plan Atómico de Tareas**: Desglose detallado de la Fase 3 en `tasks.md` abarcando configuración de MCP (`T10`), guía de integración (`T11`), theme engine (`T12a`), componentes modulares (`T12b` a `T12e`), refactorización e integración (`T12f`) y cobertura de pruebas unitarias (`T12g`).
33. **Ejecución de Fase 3 (SPEC-013) y Conciliación P2P ante Anonimato de Binance (ADR 033)**:
    - **Diagnóstico de Privacidad en Binance**: Se confirmó que Binance jamás expone la Cédula de Identidad en su API o exportaciones C2C. Para superar esto sin degradar la precisión contable, se implementó un motor de coincidencia multi-criterio:
      1. *Identificador Primario por Monto*: Coincidencia del monto exacto en bolívares (`fiat_amount == amount_ves` con tolerancia $\pm 0.05\text{ VES}$), el cual es altamente específico en operaciones P2P.
      2. *Captura de Contraparte*: Añadida columna `counterparty_name` a `Order` en `src/data/models.py` y parseo en `BinanceFileParser`.
      3. *Desempate Inteligente*: En caso de colisión de montos, el algoritmo compara las palabras clave del nombre y apellido extraídos del comprobante bancario (`sender_name`) contra `counterparty_name` de Binance.
      4. *Blindaje Anti-Terceros*: Cruce con `IdentityService` (SENIAT/CNE) para auditar que la cuenta bancaria pertenezca a la misma persona física.
    - **Cierre de Fase 3 (Terminal P2P Stitch)**:
      - Servidor MCP registrado en `C:\Users\jonan\.gemini\config\mcp_config.json` y documentación en `docs/stitch_mcp_setup.md`.
      - Tema Glassmorphism Obsidian Fintech implementado en `src/reporting/dashboard/theme.py`.
      - Componentes modulares desacoplados: `terminal_header.py`, `kpi_cards.py`, `receipt_center.py` y `ai_telemetry.py`.
      - `app.py` actualizado cumpliendo al 100% los estándares Streamlit 2026.
34. **Rentabilidad Real P2P, Matriz de Arbitraje Interbancario y Compliance Bancario (ADR 034)**:
    - **Fórmula de Rentabilidad Neta Real**: Integrado el cálculo matemático exacto que deduce comisiones invisibles: comisiones de anuncio Binance Maker (0.35% usuario normal hasta 0.15% PRO) y comisiones bancarias interbancarias (0.30% Pago Móvil en compra y venta).
    - **Regla del Spread Mínimo Viable (0.80% en VES)**: Detección proactiva de márgenes deficitarios. Si el spread bruto es menor al 0.80%, el sistema clasifica la operación como `CRITICAL_MARGIN` o `LOSS`.
    - **Servicio `SpreadMonitor` (`src/core/spread_monitor.py`)**:
      - Generación de matriz comparativa por banco en tiempo real (BDV, Banesco, Mercantil, Bancamiga, Pago Móvil, Banco Activo).
      - Algoritmo de arbitraje cruzado óptimo (`find_best_cross_arbitrage`): identifica la combinación más rentable (comprar en banco más barato y vender en el más caro).
      - Cálculo de la brecha cambiaria respecto a la tasa oficial del Banco Central de Venezuela (BCV).
    - **Componentes Visuales en Dashboard (`arbitrage_matrix.py`)**:
      - Incorporada pestaña `:material/candlestick_chart: Monitor & Arbitraje P2P` en `src/reporting/dashboard/app.py`.
      - Matriz interactiva de cotizaciones bancarias con badges semánticos de rentabilidad.
      - Calculadora interactiva de ciclos Maker con desglose al centavo de costos, ROI porcentual y diagnósticos de seguridad.
    - **Dossier Institucional de Compliance Bancario (`ExcelReporter.generate_compliance_report`)**:
      - Generación de informe en Excel con 4 hojas institucionales (*Certificación Institucional*, *Entradas (Ventas P2P)*, *Salidas (Compras P2P)* y *Traza de Conciliación 1 a 1*) diseñado para sustentar fondos ante departamentos de prevención de legitimación de capitales (Compliance) en la banca venezolana.
      - Botón de descarga directa integrado en la pestaña fiscal de la interfaz Streamlit.
    - **Comando `/spread` en Telegram**:
      - Despacho inmediato del resumen de cotizaciones bancarias, arbitraje cruzado y brecha BCV con formato Markdown protegido contra filtraciones.
    - **Calidad y Verificación**: Suite expandida a **99/99 tests pasando al 100%**, Mypy limpio (0 errores en 43 archivos) y Ruff limpio.
35. **Automatización Interactiva de Telegram, Alertas Proactivas BCV/Spread y Compliance en Google Sheets (ADR 035)**:
    - **Google Sheets Compliance Exporter (`SheetsExporter.export_compliance_report`)**:
      - Sincronización completa de las 4 pestañas de auditoría institucional: *Certificación Institucional*, *Entradas*, *Salidas* y *Traza de Conciliación*.
      - Comando `/sheets_compliance` añadido en Telegram para sincronización bajo demanda y diagnóstico de permisos.
    - **Interactividad Enriquecida en Telegram Bot API**:
      - `InlineKeyboardMarkup` con callbacks táctiles en tiempo real para ejecución inmediata de acciones (`/spread`, `/bcv`, `/status`, `/cierre`, `/conciliacion`, `/sheets`, etc.).
      - Manejo de `callback_query` en `TelegramCommandPoller.poll_once()` con llamada a `answerCallbackQuery` para detener el spinner en la app móvil.
      - Teclado persistente `ReplyKeyboardMarkup` para accesibilidad rápida desde dispositivos móviles sin necesidad de escribir comandos de texto.
      - Menú nativo de comandos registrado mediante `set_bot_commands()` (`/setMyCommands`) con descripciones claras.
    - **Monitoreo Proactivo de Tasa BCV y Alertas de Arbitraje (`RateAlertService`)**:
      - Detección inmediata de fluctuaciones en la tasa oficial del Banco Central de Venezuela (`check_bcv_rate_change`) con cálculo de variación absoluta y porcentual.
      - Monitoreo continuo de oportunidades de arbitraje interbancario (`check_spread_opportunities`) con cooldown configurable para evitar spam.
      - Integración directa en el ciclo de ejecución de `P2PBotEngine` (`src/main.py`), despachando alertas prioritarias en background a través de `TelegramQueueDispatcher`.
    - **Calidad y Verificación**:
      - Suite expandida y verificada con **105/105 tests pasando al 100%** (`pytest`).
      - Tipado estricto `mypy src/` limpio (**0 errores en 44 archivos fuente**).
      - Linter estático `ruff check .` (**0 errores de estilo e importaciones**).
36. **Control de Acceso Basado en Roles (RBAC), Aislamiento Visual Estricto y Búsqueda MetaP2P (ADR 036)**:
    - **Aislamiento Multicapa para Invitados**:
      - Los usuarios con rol `INVITADO` tienen acceso restringido única y exclusivamente a cotizaciones públicas y utilitarias: `/spread` y `/bcv`.
      - Prohibición total de acceso a saldos, ganancias netas, órdenes Binance, comprobantes bancarios y consultas de Cédula de Identidad, tanto en Telegram como en el Dashboard Streamlit.
      - Menú persistente en Telegram (`ReplyKeyboardMarkup`) y botones táctiles (`InlineKeyboardMarkup`) adaptados dinámicamente según el rol (solo 3 botones para invitados).
    - **Gestión Dinámica de Acceso y Aprobación Interactiva**:
      - Cuando un usuario no registrado interactúa con el bot, recibe un mensaje de bienvenida informando que su solicitud fue enviada al Administrador.
      - El Administrador recibe de inmediato una notificación con botones táctiles interactivos: `[👁️ Aprobar Invitado]`, `[💼 Aprobar Trader]`, `[⛔ Bloquear]`, permitiendo delegar permisos sin salir de Telegram.
      - Comandos de administración `/usuarios`, `/autorizar` y `/revocar` exclusivos para el rol `ADMIN`.
    - **Conector REST de MetaP2P sin Web Scraping**:
      - El análisis de la arquitectura reveló que MetaP2P opera como una Single Page Application (SPA) sobre la API REST `https://api.metap2p.io/api`.
      - No se requiere emulación con navegadores headless: la autenticación (`POST /api/login`) y la búsqueda de DNI (`GET /api/dni/search`) se ejecutan de manera ultra-rápida y ligera mediante peticiones JSON nativas con `httpx`.
      - Almacenamiento volátil del token de acceso (`access_token`) en memoria RAM y re-autenticación automática ante códigos de error HTTP 401.
    - **Autenticación Web Segura en Streamlit (Obsidian Glassmorphism)**:
      - Implementado `login_view.py` integrado armónicamente con los tokens de diseño Stitch Obsidian Fintech.
      - Protección Fail-closed: si la sesión no está autenticada, `st.stop()` detiene inmediatamente la ejecución de cualquier vista o componente.
      - Renderizado condicional de pestañas según el rol: `INVITADO` únicamente accede a `📈 Monitor & Arbitraje P2P`.
37. **Deduplicación Anti-Spam de Alertas, Arbitraje Cruzado Interbancario Estricto y Directorio Permanente de Cédulas (ADR 037)**:
    - **Deduplicación Inteligente Anti-Spam (`RateAlertService`)**:
      - Se erradicó el reenvío redundante de alertas idénticas cada 10 minutos cuando el mercado no ha cambiado.
      - Ahora se memorizan los últimos precios y spread (`last_arbitrage_buy_rate`, `last_arbitrage_sell_rate`, `last_arbitrage_spread_pct`).
      - La alerta solo vuelve a dispararse si cambia el par de bancos o si, transcurrido el cooldown, las tasas varían al menos $\pm 0.50\text{ VES}$ o el spread porcentual $\ge 0.20\%$.
    - **Arbitraje Interbancario Cruzado Garantizado (`SpreadMonitor`)**:
      - Se corrigió la discrepancia donde un mismo banco con precios extremos (como Banco Activo) se emparejaba consigo mismo ("Comprar en Banco Activo ➔ Vender en Banco Activo").
      - `find_best_cross_arbitrage` evalúa exhaustivamente todas las combinaciones `(q_buy, q_sell)` forzando la condición `q_buy.bank_name != q_sell.bank_name`.
    - **Persistencia Permanente y Directorio de Cédulas en Base de Datos con Trazabilidad (`IdentityRepository`)**:
      - Se implementó `IdentityRepository` para gestionar de forma centralizada, idempotente y permanente la tabla `identities` (`IdentityCache`).
      - Toda consulta a MetaP2P, comprobantes OCR o portales públicos queda resguardada de forma indefinida en la base de datos local para debida diligencia.
      - **Atribución y Trazabilidad de Usuario (`queried_by`)**: Se añade el campo `queried_by` a cada registro para identificar qué usuario o Telegram ID realizó la consulta o registro de la cédula.
      - **Notificación Proactiva al Autorizar/Promover**: Al aprobar o promover a un usuario (como `INVITADO` o `TRADER`) con `/autorizar`, el bot envía automáticamente un mensaje directo de bienvenida con sus opciones habilitadas y teclado interactivo.
      - En Telegram: Nuevo comando `/cedulas` para listar el directorio permanente con indicación de qué usuario guardó cada registro (restringido a `TRADER` y `ADMIN`).
      - En Streamlit: Nueva pestaña `"👤 Directorio Cédulas"` con columna *Consultado Por* y vinculación con la sesión activa del operador.
      - **Navegación Lateral Limpia y Gestión de Perfil en Sidebar**:
        - Se reubicó la lista horizontal de pestañas en un selector vertical limpio en la barra lateral izquierda, justo debajo del perfil activo y el botón de cerrar sesión.
        - Se integró el formulario interactivo **"🔒 Cambiar mi Contraseña"** para cualquier operador autenticado.
        - Se integró el formulario **"👤 Registrar Nuevo Trader"** (exclusivo para `ADMIN`) y la pestaña pública **"📝 Registro de Trader"** en la pantalla inicial de login.
    - **Calidad y Verificación Rigurosa**:
      - **123/123 pruebas unitarias y de integración pasando al 100%** (`pytest`).
      - Tipado estricto `mypy src/` limpio (**0 errores en 48 archivos fuente**).
      - Linter estático `ruff check .` (**0 errores de estilo e importaciones**).

38. **Conexión de Precios en Vivo Binance P2P e Interfaz con Filtros Estilo Binance (ADR 038)**:
    - **Esquemas Tipados Enriquecidos (`binance_schemas.py`)**:
      - Incorporación de `BinanceTradeMethod` para tipar con Pydantic los métodos de pago bancarios (`payType`, `tradeMethodName`, `payId`).
      - Actualización de `BinanceAdDetail` con la lista de `tradeMethods` y propiedad `bank_names` en `BinanceSearchOrderItem` para extracción limpia y sin duplicados de los bancos que acepta cada anuncio.
    - **Conector Universal de Búsqueda P2P (`BinanceP2PClient` y `MockBinanceP2PClient`)**:
      - Firma estandarizada de `search_p2p_ads(asset, fiat, trade_type, pay_types, trans_amount, merchant_check, use_public_bapi)`.
      - Soporte para consulta pública BAPI (`https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search`) y SAPI privada sin consumir peso de API Key para visualización de orderbook.
      - Enriquecimiento de `MockBinanceP2PClient` con bancos reales venezolanos (Banesco, BDV, Pago Móvil, Mercantil, Bancamiga, Provincial, BNC, Banco Activo) y filtrado dinámico por monto y comercios verificados.
    - **Cotizaciones en Vivo en `SpreadMonitor` (`fetch_live_quotes`)**:
      - `SpreadMonitor.fetch_live_quotes()` consulta simultáneamente anuncios BUY y SELL de Binance P2P, extrae la mejor cotización para cada entidad bancaria venezolana y actualiza los diferenciales en tiempo real.
      - Resiliencia Fail-closed: Si la red hacia Binance falla o la conexión es inestable, conmuta de inmediato a las cotizaciones calibradas de respaldo sin detener el sistema.
    - **Interfaz Binance P2P con Filtros en Streamlit (`binance_p2p_book.py`)**:
      - Selector de operación nativo: `Comprar USDT` / `Vender USDT` con `st.segmented_control`.
      - Barra de filtros idéntica a Binance P2P: Criptomoneda (`USDT`, `BTC`, `ETH`, etc.), Moneda Fíat (`VES`, `USD`, `EUR`, `COP`), Monto en Fíat con filtro de límites, Selector de Banco / Método de Pago, y Toggle para Comerciantes Verificados.
      - Renderizado de anuncios estilo Binance con Nickname, % de finalización, precio en grande, límites mínimo/máximo, badges de bancos y simulador de operación integrado con cálculo de comisiones (Binance 0.35% + Bancaria 0.30% Pago Móvil).
      - Integración armónica en la pestaña `📈 Monitor & Arbitraje P2P` mediante navegación interna con `st.segmented_control` entre el Libro de Órdenes, la Matriz de Spreads y la Calculadora Maker.
    - **Calidad y Verificación Rigurosa**:
      - **128/128 pruebas unitarias y de integración pasando al 100%** (`pytest`).
      - Tipado estricto `mypy src/` limpio (**0 errores en 49 archivos fuente**).
      - Linter estático `ruff check .` (**0 errores de estilo e importaciones**).

39. **Resolución de Datos Reales en Vivo Binance P2P vs Simulación en Streamlit (ADR 039)**:
    - **Diagnóstico del Estado Previo**:
      - Al iniciar el Dashboard Streamlit, las cotizaciones y el libro de órdenes se mostraban en modo simulación/calibrado debido a que `USE_SANDBOX=True` estaba fijado en `config/.env` y existía una discrepancia en la importación de `ApiKeyManager` que provocaba un fallback silencioso hacia `MockBinanceP2PClient`.
    - **Conexión Directa a la BAPI Pública Oficial de Binance P2P**:
      - La visualización de anuncios y el análisis del libro de órdenes no requiere permisos privados de trading ni arriesga fondos. Se conectó la BAPI pública (`https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search`) mediante `BinanceP2PClient(..., use_public_bapi=True)`.
      - Se hizo opcional la API Key en `BinanceP2PClient.__init__` para permitir consultas públicas directas.
      - Se corrigió la importación canónica `from src.security.api_key_manager import ApiKeyManager`.
    - **Selectores y Toggles Transparentes en la UI**:
      - **En Libro de Órdenes**: Toggle interactivo `🟢 Mercado Real (Binance P2P)` con selector de anuncios, bancos y simulación. Si la conexión de red falla o se apaga el toggle, conmuta limpiamente a `🧪 Simulación (Sandbox)`.
      - **En Matriz de Spreads & Arbitraje**: Toggle `🟢 Cotizaciones en Vivo (Binance P2P)` que ejecuta `SpreadMonitor.fetch_live_quotes(use_public_bapi=True)` para calcular los spreads, el retorno neto y la mejor oportunidad de arbitraje interbancario con los precios reales de los bancos en Venezuela en ese instante.
    - **Modularización del Entrypoint de Streamlit**:
      - Se aisló la ejecución principal de `src/reporting/dashboard/app.py` dentro de `run_dashboard()` protegido con `if __name__ == "__main__" or st.runtime.exists():`, permitiendo importar funciones de autenticación (`get_visible_tabs_for_role`) en tests sin disparar el runner de UI en modo bare.
    - **Calidad y Verificación**:
      - **128/128 pruebas pasando al 100%**.
      - `mypy src/` limpio (0 errores en 49 archivos).
      - `ruff check .` limpio (0 errores de linting).

40. **Corrección de Método BCV y Conexión de la Matriz de Spreads con Telegram (ADR 040)**:
    - **Corrección de `BCVService`**:
      - Se añadió el método alias `get_official_rate()` en `BCVService` apuntando a `fetch_current_rate()`, erradicando el error `AttributeError` al consultar la tasa oficial en la Matriz de Spreads.
    - **Conexión Directa de la Matriz con Telegram**:
      - **Botón en Streamlit**: En la pestaña *Matriz de Spreads & Arbitraje*, se incorporó la acción interactiva **`📤 Enviar Matriz a Telegram`**, que formatea las cotizaciones actuales de los bancos venezolanos, la brecha cambiaria con el BCV y la mejor oportunidad de arbitraje interbancario, despachándola al instante al chat/canal de Telegram.
      - **Comando `/matriz` en Telegram**: Se agregó el comando `/matriz` (y `/matriz_spreads`), permitiendo a usuarios autorizados (`INVITADO`, `TRADER` y `ADMIN`) recibir el reporte detallado de arbitraje en tiempo real desde Telegram.
      - **Formateador Unificado**: Se implementó `TelegramNotifier.format_arbitrage_matrix_report()` como estándar centralizado de formato para notificaciones web y móviles.
      - **Instanciación Resiliente**: `TelegramNotifier.__init__` ahora cuenta con parámetros por defecto y fallback automático a `Settings()`, facilitando su uso en cualquier componente.
41. **Integración Multifuente de Spreads Bancarios P2P (PitbullChain, Yadio, CriptoYa, Binance P2P BAPI) (ADR 041)**:
    - **Descubrimiento y Arquitectura Multinivel (Failover en Cascada)**:
      - **Nivel 1 (PitbullChain Aggregator API)**: Se integró el consumo directo del endpoint público de PitbullChain (`https://pitbullchain.com/api/p2p/banks?exchange={exchange}`) que mapea en tiempo real los 21 métodos de pago oficiales de Binance P2P en Venezuela (`binanceMethods`), extrayendo cantidad de anuncios activos (`totalAds`), precios promedios de compra/venta, spreads, liquidez de mercado (`liquidityPct`) y puntuación de viabilidad (`score` 0-100).
      - **Nivel 2 (Binance P2P BAPI / SAPI Directo)**: Fallback directo a la API de Binance P2P para consultas por banco individual (`payTypes: [...]`).
      - **Nivel 3 (Ancla Macro Yadio / CriptoYa)**: Consumo de `https://api.yadio.io/rate/VES` y `https://criptoya.com/api/binancep2p/USDT/VES/1` para anclaje de precios de mercado libre y validación cruzada de spreads Maker/Taker.
      - **Nivel 4 (Offline / Fail-closed)**: Cotizaciones calibradas de contingencia.
    - **Enriquecimiento del Dominio de Spreads**:
      - `BankRateQuote` extendido con `total_ads`, `score`, `liquidity_pct`, `binance_code`, `exchanges` y `source`.
      - Mapeo institucional y normalización de nombres bancarios venezolanos (`Banco de Venezuela`, `BNC`, `Banesco`, `Pago Móvil`, `Provincial`, etc.).
    - **Rediseño UI Estilo PitbullChain Pro en Streamlit**:
      - Selector de Exchange (Binance P2P, Bybit P2P, Todos los Exchanges).
      - Filtro interactivo por entidad bancaria.
      - Tabla enriquecida con Ranking, Código Binance, Anuncios detectados, Precios Maker compra/venta, Spread en Bs y %, Score de rentabilidad (0-100), Liquidez (%) y Etiquetas de Exchanges.
      - Indicador visual dinámico de la fuente de datos (`PitbullChain Live`, `Binance Direct`, `Yadio Macro`, `Calibrado`).
    - **Verificación en Vivo y Calidad**:
      - Se ejecutaron consultas en vivo a cada una de las 4 fuentes (PitbullChain, Yadio, CriptoYa, Binance P2P BAPI), verificando respuesta HTTP 200 y extracción de datos reales.
      - **133/133 pruebas pasando al 100%** (`pytest`).
      - `mypy src/` limpio (0 errores en 49 archivos fuente).
      - `ruff check .` limpio (0 errores de linting).

---

## 🎯 Guía Operativa Actual

1. **Dashboard y Panel de Control**: `streamlit run src/reporting/dashboard/app.py` o `make dashboard`.
2. **Motor en Terminal (Opcional)**: `python -m src.main` o `make run` (opera en bucle continuo emitiendo alertas y respondiendo comandos).
3. **Smoke Tests Operacionales**: `python scripts/smoke_test.py --stage=local`.
4. **Suite de Pruebas**: `pytest -v tests/` (**133/133 tests pasando al 100%**).
5. **Comprobación de Calidad de Código**:
   - `mypy src/` (0 errores en 49 archivos fuente).
   - `ruff check .` (0 errores de linting).