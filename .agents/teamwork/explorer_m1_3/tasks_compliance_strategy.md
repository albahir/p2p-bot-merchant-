# ESTRATEGIA DE TAREAS Y CUMPLIMIENTO SDD: ESPECIFICACIÓN 023 (AI MARKET PREDICTOR)

**Documento:** `tasks_compliance_strategy.md`  
**Autor:** Explorer M1_3 — Tasks & SDD Compliance Planner  
**Fecha:** 17 de Noviembre de 2026  
**Entorno de Trabajo:** `c:\p2p-bot-merchant`  
**Paquete:** `023-ai-market-predictor`  
**Destinatario:** Parent Orchestrator (`fefc4a8c-cb37-4d70-9d05-32d746794690`) & Worker de Implementación  

---

## 1. Resumen Ejecutivo y Marco Normativo SDD

El presente documento establece el blueprint técnico definitivo, la secuencia ordenada de tareas atómicas y la estrategia de cumplimiento metodológico para que el Agente Worker cree y verifique los siguientes artefactos:
1. `.specify/specs/023-ai-market-predictor/tasks.md`: Desglose secuencial de 26 tareas atómicas con checkboxes `[ ]`, organizadas en 6 fases según el ciclo TDD (Rojo ➔ Verde ➔ Refactor) y los principios constitucionales del proyecto.
2. `memory.md`: Registro formal e inmutable del **Paquete 023** en el inventario de paquetes y registro del **ADR 056** en la cronología de decisiones arquitectónicas, preservando la monotonicidad histórica sin alterar registros previos.
3. Validación de Conformidad SDD: Protocolo de ejecución y verificación con `.specify\scripts\validate-spec.ps1` y suite de pruebas del proyecto.

### 1.1 Jerarquía de Contratos del Proyecto
De acuerdo con la Constitución (`.specify/memory/constitution.md`) y `AGENTS.md`, todo desarrollo en `p2p-bot-merchant` sigue el flujo:
$$\text{constitution.md} \longrightarrow \text{spec.md} \longrightarrow \text{plan.md} \longrightarrow \text{tasks.md} \longrightarrow \text{TDD Code Implementation}$$

El Paquete 023 opera como un subsistema de **Inteligencia y Recomendación Macroeconómica (Advisory / Market Intelligence)**, completamente desacoplado del motor de pricing algorítmico (Paquete 003, actualmente pausado por decisión del usuario).

---

## 2. Blueprint Completo para `.specify/specs/023-ai-market-predictor/tasks.md`

El archivo `.specify/specs/023-ai-market-predictor/tasks.md` debe ser creado con el contenido exacto y estructurado que se detalla a continuación.

