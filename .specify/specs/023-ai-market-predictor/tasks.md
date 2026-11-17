# Tasks: SPEC-023 Sistema de Inteligencia Macroeconómica y Predicción de Mercado USDT con IA Tolerante a Fallos

## Fase 1: Setup, Contratos de Datos y Pruebas Unitarias de Modelos (TDD Red)
- [ ] T23.1: Crear tests unitarios en rojo para esquemas Pydantic v2 en `tests/unit/test_macro_schemas.py`, validando:
  - Enumeraciones estrictas y normalizadas: `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`), `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, admitiendo `AJUSTADO_FAIL_CLOSED` como alias funcional de `CORREGIDO`), `TaxonomyCategory` (7 categorías canónicas alineadas con Prompt 7.1 y `macro_usdt_taxonomy.md`), `SourceCredibility` (`ALTA`, `MEDIA`, `BAJA`) y `ModelProvider` (`GEMINI`, `GROQ`, `DEEPSEEK`, `OPENAI`, `ANTHROPIC`).
  - Validación de rangos numéricos: `impact_weight` (0.0 a 1.0), `confiabilidad_porcentaje` (0.0 a 100.0) y validador condicional que restringe la confianza máxima a $\le 75.0\%$ ante veredicto `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
  - Serialización y deserialización JSON sin pérdida de precisión ni timezone drift en timestamps UTC (`datetime` con formato ISO 8601 canónico).
- [ ] T23.2: Implementar esquemas Pydantic v2 en `src/core/macro/schemas.py`:
  - `MacroEventItem`: modelo de evento individual con `event_id`, `code` (ej. `GP-01`, `IC-01`), `categoria: TaxonomyCategory`, `titulo: str`, `resumen_factico: str` (ASCII estricto), `fuente_nombre: str`, `fuente_url: Optional[str]`, `credibilidad: SourceCredibility`, `cifras_especificadas: bool`, `monto_relevante: Optional[float]`, `unidad_monto: Optional[str]`, `timestamp_evento_utc: datetime`.
  - `MacroContextPayload`: contenedor consolidado de contexto macroeconómico con `timestamp_extraccion: datetime`, `eventos: List[MacroEventItem]`, `tasa_p2p_actual: float`, `tasa_bcv_actual: float`, `brecha_cambiaria_porcentaje: float`, `fuentes_consultadas: List[str]`, `filtro_antirruido_status: Optional[str]`.
  - `DraftPrediction`: borrador de inferencia del Predictor con `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float` (0.0 a 100.0), `factores_clave: List[str]`, `justificacion_detallada: str`, `riesgos_invalidacion: List[str]`.
  - `AuditResult`: dictamen crítico del Revisor con `veredicto: AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, mapeando `AJUSTADO_FAIL_CLOSED` a `CORREGIDO`), `direccion_validada: PredictionDirection`, `confiabilidad_calibrada: float`, `puntaje_rigor: float`, `alucinaciones_detectadas: bool`, `hallazgos_criticos: List[str]`.
  - `AuditMetadata`: metadatos de auditoría y trazabilidad con `predictor_model: str`, `reviewer_model: str`, `cross_family_verified: bool`, `prev_hash: str`, `prediction_hash: str`, `timestamp_utc: datetime`, `execution_duration_ms: int`.
  - `FinalUSDTPrediction`: predicción consolidada validada con `id: str`, `veredicto: AuditVerdictEnum`, `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float`, `justificacion_auditada: str`, `factores_clave: List[str]`, `riesgos_invalidacion: List[str]`, `metadata: AuditMetadata`, incorporando validador `validar_confianza_maxima_si_corregido` que acota la confianza a un máximo de 75.0% cuando el veredicto sea `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
  - `AIProviderConfig` y `ProviderQuotaStatus`: telemetría de cuotas y estado del Circuit Breaker (`CLOSED`, `OPEN`, `HALF-OPEN`) por proveedor.
