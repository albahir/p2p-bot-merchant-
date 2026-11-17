# SURVEY REPORT: Estándares de Especificación, Arquitectura y Propuesta de Integración para el Paquete de Predicción Macro de IA en `p2p-bot-merchant`

**Fecha**: 2026-11-17  
**Autor**: Explorer 3 (Spec Miner & Standards Specialist)  
**Entorno de Trabajo**: `c:\p2p-bot-merchant`  
**Referencia del Requerimiento**: `c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md`  
**Destinatario**: Parent Orchestrator (`fefc4a8c-cb37-4d70-9d05-32d746794690`)

---

## 1. Resumen Ejecutivo

Este informe documenta la investigación exhaustiva sobre los estándares de especificación (`.specify/`), memoria persistente (`memory.md`, `.specify/memory/constitution.md`), reglas de arquitectura (`AGENTS.md`) y el código base existente en `p2p-bot-merchant`.

El objetivo es sentar las bases normativas, arquitectónicas y técnicas para integrar el nuevo **Sistema de Predicción Macroeconómica de USDT con IA**, basado en una arquitectura tolerante a fallos con balanceo Round-Robin multi-proveedor y una cadena de tres roles especializados:
1. **Rol Buscador / Recopilador**: Extracción y estructuración de noticias y variables macroeconómicas de Venezuela (intervenciones cambiarias del BCV, emisión de liquidez monetaria M2, cronogramas de nóminas del Estado y bonos Patria, anuncios regulatorios).
2. **Rol Analista / Predictor**: Modelo de razonamiento económico que deduce la dirección de la tasa USDT/VES (subirá, bajará o neutral), el lapso o ventana temporal estimada y el porcentaje de confiabilidad.
3. **Rol Revisor / Auditor**: Validador crítico y filtro de coherencia que somete la predicción a contraste metodológico antes de su emisión, impidiendo alucinaciones o proyecciones sin sustento empírico.

---

## 2. Inventario y Análisis del Repositorio de Especificaciones (`.specify/`)

### 2.1. Estructura de Directorios en `.specify/`
La carpeta `.specify/` sigue una disciplina estricta de Spec-Driven Development (SDD):
- `.specify/memory/`: Contiene `constitution.md`, el documento supremo que define los 9 principios innegociables del proyecto.
- `.specify/templates/`: Contiene las plantillas canónicas:
  - `spec-template.md`: Define la estructura `## QUÉ`, `## Requisitos Funcionales` (RF-01...), `## Requisitos No Funcionales` (RNF-01...), `## Criterios de Aceptación`.
  - `plan-template.md`: Define `## Stack`, `## Arquitectura`, `## Decisiones`, `## Dependencias`.
  - `tasks-template.md`: Define la lista atómica de tareas `T-[Número].X` con archivos específicos y pruebas TDD.
- `.specify/scripts/`: Scripts de automatización y validación:
  - `validate-spec.ps1` / `validate-spec.sh`: Validador automatizado que itera por cada subdirectorio en `.specify/specs/` y **falla de forma estricta (exit 1)** si falta alguno de los 3 archivos: `spec.md`, `plan.md` o `tasks.md`.
- `.specify/specs/`: Repositorio ordenado de paquetes de especificación.

### 2.2. Registro Histórico de Especificaciones Existentes