```markdown
# Tasks: SPEC-023 Sistema de Inteligencia Macroeconómica y Predicción de Mercado USDT con IA Tolerante a Fallos

## Fase 1: Setup, Contratos de Datos y Pruebas Unitarias de Modelos (TDD Red)
- [ ] T23.1: Crear tests unitarios en rojo para esquemas Pydantic v2 en `tests/unit/test_macro_schemas.py`, validando:
  - Enumeraciones estrictas: `MacroEventType` (14 categorías normalizadas), `MarketDirection` (BULLISH, BEARISH, NEUTRAL), `TimeHorizon` (INMEDIATO_12H, CORTO_24_48H, MEDIANO_3_5D, SEMANAL), `ReviewVerdict` (APROBADO, RECHAZADO, AJUSTADO_FAIL_CLOSED) y `ModelProvider` (GEMINI, GROQ, DEEPSEEK, OPENAI, ANTHROPIC).
  - Validación de rangos numéricos: `impact_weight` (0.0 a 1.0), `confidence_pct` (0.0 a 100.0), `credibility_score` (0.0 a 1.0).
  - Serialización y deserialización JSON sin pérdida de precisión ni timezone drift en timestamps UTC.
- [ ] T23.2: Implementar esquemas Pydantic v2 en `src/core/macro/schemas.py`:
  - `MacroEventItem`: modelo de evento individual con campos `id`, `event_code`, `category`, `title`, `summary`, `source`, `source_url`, `published_at`, `impact_weight`, `transmission_lag_hours`, `verified`.
  - `MacroContextPayload`: contenedor consolidado con `events`, `bcv_official_rate`, `current_p2p_rate`, `spread_pct`, `m2_trend_expansion`, `timestamp_utc`, `noise_filter_status`.
  - `DraftPrediction`: propuesta de inferencia del Predictor con `direction`, `horizon`, `confidence_pct`, `bullish_force_weight`, `bearish_force_weight`, `net_balance`, `key_drivers`, `reasoning_chain`, `risks_invalidation`.
  - `FinalUSDTPrediction`: predicción validada por el Revisor con `verdict`, `direction`, `horizon`, `confidence_pct`, `audited_justification`, `reviewer_notes`, `predictor_model`, `reviewer_model`, `prev_hash`, `prediction_hash`, `timestamp_utc`.
  - `AIProviderConfig` y `ProviderQuotaStatus`: telemetría de cuotas y estado de Circuit Breaker por proveedor.
- [ ] T23.3: Crear tests unitarios en rojo para modelos SQLAlchemy y repositorios en `tests/unit/test_macro_models_repository.py`, validando persistencia, unicidad y encadenamiento SHA-256 inmutable.
- [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo de `prediction_hash = SHA256(prev_hash + payload)`.

## Fase 2: Extractor de Contexto Macroeconómico, Taxonomía y Filtro Anti-Ruido
- [ ] T23.5: Crear tests unitarios en rojo para extracción y normalización de noticias macroeconómicas en `tests/unit/test_macro_extractor.py`, mockeando respuestas de fuentes públicas, timeouts y páginas con HTML corrupto.
- [ ] T23.6: Implementar `MacroNormalizer` en `src/core/macro/normalizer.py`:
  - Limpieza y sanitización de texto con caracteres especiales o codificación mixta (UTF-8 / Latin-1).
  - Detección y normalización de fechas en español (ej. "Lunes 17 de noviembre de 2026", "hace 2 horas").
  - Extracción de cifras monetarias en Bolívares (Bs., BsD, BsF) y conversión consistente a notación estándar decimal.
- [ ] T23.7: Implementar `MacroContextExtractor` en `src/core/macro/extractor.py`:
  - Conector primario para intervenciones cambiarias y notas de prensa del BCV (`https://www.bcv.org.ve`).
  - Conector para agregadores económicos y reportes de liquidez monetaria M2.
  - Conector para cronograma de pagos de nómina pública y bonos Patria.
  - Clasificador heurístico de taxonomía que asigna el código correspondiente de la taxonomía canónica de 14 eventos (`docs/macro_usdt_taxonomy.md`).
- [ ] T23.8: Implementar comportamiento **Fail-closed** ante caídas de fuentes en `MacroContextExtractor`:
  - Ante error HTTP 5xx, timeout o baneo WAF en un portal, degradar a fuentes secundarias.
  - Si ninguna fuente responde o los datos están desactualizados (> 72 horas sin eventos), emitir flag `DATA_STALE` y bloquear la inferencia con estado `NEUTRAL / DATOS_INSUFICIENTES` sin inventar noticias.

## Fase 3: Motor Round-Robin Multi-Proveedor y Pool de Claves de IA
- [ ] T23.9: Crear tests unitarios en rojo para el motor multi-proveedor en `tests/unit/test_multi_provider_ai_engine.py`, simulando:
  - Rotación Round-Robin equitativa entre múltiples slots de claves de un mismo proveedor.
  - Conmutación por error (Failover) en cascada: Google Gemini ➔ Groq Cloud ➔ DeepSeek ➔ OpenAI.
  - Activación de Circuit Breaker (estados CLOSED ➔ OPEN ➔ HALF-OPEN) tras 3 fallos consecutivos (HTTP 429, 500, 503 o timeouts).
  - Enfriamiento dinámico (cooldown) y reintentos Tenacity con backoff exponencial y jitter.
  - Sanitización obligatoria anti-filtración de API Keys en prompts y excepciones con `sanitize_message()`.
- [ ] T23.10: Implementar la clase `MultiProviderAIEngine` en `src/core/macro/llm_engine.py` (extendiendo el diseño probado de `AIKeyPool`):
  - Soporte de configuración de proveedores vía variables de entorno (`GEMINI_API_KEYS`, `GROQ_API_KEYS`, `DEEPSEEK_API_KEYS`, `OPENAI_API_KEYS`, `ANTHROPIC_API_KEYS`).
  - Punteros de rotación atómica por proveedor con protección contra condiciones de carrera (`threading.Lock`).
  - Detección de cabeceras de rate-limit (`retry-after`, `x-ratelimit-reset`) para asignar tiempos exactos de cooldown.