- [ ] T23.3: Crear tests unitarios en rojo para modelos SQLAlchemy y repositorios en `tests/unit/test_macro_models_repository.py`, validando persistencia, unicidad, inmutabilidad de la cadena SHA-256 encadenada y verificación de resistencia a colisiones de delimitador en la fórmula canónica delimitada por tuberías (`|`).
- [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo estricto de hash criptográfico encadenado mediante la fórmula canónica delimitada por tuberías (`|`):
  `prediction_hash = hashlib.sha256(f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}".encode("utf-8")).hexdigest()`
  utilizando como semilla génesis `prev_hash = "0" * 64` y garantizando unicidad indexada e inmutabilidad append-only.

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
  - Inferencia de dirección con `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), horizonte temporal con `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`) y cálculo de confiabilidad calibrada ($C_{\text{calibrada}} \in [0, 100\%]$).
  - Emisión de `DraftPrediction` en formato JSON estructurado estricto conforme al esquema Pydantic v2.
- [ ] T23.15: Implementar `PredictionReviewer` en `src/core/macro/reviewer.py`:
  - Regla Constitucional de **Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**: si el Predictor es DeepSeek o Gemini, el Revisor DEBE ser asignado a una familia distinta (Anthropic Claude o OpenAI GPT).
  - System Prompt adversarial y escéptico que audita:
    1. Veracidad empírica: ¿Cada factor citado en la justificación proviene textualmente de `MacroContextPayload`?
    2. Coherencia causal: ¿La dirección y horizonte son lógicamente consistentes con la taxonomía y la matriz de rezagos temporales?
    3. Calibración de confianza: ¿La confianza declarada refleja adecuadamente la presencia de fuerzas contrapuestas?
  - Determinación del veredicto según `AuditVerdictEnum`: `APROBADO` (emite la señal sin alteración), `CORREGIDO` (ajusta justificación y calibra la confianza máxima a $\le 75.0\%$, aceptando `AJUSTADO_FAIL_CLOSED` como alias funcional), o `RECHAZADO` (bloqueo preventivo fail-closed ante alucinaciones o incongruencias severas).
- [ ] T23.16: Implementar la clase orquestadora `MacroPredictionPipeline` en `src/core/macro/pipeline.py`:
  - Coordinación secuencial: `MacroContextExtractor` ➔ `MacroAnalystPredictor` ➔ `PredictionReviewer`.
  - Encadenamiento criptográfico: lectura del último `prediction_hash` desde `MacroRepository`, cálculo del nuevo hash con la fórmula canónica delimitada por tuberías (`|`) y guardado atómico en base de datos.
  - Manejo de excepciones con parada preventiva fail-closed: si cualquier paso falla tras agotar reintentos, registrar evento de auditoría de fallo y emitir estado neutral sin romper el proceso principal del bot.
- [ ] T23.17: Crear comando CLI de diagnóstico `python -m src.core.macro.cli --dry-run` para inspección y depuración manual por operadores.

## Fase 5: Integraciones (Telegram, Dashboard Streamlit y API REST FastAPI)
- [ ] T23.18: Crear tests unitarios e integración para la capa de presentación y mensajería en `tests/unit/test_macro_presentation.py`.
- [ ] T23.19: Integrar el motor de predicción en el Bot de Telegram (`src/integrations/telegram_notifier.py` y `src/integrations/ai_assistant.py`):
  - Nuevo comando `/prediccion` (con alias `/macro`, `/tendencia`): genera o consulta la última predicción auditada, formateada con semáforo visual (🟢 Alcista / 🔴 Bajista / ⚪ Neutral), lapso estimado, confiabilidad %, justificación resumida y hash SHA-256 truncado.
  - Alertas Push Proactivas: notificación automática cuando se detecte un cambio de tendencia con confianza $\ge 75\%$ o un evento macroeconómico de impacto crítico (ej. mega-intervención BCV o devaluación oficial).
  - Registro de Tool en `AIAssistantTools` (`consultar_prediccion_macro`) para permitir consultas en lenguaje natural libre ("¿Cómo ves el USDT para este fin de semana?").
- [ ] T23.20: Implementar la vista interactiva de Inteligencia Macroeconómica en Streamlit (`src/reporting/dashboard/views/macro_prediction_view.py`) e integrarla en `src/reporting/dashboard/app.py`:
  - Tarjeta KPI principal con dirección proyectada (`PredictionDirection`: `SUBE`, `BAJA`, `ESTABLE`), ventana temporal (`TimeframeHorizon`: `24h-48h`, `3-5 dias`, `semanal`), veredicto (`AuditVerdictEnum`) y velocímetro/gauge de confiabilidad calibrada.
  - Gráfico de balance vectorial de fuerzas (factores alcistas vs factores bajistas con ponderación).
  - Cronología interactiva de eventos macroeconómicos recientes con categoría (`TaxonomyCategory`), fuente y peso de impacto.
  - Visor de auditoría criptográfica con botón para verificar la integridad del hash encadenado SHA-256 pipe-delimited en base de datos.
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
  - Verificación de la integridad de la cadena SHA-256 en 10 predicciones consecutivas calculadas con la fórmula delimitada por tuberías (`|`), validando resistencia a colisiones y consistencia ante reordenamientos.
  - Verificación de recuperación transparente ante simulación de caída de proveedores primarios (Gemini y Groq) con failover hacia DeepSeek y OpenAI.
- [ ] T23.24: Ejecutar escaneo estático de seguridad y auditoría de dependencias:
  - Invocar skill `security-review` (SAST, detección de secretos en git history, validación de permisos).
  - Verificar ausencia total de llamadas genéricas `except Exception:` desnudas (cumplimiento BLE001 / ADR 008).
- [ ] T23.25: Ejecutar suite de calidad del código:
  - `python -m ruff check .` (0 advertencias).
  - `python -m mypy src/ tests/` (0 errores de tipado estricto).
  - `pytest tests/` (todos los tests existentes y nuevos pasando al 100%).
- [ ] T23.26: Ejecutar script de validación SDD `.specify\scripts\validate-spec.ps1` comprobando que `spec.md`, `plan.md` y `tasks.md` cumplan íntegramente los estándares, y actualizar `memory.md` registrando la especificación y el ADR correspondiente.