| Especificación | Nombre del Paquete | Estado | Resumen Funcional |
|---|---|---|---|
| `001-security-foundation` | Fundación de Seguridad | Completado | Cifrado AES-256-GCM, auditoría append-only SHA-256, whitelist IP. |
| `002-binance-connector` | Conector Binance P2P | Completado | Cliente oficial Ed25519/HMAC, monitor de weight, límite 30 días. |
| *003-pricing* | Motor de Estrategias / Pricing | **Pausado** | Pricing algorítmico automatizado (pausado por el usuario). |
| *004-banking* | Verificación Bancaria | **Pausado** | Conexión con bancos locales / Open Banking (pausado por el usuario). |
| `005-tax-engine` | Motor Fiscal e Historial | Completado | FIFO, Costo Promedio Ponderado, tasa BCV, exportador Excel 2 pestañas. |
| `006-telegram-notifications`| Notificaciones Telegram | Completado | Alertas sanitizadas y comandos `/status`, `/pause`, `/resume`, `/report`. |
| `007-dashboard-reporting` | Dashboard y Reportes | Completado | Dashboard Streamlit base con KPIs, órdenes y auditoría. |
| `008-ci-cd-infra` | CI/CD e Infraestructura | Completado | GitHub Actions, Dockerfiles y Docker Compose. |
| `009-control-panel-ui` | Panel de Control UI | Completado | Mission Control en Streamlit sin comandos de consola. |
| `010-api-security-and-resilience` | Seguridad API y Resiliencia | Completado | Esquemas Pydantic, compensación de clock drift, SyncLock mutex. |
| `011-telegram-resilience-and-sandbox-ops` | Resiliencia Telegram & Sandbox | Completado | Proxy SOCKS5/HTTP, cola en background, poller long-polling. |
| `012-ai-assistant-telegram` | Asistente de IA en Telegram | Completado | Gemini Function Calling de solo lectura, `AIKeyPool` con Round-Robin. |
| `013-sheets-vps-stitch-enhancements` | Google Sheets & VPS | Completado | Sincronización multi-pestaña, hoja de ruta VPS IP fija. |
| `014-p2p-fiscal-reconstruction-and-ocr` | Reconstrucción Fiscal 6 Piezas | Completado | OCR de comprobantes con Gemini Vision, matching multi-factor. |
| `015-multiuser-rbac-and-metap2p` | RBAC Multi-Usuario & MetaP2P | Completado | Roles ADMIN/TRADER/INVITADO, MetaP2P, hashes PBKDF2. |
| `016-p2p-live-orderbook-and-binance-ui` | Live Orderbook Binance | Completado | Visualización en vivo del libro P2P y cálculo de spreads. |
| `017-p2p-accounting-journal-and-reconciliation` | Contabilidad SENIAT | Completado | Libro Diario SHA-256, Libro Mayor, régimen Fecha Valor BCV. |
| `018-live-reconciliation-and-ux-automation` | Conciliación en Vivo | Completado | Automatización contable y reconciliación instantánea. |
| *019-trader-roles* | Preservación de Roles | Completado | Persistencia de roles de traders en `memory.md` y volúmenes Docker. |
| `020-stitch-institutional-ui-overhaul` | P2P Merchant OS (8 Pantallas) | Completado | Migración a interfaz Next.js Obsidian Amber Gold. |
| `021-e2e-user-simulation-and-hardening` | Simulación E2E & Hardening | Completado | Suite de simulación humana E2E, blindaje de contraseñas. |
| `022-multi-tenant-privacy-and-ux-overhaul` | Aislamiento Confidencial | Completado | Aislamiento estricto Admin/Trader, vista dual de spreads. |

### 2.3. Asignación del Número de Especificación para la Predicción con IA

Se analizaron dos alternativas técnicas:
1. **Reutilizar / Despausar Paquete 003 (`003-ai-macro-pricing`)**:
   - *Ventaja aparente*: Unificar la inteligencia de mercado con el pricing.
   - *Desventajas críticas*: Viola la Constitución del proyecto y la trazabilidad histórica de `memory.md`. En `AGENTS.md` y `memory.md`, el paquete 003 representa un motor de trading algorítmico automatizado (creación/actualización de anuncios en Binance P2P vía API) que fue explícitamente **pausado por decisión del usuario**. Sobre-escribir el 003 alteraría el alcance del sistema y mezclaría un sistema de recomendación macroeconómica (Advisory/Intelligence) con ejecución directa de órdenes.
2. **Asignar la Siguiente Especificación Secuencial: `023-ai-market-predictor`**:
   - *Fundamento normativo*: La secuencia histórica del repositorio alcanza actualmente hasta `022-multi-tenant-privacy-and-ux-overhaul`. Asignar el número **023** respeta el principio de monotonicidad y el registro append-only de `memory.md`.
   - *Relación con 003*: `023-ai-market-predictor` opera como un subsistema de inteligencia macroeconómica independiente y desacoplado. En el futuro, si el usuario decide reactivar el Paquete 003, el motor de pricing consumirá las predicciones emitidas por la Spec 023 como un parámetro de entrada de ponderación de riesgo cambiario.
   - **Veredicto Definitivo**: El nuevo paquete DEBE denominarse **`023-ai-market-predictor`** (o `023-ai-macro-market-predictor`).