- [ ] T23.11: Implementar clientes adaptadores desacoplados para cada proveedor de LLM en `src/core/macro/adapters/`:
  - `GeminiAdapter`: invocación mediante REST HTTPX / Google GenAI SDK con soporte para `response_schema` Pydantic y `thinking_budget`.
  - `GroqAdapter`: invocación compatible con OpenAI API apuntando a `api.groq.com/openai/v1` (modelo `llama-3.3-70b-versatile`).
  - `DeepSeekAdapter`: invocación con extracción de bloques de razonamiento `<think>` y payload JSON.
  - `OpenAIAdapter`: invocación con modo `strict: true` de Structured Outputs.
  - `AnthropicAdapter`: invocación de Claude 3.5 Sonnet / Haiku con tool-based JSON outputs.
- [ ] T23.12: Implementar módulo de telemetría y métricas de cuotas en `src/core/macro/quota_monitor.py` que reporte latencia, tokens consumidos, costo acumulado estimado ($ USD) y estado de disponibilidad de cada proveedor.

## Fase 4: Pipeline de Predicción y Revisión Cruzada (Analyst + Cross-Family Reviewer)
- [ ] T23.13: Crear tests unitarios en rojo para el pipeline completo de inferencia en `tests/unit/test_prediction_pipeline.py`, mockeando casos de:
  - Consenso pleno (Buscador ➔ Predictor ➔ Revisor aprueba con alta confianza).
  - Veto adversarial por alucinación (Revisor detecta que el Predictor cita una intervención cambiaria inexistente en el contexto).
  - Ajuste Fail-Closed por incertidumbre o contradicción fuerte entre fuerzas alcistas y bajistas.
  - Inmutabilidad de la cadena SHA-256 generada.
- [ ] T23.14: Implementar `MacroAnalystPredictor` en `src/core/macro/analyst.py`:
  - Inyección del System Prompt canónico de analista macroeconómico especializado en el mercado cambiario venezolano.
  - Ingesta de `MacroContextPayload` y formulación del balance vectorial ($F_{\text{neta}} = \sum w_{\text{alcista}} - \sum w_{\text{bajista}}$).
  - Inferencia de dirección (`SUBE`, `BAJA`, `ESTABLE`), horizonte temporal estimado y cálculo de confiabilidad calibrada ($C_{\text{calibrada}} \in [0, 100\%]$).
  - Emisión de `DraftPrediction` en formato JSON estructurado estricto.
- [ ] T23.15: Implementar `PredictionReviewer` en `src/core/macro/reviewer.py`:
  - Regla Constitucional de **Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**: si el Predictor es DeepSeek o Gemini, el Revisor DEBE ser asignado a una familia distinta (Anthropic Claude o OpenAI GPT).
  - System Prompt adversarial y escéptico que audita:
    1. Veracidad empírica: ¿Cada factor citado en la justificación proviene textualmente de `MacroContextPayload`?
    2. Coherencia causal: ¿La dirección y horizonte son lógicamente consistentes con la taxonomía y la matriz de rezagos temporales?
    3. Calibración de confianza: ¿La confianza declarada refleja adecuadamente la presencia de fuerzas contrapuestas?
  - Determinación del veredicto: `APROBADO`, `RECHAZADO` o `AJUSTADO_FAIL_CLOSED` (reduciendo la confianza y añadiendo notas de advertencia).
- [ ] T23.16: Implementar la clase orquestadora `MacroPredictionPipeline` en `src/core/macro/pipeline.py`:
  - Coordinación secuencial: `MacroContextExtractor` ➔ `MacroAnalystPredictor` ➔ `PredictionReviewer`.
  - Encadenamiento criptográfico: lectura del último `prediction_hash` desde `MacroRepository`, cálculo del nuevo hash y guardado atómico en base de datos.
  - Manejo de excepciones con parada preventiva fail-closed: si cualquier paso falla tras agotar reintentos, registrar evento de auditoría de fallo y emitir estado neutral sin romper el proceso principal del bot.