---

## 3. Principios Constitucionales y Reglas de la Arquitectura

La especificación e implementación del paquete 023 debe satisfacer sin excepción los 9 mandatos de `.specify/memory/constitution.md` y las directivas de `AGENTS.md`:

1. **Principio Fail-Closed (Mandato #2)**:
   - Si las fuentes de noticias no responden, si el extractor no detecta datos confiables, o si los LLMs entran en discrepancia o saturación de cuotas, el sistema **nunca debe emitir una predicción aleatoria o desinformada**.
   - Ante cualquier ambigüedad, el estado resultante se marca como `NEUTRAL / INDETERMINADO` con flag de advertencia y se notifica al operador.
2. **Ciclo TDD Obligatorio (Test-Driven Development)**:
   - Primero se crea la suite de pruebas unitarias e integración en rojo (`tests/unit/test_ai_market_predictor.py`, `tests/integration/test_macro_pipeline.py`) verificando el pipeline con mocks de noticias y respuestas de LLMs.
   - Una vez confirmado el fallo esperado en rojo, se implementa el código en verde (`src/core/macro/`).
3. **Cero Secretos en Logs, Código y UI (Mandato #8)**:
   - Prohibido registrar API Keys de Google Gemini, Groq, OpenAI o tokens en logs, excepciones o respuestas salientes.
   - Las salidas deben filtrarse con `sanitize_message()`.
   - Las llaves en el pool deben mostrarse enmascaradas (`AIzaSy...7GBE`).
4. **Trazabilidad Total y Encadenamiento SHA-256 (Mandato #4)**:
   - Cada predicción emitida por el pipeline debe registrarse en la base de datos (`macro_predictions`) incluyendo:
     - Timestamp UTC
     - Snapshot de las variables y noticias analizadas
     - Salida del Predictor y dictamen del Revisor
     - `prev_hash` y `prediction_hash` calculados con SHA-256 encadenado.
5. **Separación Estricta de Responsabilidades (Mandato #6)**:
   - El pipeline de IA (`src/core/macro/`) no interactúa directamente con la interfaz visual.
   - Expone métodos desacoplados e inyectables que son consumidos por Telegram (`src/integrations/`), el Dashboard Streamlit (`src/reporting/dashboard/`) y los endpoints de la API REST (`src/api/routes/`).

---

## 4. Encaje del Sistema en la Arquitectura de `p2p-bot-merchant`

### 4.1. Módulos Involucrados y Contratos de Interfaz

```
                       ┌──────────────────────────────────────────────┐
                       │           FUENTES MACRO EXTERNAS             │
                       │ (BCV, Gaceta Oficial, M2, Medios Económicos) │
                       └──────────────────────┬───────────────────────┘
                                              │ HTTP Scraping / RSS / API
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           src/core/macro/ (PAQUETE 023)                             │
│                                                                                     │
│  ┌────────────────────────┐       ┌──────────────────────┐                          │
│  │  MacroContextExtractor │ ----> │   MacroContextData   │                          │
│  └────────────────────────┘       └──────────┬───────────┘                          │
│                                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │             RoundRobinLLMEngine (Gemini Flash Lite / Groq / OpenAI)           │  │
│  └───────────────────────┬───────────────────────────────┬───────────────────────┘  │
│                          │                               │                          │
│                          ▼                               ▼                          │
│               ┌──────────────────────┐        ┌──────────────────────┐              │
│               │   AnalystPredictor   │ -----> │   PredictionReviewer │              │
│               │ (BULLISH/BEARISH/...)│        │ (Validación Crítica) │              │
│               └──────────────────────┘        └──────────┬───────────┘              │
│                                                          ▼                          │
│                                               ┌──────────────────────┐              │
│                                               │   FinalPrediction    │              │
│                                               └──────────┬───────────┘              │
└──────────────────────────────────────────────────────────┼──────────────────────────┘
                                                           │
        ┌───────────────────────────┬──────────────────────┴────────────────────┐
        ▼                           ▼                                           ▼
┌─────────────────┐       ┌────────────────────┐                     ┌────────────────────┐
│  src/security/  │       │ src/integrations/  │                     │   src/reporting/   │
│                 │       │                    │                     │     dashboard/     │
│   AuditLogger   │       │ TelegramNotifier   │                     │                    │
│   (SHA-256      │       │ • Alerta Push      │                     │ Streamlit Tab:     │
│   Append-Only)  │       │ • Tool para Agente │                     │ • Gauge Sentimiento│
│                 │       │   Conversacional   │                     │ • Tabla Predicción │
│                 │       │   (/prediccion)    │                     │ • Trazabilidad     │
└─────────────────┘       └────────────────────┘                     └────────────────────┘
```

### 4.2. Contratos de Datos (Pydantic Models)

#### Contrato 1: Contexto Macroeconómico Estructurado
```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class MacroEventType(str, Enum):
    BCV_INTERVENTION = "BCV_INTERVENTION"     # Inyección o recorte de divisas a la banca
    PAYROLL_BONUS = "PAYROLL_BONUS"           # Pagos nómina pública / Sistema Patria
    LIQUIDITY_EXPANSION = "LIQUIDITY_EXPANSION"# Emisión monetaria M2
    REGULATORY_POLICY = "REGULATORY_POLICY"   # Encaje legal, límites bancarios, tributos
    MARKET_SENTIMENT = "MARKET_SENTIMENT"     # Brecha cambiaria, noticias generales

class MacroNewsItem(BaseModel):
    title: str
    source: str
    published_at: datetime
    summary: str
    category: MacroEventType
    impact_weight: float = Field(ge=0.0, le=1.0) # Relevancia estimada

class MacroContextData(BaseModel):
    timestamp: datetime
    bcv_official_rate: float
    current_p2p_rate: float
    official_spread_pct: float
    recent_events: list[MacroNewsItem]
    m2_expansion_detected: bool
    bcv_weekly_intervention_usd: float | None
```

#### Contrato 2: Predicción de Mercado
```python
class MarketDirection(str, Enum):
    BULLISH = "BULLISH"   # USDT/VES subirá (depreciación del VES)
    BEARISH = "BEARISH"   # USDT/VES bajará (apreciación temporal o contención del VES)
    NEUTRAL = "NEUTRAL"   # Mercado lateral / equilibrio

class TimeHorizon(str, Enum):
    INMEDIATO = "INMEDIATO"       # < 12 horas
    CORTO_PLAZO = "CORTO_PLAZO"   # 24 a 48 horas
    MEDIANO_PLAZO = "MEDIANO_PLAZO" # 3 a 7 días

class PredictionResult(BaseModel):
    direction: MarketDirection
    horizon: TimeHorizon
    confidence_pct: float = Field(ge=0.0, le=100.0)
    key_drivers: list[str]
    causal_explanation: str
    recommended_stance: str
    reviewer_status: str # "APPROVED" o "DISCREPANCY_FLAGGED"
    reviewer_notes: str
    engine_model_used: str
    prediction_hash: str
```

---

## 5. Diseño Estructural e Índice para los 3 Artefactos de la Spec 023

A continuación se define la estructura exacta que deben contener `spec.md`, `plan.md` y `tasks.md` dentro de `.specify/specs/023-ai-market-predictor/`:

### 5.1. Esquema de `spec.md`
```markdown
# Spec 023: Sistema de Predicción Macroeconómica de USDT con IA Tolerante a Fallos

## 1. Visión General y Propósito (QUÉ)
## 2. Historias de Usuario
- HU-01: Alerta Proactiva de Presión Cambiaria para el Comerciante P2P.
- HU-02: Consulta en Lenguaje Natural de la Tendencia Macroeconómica vía Telegram.
- HU-03: Visualización en el Dashboard de Factores Macroeconómicos y Confianza.
- HU-04: Auditoría Inmutable de Predicciones y Rendimiento del Modelo.

## 3. Requisitos Funcionales
- RF-01: Extracción Automatizada de Contexto Macroeconómico de Venezuela.
- RF-02: Pipeline Multi-Rol de Razonamiento (Buscador -> Analista -> Revisor).
- RF-03: Formulación Direccional, Lapso Temporal y Métrica de Confiabilidad.
- RF-04: Estrategia de Balanceo Round-Robin Multi-Clave y Multi-Proveedor LLM.
- RF-05: Protocolo de Validación y Filtro Crítico Anti-Alucinación (Revisor).
- RF-06: Persistencia y Trazabilidad Criptográfica SHA-256 en Base de Datos.
- RF-07: Integración con el Bot de Telegram (Alertas Push y Comando /prediccion).
- RF-08: Integración con Dashboard Streamlit (Pestaña Inteligencia Macro).
- RF-09: Exposición de Métricas y Estado en la API REST FastAPI.

## 4. Requisitos No Funcionales
- RNF-01: Comportamiento Fail-Closed ante Caída de Modelos o Datos Incompletos.
- RNF-02: Cero Secretos en Logs y Mensajes (Sanitización con sanitize_message).
- RNF-03: Latencia Máxima del Pipeline Completo (< 15 segundos).
- RNF-04: Disponibilidad Continua mediante Rotación Activa de Proveedores.

## 5. Criterios de Aceptación
- AC-01..AC-08 (Pruebas unitarias, de integración, cobertura y validación).
```

### 5.2. Esquema de `plan.md`
```markdown
# Plan de Arquitectura 023: Sistema de Predicción Macroeconómica con IA

## 1. Stack Técnico
- Python 3.12+, Pydantic v2, HTTPX, BeautifulSoup4 / Feedparser.
- LLMs: Google Gemini 2.5 Flash / Flash Lite (SDK / REST), Groq (Llama-3.3-70B), OpenAI GPT-4o-mini (Fallback).
- Persistencia: SQLAlchemy, SQLite local y PostgreSQL (Neon).

## 2. Diagramas de Secuencia y Arquitectura
- Diagrama de flujo de datos del Pipeline Multi-Rol.
- Diagrama de secuencia del Balanceador Round-Robin con Cooldown y Failover.

## 3. Especificación de los 3 Roles del Pipeline
- Rol 1: Macro Context Extractor & Structurer (System Prompt, Inputs, Output Schema).
- Rol 2: Economic Analyst & Market Predictor (System Prompt, Deducción Económica, Output Schema).
- Rol 3: Independent Prediction Reviewer (System Prompt, Matriz de Coherencia, Aprobación/Rechazo).

## 4. Estrategia Round-Robin Multi-Proveedor y Gestión de Cuotas
- Expansión de AIKeyPool para soportar múltiples proveedores (Gemini, Groq, OpenAI).
- Manejo de Códigos HTTP 429, 503, 500 y timeouts con enfriamiento dinámico.

## 5. Modelos de Base de Datos y Repositorios
- Tabla `macro_events` y `macro_predictions`.
- Hash encadenado SHA-256 (`prev_hash`, `prediction_hash`).

## 6. Puntos de Integración con Módulos Existentes
- Integración en `src/integrations/telegram_notifier.py` y `ai_assistant.py`.
- Integración en `src/reporting/dashboard/` (componente `macro_intelligence.py`).
- Integración en `src/api/routes/macro.py` (FastAPI).
```

### 5.3. Esquema de `tasks.md`
```markdown
# Tasks 023: Sistema de Predicción Macroeconómica con IA

## Fase 1: Setup, Modelos de Datos y Pruebas Iniciales (TDD Red)
- [ ] T23.1: Crear tests unitarios en rojo para contratos Pydantic y modelos SQLAlchemy (`tests/unit/test_macro_models.py`).
- [ ] T23.2: Definir esquemas Pydantic `MacroNewsItem`, `MacroContextData`, `PredictionResult` en `src/core/macro/schemas.py`.
- [ ] T23.3: Crear modelos SQLAlchemy `MacroEvent` y `MacroPrediction` con hash SHA-256 en `src/data/models.py` e inicializar en `init_db()`.
- [ ] T23.4: Implementar `MacroRepository` en `src/data/repositories.py` con operaciones de inserción idempotente y consulta cronológica.

## Fase 2: Macro Context Extractor & Structurer
- [ ] T23.5: Crear tests unitarios en rojo para scraping y clasificación de noticias macroeconómicas (`tests/unit/test_macro_extractor.py`).
- [ ] T23.6: Implementar `MacroContextExtractor` en `src/core/macro/extractor.py` con conectores para BCV, noticias de liquidez y eventos de nómina/bonos.
- [ ] T23.7: Implementar sanitizador y normalizador de texto sucio para fuentes de noticias locales en `src/core/macro/normalizer.py`.

## Fase 3: Multi-Provider LLM & Round-Robin Engine
- [ ] T23.8: Crear tests unitarios en rojo para el motor multi-proveedor con failover y rotación (`tests/unit/test_multi_llm_engine.py`).
- [ ] T23.9: Extender `AIKeyPool` para soportar perfiles multi-proveedor (Google Gemini, Groq, OpenAI) en `src/core/macro/llm_engine.py`.
- [ ] T23.10: Implementar gestión de cooldown, balanceo Round-Robin proactivo y telemetría de cuotas por proveedor.

## Fase 4: Pipeline de Predicción y Revisión (Analyst + Reviewer)
- [ ] T23.11: Crear tests unitarios en rojo para el pipeline de predicción y validación cruzada (`tests/unit/test_prediction_pipeline.py`).
- [ ] T23.12: Implementar `MacroAnalystPredictor` en `src/core/macro/analyst.py` con system prompt especializado en economía venezolana.
- [ ] T23.13: Implementar `PredictionReviewer` en `src/core/macro/reviewer.py` con reglas de validación lógica, veto de alucinaciones y cálculo de discrepancias.
- [ ] T23.14: Crear la clase orquestadora `MacroPredictionPipeline` en `src/core/macro/pipeline.py` uniendo extractor, predictor y revisor.

## Fase 5: Integraciones (Telegram, Dashboard Streamlit y API REST)
- [ ] T23.15: Crear tests de integración para alertas de Telegram y comandos (`tests/unit/test_macro_telegram.py`).
- [ ] T23.16: Integrar comando `/prediccion` y tool de consulta en `src/integrations/ai_assistant.py` y alertas push en `src/integrations/telegram_notifier.py`.
- [ ] T23.17: Implementar componente visual `render_macro_intelligence` en `src/reporting/dashboard/components/macro_intelligence.py` e integrarlo en `app.py`.
- [ ] T23.18: Crear endpoints REST `GET /api/macro/prediction`, `GET /api/macro/events` en `src/api/routes/macro.py`.

## Fase 6: Verificación Integral, Hardening y Documentación
- [ ] T23.19: Ejecutar suite de pruebas completa (`pytest tests/`), linter (`ruff check .`), typecheck (`mypy src/`) y escaneo de seguridad (`security-review`).
- [ ] T23.20: Validar la especificación con `.specify/scripts/validate-spec.ps1` y actualizar `memory.md` con el estado final del Paquete 023.
```

---

## 6. Tabla de Características Descubiertas (Features Discovered)

| # | Categoría | Característica | Descripción | Entradas | Salidas | Comportamiento ante Error | Descubierto Vía |
|---|---|---|---|---|---|---|---|
| 1 | Especificación | Validador SDD | Script PowerShell y Bash que valida que cada spec tenga `spec.md`, `plan.md` y `tasks.md`. | Ruta `.specify/specs/` | Éxito o Exit 1 | Termina el script con error si falta algún archivo. | `.specify/scripts/validate-spec.ps1` |
| 2 | Especificación | Plantillas Estándar | Estructura formal obligatoria de requerimientos, planes técnicos y tareas atómicas. | Plantillas en `.specify/templates/` | Documentos formateados | N/A | `.specify/templates/*.md` |
| 3 | Memoria & Principios | Constitución de 9 Principios | Reglas supremas del repositorio: Fail-closed, TDD, Cero Secretos, Respeto de Peso API, Trazabilidad SHA-256. | Políticas de desarrollo | Cumplimiento del bot | Bloqueo o parada preventiva ante violación. | `.specify/memory/constitution.md` |
| 4 | Resiliencia IA | AIKeyPool Round-Robin | Balanceador dinámico de claves de Gemini con rotación proactiva y enfriamiento automático ante 429/503. | String de claves separadas por coma | Siguiente clave disponible | Retorna clave que expire primero si todas están en cooldown. | `src/integrations/ai_assistant.py:209` |
| 5 | Asistente Conversacional | TelegramAIAgent & Tools | Function Calling de solo lectura hacia base de datos, motor fiscal y tasas BCV. | Mensaje de texto libre en Telegram | Respuesta markdown sanitizada | Responde mensaje de error limpio sin bloquear Telegram. | `src/integrations/ai_assistant.py:361` |
| 6 | Integridad & Auditoría | AuditLogger SHA-256 | Registro append-only de eventos con encadenamiento criptográfico (`prev_hash` \| `payload` -> `event_hash`). | Evento, IP, estado, identificador | Registro en `security_events` | Fallo de base de datos genera excepción controlada. | `src/security/audit_logger.py` |
| 7 | Contabilidad | Partida Doble SHA-256 | Asientos contables con balance estricto Debe=Haber y hash encadenado por entrada. | Vouchers, órdenes, saldos | Registro en `journal_entries` | Bloqueo si el balance no cuadra. | `src/reporting/accounting_engine.py` |
| 8 | Monitoreo de Mercado | RateAlertService | Monitor de cambios de tasa oficial BCV con protección anti-flapping y Fecha Valor. | Tasa BCV y fecha valor | Alerta formatada para Telegram | Ignora tasas inválidas (`<= 0`). | `src/core/rate_alert_service.py` |
| 9 | Monitoreo de Spreads | SpreadMonitor & Orderbook | Extracción del libro P2P Binance filtrado por banco, volumen y comerciante verificado. | Parámetros de búsqueda | Libro estructurado y spreads | Fallback a caché TTL de 12 segundos. | `src/core/spread_monitor.py` |
| 10 | Interfaz Operativa | Dashboard Streamlit RBAC | Panel de 8-11 pestañas con renderizado condicional según rol (ADMIN, TRADER, INVITADO). | Sesión de usuario / Token | Vistas y componentes reactivos | Redirección a login o vista reducida para invitados. | `src/reporting/dashboard/app.py` |

---

## 7. Casos Extremos Observados (Edge Cases)

| # | Característica | Entrada / Escenario | Comportamiento Observado / Esperado |
|---|---|---|---|
| 1 | Extracción de Noticias | Portal del BCV o medio local inaccesible (HTTP 500, timeout, SSL corrupto). | El extractor captura la excepción de red, omite la fuente caída y utiliza las fuentes secundarias disponibles; si ninguna responde, activa flag `DATA_UNAVAILABLE` sin inventar noticias. |
| 2 | Rotación de Claves IA | Todas las claves de Gemini en el pool reciben HTTP 429 simultáneamente. | `AIKeyPool.get_next_key()` selecciona la clave cuyo cooldown esté más próximo a vencer, evitando bloqueo nulo y esperando liberación. |
| 3 | Discrepancia Predictor vs Revisor | El Predictor proyecta `BULLISH (95%)` pero el Revisor detecta contradicción con intervención bancaria inminente. | El Revisor marca el status como `DISCREPANCY_FLAGGED`, reduce la confianza calculada y añade notas de advertencia en la justificación. |
| 4 | Mensaje Saliente con Secretos | La respuesta generada por el LLM incluye accidentalmente una API Key o hash. | `sanitize_message()` ejecuta sustitución regex reemplazando cualquier patrón de token por `[REDACTED]`. |
| 5 | Pausa Fail-Closed Activa | El bot está en estado de pausa por error 401 de Binance o fallo crítico. | El sistema de predicción macroeconómica sigue funcionando en modo consulta/advisory, pero indica en su salida que el trading del bot está actualmente suspendido. |