- [ ] T23.17: Crear comando CLI de diagnóstico `python -m src.core.macro.cli --dry-run` para inspección y depuración manual por operadores.

## Fase 5: Integraciones (Telegram, Dashboard Streamlit y API REST FastAPI)
- [ ] T23.18: Crear tests unitarios e integración para la capa de presentación y mensajería en `tests/unit/test_macro_presentation.py`.
- [ ] T23.19: Integrar el motor de predicción en el Bot de Telegram (`src/integrations/telegram_notifier.py` y `src/integrations/ai_assistant.py`):
  - Nuevo comando `/prediccion` (con alias `/macro`, `/tendencia`): genera o consulta la última predicción auditada, formateada con semáforo visual (🟢 Alcista / 🔴 Bajista / ⚪ Neutral), lapso estimado, confiabilidad %, justificación resumida y hash SHA-256 truncado.
  - Alertas Push Proactivas: notificación automática cuando se detecte un cambio de tendencia con confianza $\ge 75\%$ o un evento macroeconómico de impacto crítico (ej. mega-intervención BCV o devaluación oficial).
  - Registro de Tool en `AIAssistantTools` (`consultar_prediccion_macro`) para permitir consultas en lenguaje natural libre ("¿Cómo ves el USDT para este fin de semana?").
- [ ] T23.20: Implementar la vista interactiva de Inteligencia Macroeconómica en Streamlit (`src/reporting/dashboard/views/macro_prediction_view.py`) e integrarla en `src/reporting/dashboard/app.py`:
  - Tarjeta KPI principal con dirección proyectada, ventana temporal y velocímetro/gauge de confiabilidad.
  - Gráfico de balance vectorial de fuerzas (factores alcistas vs factores bajistas con ponderación).
  - Cronología interactiva de eventos macroeconómicos recientes con categoría, fuente y peso.
  - Visor de auditoría criptográfica con botón para verificar la integridad del hash SHA-256 en base de datos.
  - Selector de proveedor LLM y botón de refresco manual con control de cooldown para administradores.
- [ ] T23.21: Implementar endpoints REST en FastAPI (`src/api/routes/macro.py`) e incluir el router en `src/api/main.py`:
  - `GET /api/macro/prediction/latest`: devuelve la predicción vigente.
  - `GET /api/macro/prediction/history?limit=20`: listado cronológico de predicciones auditadas.
  - `POST /api/macro/prediction/run`: disparo manual autenticado (rol `ADMIN` / `TRADER`).
  - `GET /api/macro/events`: listado de eventos macroeconómicos categorizados activos en el horizonte actual.
- [ ] T23.22: Sanitizar todas las salidas hacia Telegram, UI y API con `sanitize_message()` garantizando **Cero Secretos** (claves API, tokens o credenciales enmascaradas).

## Fase 6: Pruebas E2E, Validación SDD, Hardening de Seguridad y Memoria
- [ ] T23.23: Crear y ejecutar suite de pruebas E2E en `tests/e2e/test_macro_prediction_e2e.py`:
  - Simulación completa de ciclo de predicción desde extracción de fuentes con mocks hasta persistencia en base de datos y emisión de alerta en Telegram.
  - Verificación de la integridad de la cadena SHA-256 en 10 predicciones consecutivas.
  - Verificación de recuperación transparente ante simulación de caída de proveedores primarios (Gemini y Groq) con failover hacia DeepSeek y OpenAI.
- [ ] T23.24: Ejecutar escaneo estático de seguridad y auditoría de dependencias:
  - Invocar skill `security-review` (SAST, detección de secretos en git history, validación de permisos).
  - Verificar ausencia total de llamadas genéricas `except Exception:` desnudas (cumplimiento BLE001 / ADR 008).
- [ ] T23.25: Ejecutar suite de calidad del código:
  - `python -m ruff check .` (0 advertencias).
  - `python -m mypy src/ tests/` (0 errores de tipado estricto).
  - `pytest tests/` (todos los tests existentes y nuevos pasando al 100%).
- [ ] T23.26: Ejecutar script de validación SDD `.specify\scripts\validate-spec.ps1` comprobando que `spec.md`, `plan.md` y `tasks.md` cumplan íntegramente los estándares, y actualizar `memory.md` registrando la especificación y el ADR correspondiente.
```

---

## 3. Estrategia de Edición de `memory.md`

`memory.md` es el registro histórico canónico y append-only del proyecto. Para incorporar la **SPEC-023** sin romper los registros históricos previos, el Worker debe realizar tres inserciones quirúrgicas en secciones específicas:

### 3.1. Inserción 1: Registro en `## 📊 Estado del Proyecto por Paquetes y Tareas`
En la sección `## 📊 Estado del Proyecto por Paquetes y Tareas`, justo antes de `### ✅ Paquetes Completados` (o como primer ítem de especificaciones en curso), registrar el estado del Paquete 023:

```markdown
### 📋 Paquetes en Especificación y Diseño Arquitectónico (ACTIVO)
- [ ] **Paquete 023 (Sistema de Inteligencia Macroeconómica y Predicción de Mercado USDT con IA — SPEC-023)**:
  - **Especificación SDD Formalizada** ([`.specify/specs/023-ai-market-predictor/`](file:///c:/p2p-bot-merchant/.specify/specs/023-ai-market-predictor/)): Creados y validados con `.specify/scripts/validate-spec.ps1` los artefactos canónicos `spec.md`, `plan.md` y `tasks.md` (26 tareas atómicas ordenadas).
  - **Taxonomía Canónica Macroeconómica** ([`docs/macro_usdt_taxonomy.md`](file:///c:/p2p-bot-merchant/docs/macro_usdt_taxonomy.md)): Documentados los 14 eventos clave de la economía venezolana (intervenciones BCV, liquidez M2, nóminas públicas, bonos Patria, brecha cambiaria), con pesos de impacto, matriz de rezagos temporales (lags) y catálogo de fuentes públicas oficiales y financieras.
  - **Pipeline Desacoplado de 3 Roles Especializados**:
    1. *Buscador / Recopilador*: Gemini 2.0/2.5 Flash / Groq Llama 3.3 70B para ingesta, extracción estructurada JSON y filtrado anti-ruido.
    2. *Analista / Predictor*: DeepSeek-R1 / Gemini 2.5 Flash Thinking para deducción causal monetaria, ponderación de fuerzas alcistas vs bajistas y cálculo de confiabilidad calibrada ($0-100\%$).
    3. *Revisor / Auditor*: Claude 3.5 Sonnet / OpenAI GPT-4o-mini con verificación cruzada entre familias de modelos (*Cross-Family Model Verification*) para veto de alucinaciones y enforcement Fail-Closed.
  - **Motor de Inferencia Round-Robin Multi-Proveedor**: Extensión `MultiProviderAIEngine` con rotación equitativa multi-clave, Circuit Breaker (CLOSED/OPEN/HALF-OPEN), reintentos con backoff exponencial y tolerancia a fallos multi-proveedor (Gemini ➔ Groq ➔ DeepSeek ➔ OpenAI).
  - **Seguridad, Persistencia y Trazabilidad**: Cero Secretos en prompts/logs (`sanitize_message`), persistencia en base de datos (`macro_predictions`) con encadenamiento criptográfico SHA-256 (`prev_hash` ➔ `prediction_hash`) e integraciones con Telegram (`/prediccion`), Dashboard Streamlit y API REST FastAPI.
```

### 3.2. Inserción 2: Registro en `## 📐 Decisiones Clave de Arquitectura (ADRs)`
Al final de la sección `## 📐 Decisiones Clave de Arquitectura (ADRs)` (después del ADR 055 en la línea 731), añadir el **ADR 056**:

```markdown
56. **Sistema de Inteligencia Macroeconómica y Predicción de Mercado con IA Tolerante a Fallos (ADR 056 / SPEC-023)**:
    - **Contexto**:
      - El tipo de cambio USDT/VES en el mercado P2P venezolano experimenta fluctuaciones severas determinadas por fuerzas macroeconómicas exógenas: inyecciones cambiarias semanales del Banco Central de Venezuela (BCV), emisión de liquidez monetaria M2 para financiamiento del déficit fiscal, desembolsos masivos de nóminas de la administración pública y bonos gubernamentales a través del Sistema Patria, y dinámica de la brecha cambiaria (spread entre tasa oficial y tasa paralela/P2P).
      - El comerciante P2P necesita anticipar cambios en la tendencia con horizontes accionables (24h-48h, 3-5 días o semanal) para ajustar su inventario, spreads y exposición bancaria.
      - Para evitar alucinaciones y garantizar alta disponibilidad, se requiere un pipeline de IA que no dependa de un único proveedor ni emita juicios sin contrastación factual independiente.
    - **Decisiones de Arquitectura**:
      1. **Monotonicidad y Numeración Formal (SPEC-023)**:
         - Se asigna formalmente la denominación `023-ai-market-predictor`, respetando la pausa explícita del Paquete 003 (Pricing algorítmico automatizado) acordada con el usuario. La Spec 023 opera de forma autónoma como motor de inteligencia/asesoramiento (Advisory) sin ejecutar órdenes directas en Binance P2P.
      2. **Pipeline Desacoplado de 3 Roles Especializados**:
         - *Rol 1 (Buscador / Recopilador)*: Gemini 2.0/2.5 Flash / Groq Llama 3.3 70B (baja latencia, ventana de contexto de 1M tokens, costo mínimo para ingesta de grandes volúmenes de texto y normalización JSON estructurada).
         - *Rol 2 (Analista / Predictor)*: DeepSeek-R1 / Gemini 2.5 Flash Thinking (capacidad de razonamiento CoT nativo para sopesar oferta y demanda monetaria, calcular la fuerza vectorial neta y deducir dirección, horizonte y confianza).
         - *Rol 3 (Revisor / Auditor)*: Claude 3.5 Sonnet / OpenAI GPT-4o-mini (auditoría factual escéptica y filtro anti-alucinación).
      3. **Principio Innegociable de Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**:
         - El Revisor **nunca** debe pertenecer a la misma familia arquitectónica que el Predictor. Si el Predictor es DeepSeek o Gemini, el Revisor debe ser Anthropic (Claude) u OpenAI (GPT), mitigando sesgos de entrenamiento compartidos y alucinaciones correlacionadas.
      4. **Motor Round-Robin Multi-Proveedor (`MultiProviderAIEngine`)**:
         - Extensión de la arquitectura probada de `AIKeyPool`: rotación proactiva round-robin entre claves del mismo proveedor y conmutación automática por error (failover) en cascada entre proveedores ante códigos HTTP 429, 500, 503 o timeouts, gobernado por un Circuit Breaker con estados CLOSED, OPEN y HALF-OPEN.
      5. **Trazabilidad Criptográfica SHA-256 Append-Only**:
         - Cada predicción emitida se registra en la tabla `macro_predictions` con su timestamp UTC, metadatos de los modelos utilizados, resumen de noticias ponderadas y un hash inmutable encadenado (`prediction_hash = SHA-256(prev_hash + payload)`).
      6. **Comportamiento Fail-Closed y Cero Secretos**:
         - Si las fuentes no están disponibles, si los modelos discrepan irreconciliablemente o si la confianza calculada es insuficiente, el sistema emite el estado seguro `NEUTRAL / INDETERMINADO` advirtiendo al operador.
         - Prohibida terminantemente la exposición de API Keys en logs, prompts salientes o interfaces de usuario, aplicando la sanitización regex obligatoria de `sanitize_message()`.
    - **Verificación**:
      - Validación formal de especificación con `.specify\scripts\validate-spec.ps1`.
      - Cobertura de pruebas unitarias y de integración del pipeline con mocks en `tests/unit/test_macro_*.py`.
      - 0 violaciones de seguridad en escaneo con `security-review`.
```

### 3.3. Inserción 3: Actualización en `## 🎯 Guía Operativa Actual`
En la sección `## 🎯 Guía Operativa Actual` (punto 2 y siguientes), incorporar las referencias operativas de la Spec 023:
- Comando de validación SDD: `powershell -ExecutionPolicy Bypass -File .specify\scripts\validate-spec.ps1`
- Endpoints REST de Inteligencia Macroeconómica: `GET /api/macro/prediction/latest` y `GET /api/macro/events`.
- Comando de Telegram: `/prediccion` (con alias `/macro`, `/tendencia`).

---

## 4. Estrategia y Ejecución del Script de Validación (`validate-spec.ps1`)

### 4.1. Análisis del Mecanismo de Validación
El script `.specify\scripts\validate-spec.ps1` opera de la siguiente manera:
```powershell
$specDirs = Get-ChildItem -Path ".specify\specs" -Directory

foreach ($dir in $specDirs) {
    Write-Host "Revisando: $($dir.FullName)"
    $spec = Join-Path $dir.FullName "spec.md"
    $plan = Join-Path $dir.FullName "plan.md"
    $tasks = Join-Path $dir.FullName "tasks.md"

    if (-not (Test-Path $spec)) { Write-Error "Falta spec.md en $($dir.Name)"; exit 1 }
    if (-not (Test-Path $plan)) { Write-Error "Falta plan.md en $($dir.Name)"; exit 1 }
    if (-not (Test-Path $tasks)) { Write-Error "Falta tasks.md en $($dir.Name)"; exit 1 }
}
```

### 4.2. Condición Crítica de Éxito (Edge Case de Creación Parcial)
⚠️ **ADVERTENCIA CRÍTICA PARA EL WORKER**:
Si el Worker crea la carpeta `.specify\specs\023-ai-market-predictor\` pero ejecuta el script antes de haber creado **los 3 archivos** (`spec.md`, `plan.md` y `tasks.md`), el validador **fallará de inmediato con `exit 1`** bloqueando la validación del proyecto.

**Regla de Ejecución Obligatoria**:
1. Escribir primero `spec.md`.
2. Escribir segundo `plan.md`.
3. Escribir tercero `tasks.md`.
4. Solo cuando los 3 archivos existan en `.specify\specs\023-ai-market-predictor\`, ejecutar el comando de validación.

### 4.3. Comandos de Verificación para el Worker

El Worker debe ejecutar exactamente los siguientes comandos y verificar sus salidas esperadas:

```powershell
# 1. Validación estricta de especificaciones SDD en Windows
powershell -ExecutionPolicy Bypass -File .specify\scripts\validate-spec.ps1
```
*Salida esperada:*
```
==> Validando integridad de especificaciones SDD...
Revisando: ...\.specify\specs\001-security-foundation
...
Revisando: ...\.specify\specs\023-ai-market-predictor
==> Todas las especificaciones cumplen la estructura requerida (spec.md, plan.md, tasks.md).
```

```powershell
# 2. Verificación de sintaxis y linting en el repositorio
python -m ruff check .
```
*Salida esperada:* `All checks passed!`

```powershell
# 3. Verificación de tipos estáticos
python -m mypy src/ tests/ scripts/
```
*Salida esperada:* `Success: no issues found in ... source files`

```powershell
# 4. Verificación de no regresión en la suite de pruebas
pytest tests/
```
*Salida esperada:* `230+ passed in ...s`

---

## 5. Matriz de Dependencias y Secuencia de Ejecución del Worker

| Paso | Acción del Worker | Archivo Destino | Criterio de Aceptación / Verificación |
| :--- | :--- | :--- | :--- |
| **Paso 1** | Crear documentación canónica taxonómica | `docs/macro_usdt_taxonomy.md` | 14 eventos clasificados, pesos y matriz de lags |
| **Paso 2** | Crear especificación de requerimientos | `.specify/specs/023-ai-market-predictor/spec.md` | Estructura SDD: QUÉ, RF-01..09, RNF-01..04, Criterios |
| **Paso 3** | Crear plan de arquitectura y diseño | `.specify/specs/023-ai-market-predictor/plan.md` | Stack, diagramas, 3 roles, Round-Robin, SHA-256 |
| **Paso 4** | Crear desglose de tareas ordenadas | `.specify/specs/023-ai-market-predictor/tasks.md` | 26 tareas atómicas con checkboxes `[ ]`, Fases 1 a 6 |
| **Paso 5** | Validar integridad del paquete SDD | Ejecutar `.specify\scripts\validate-spec.ps1` | Salida verde `exit 0` en todas las specs (001 a 023) |
| **Paso 6** | Actualizar memoria persistente | `memory.md` | Inserción de Paquete 023, ADR 056 y Guía Operativa |
| **Paso 7** | Verificación de no-regresión | `pytest tests/`, `ruff check .` | 0 errores y 0 secretos expuestos |

---

## 6. Conclusión

El plan y desglose de tareas aquí detallado proporciona al Agente Worker una guía atómica, exhaustiva y libre de ambigüedades para materializar la especificación 023 cumpliendo con los más altos estándares de Spec-Driven Development, la Constitución de `p2p-bot-merchant` y las expectativas del usuario.
