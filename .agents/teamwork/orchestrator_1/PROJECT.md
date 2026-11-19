# Project: AI Market Predictor & Macroeconomic Intelligence (Spec 023)

## Architecture
- **Subsistema**: `023-ai-market-predictor` (Advisory / Market Intelligence).
- **Entrada**: Noticias, comunicados oficiales, reportes de M2, intervenciones BCV, calendario de pagos Patria y tasas P2P.
- **Pipeline de 3 Roles**:
  1. **Buscador/Recopilador** (Gemini 2.0/2.5 Flash): Extracción estructurada y filtrado de ruido/fake news.
  2. **Analista/Predictor** (DeepSeek-R1 / Gemini 2.5 Flash Thinking): Razonamiento causal, ponderación vectorial y cálculo calibrado de confianza.
  3. **Revisor/Auditor** (Claude 3.5 Sonnet / GPT-4o-mini): Verificación cruzada entre familias de modelos, auditoría de coherencia y enforcement Fail-Closed.
- **Resiliencia & Tolerancia a Fallos**:
  - `AIKeyPool` extendido a `MultiProviderAIEngine`: rotación Round-Robin proactiva multi-clave y failover multi-proveedor (Gemini -> Groq -> DeepSeek -> OpenAI).
  - Circuit Breaker con estados CLOSED, OPEN, HALF-OPEN y reintentos Tenacity (backoff exponencial con jitter).
- **Seguridad & Trazabilidad**:
  - Fail-Closed: si hay rechazo o falta de consenso, se emite NEUTRAL o se bloquea la señal.
  - Cero Secretos: sanitización obligatoria de API Keys con `sanitize_message()`.
  - Trazabilidad SHA-256: cada predicción y evento auditado con hash encadenado append-only en base de datos.
- **Salida**: Señal direccional (SUBE, BAJA, ESTABLE), lapso temporal (24h-48h, 3-5d, semanal), % de confiabilidad (0-100), justificación y factores de invalidación.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Taxonomía de Eventos Macroeconómicos | 14 eventos normalizados con códigos, pesos, dirección y criticidad | M1 | Survey (Explorer 1) & R1 |
| 2 | Cadenas de Transmisión y Matriz de Lags | Causalidad económica y tiempos de respuesta inicial, pico y duración | M1 | Survey (Explorer 1) & R1 |
| 3 | Catálogo de Fuentes de Datos | Fuentes oficiales (BCV, Patria), portales financieros y Telegram con factibilidad técnica | M1 | Survey (Explorer 1) & R1 |
| 4 | Comparativa Técnica y Económica de LLMs | Benchmark Gemini vs GPT-4o, Groq, DeepSeek, Claude para los 3 roles | M1 | Survey (Explorer 2) & R2 |
| 5 | Arquitectura Round-Robin y Circuit Breaker | Tolerancia a fallos multi-clave y multi-proveedor con conmutación automática | M1 | Survey (Explorer 2) & R2 |
| 6 | Perfiles y System Prompts de los 3 Roles | Prompts especializados para Buscador, Predictor y Revisor con Cross-Family Check | M1 | Survey (Explorer 2) & R2 |
| 7 | Esquemas Formales Pydantic v2 / JSON Schema | Estructuras de datos para predicción, auditoría SHA-256 y metadatos | M1 | Survey (Explorer 2) & R2 |
| 8 | Especificación de Requerimientos (`spec.md`) | Requerimientos funcionales, no funcionales y user stories en .specify/specs/023-ai-market-predictor/ | M1 | Survey (Explorer 3) & R3 |
| 9 | Plan de Arquitectura y Diseño (`plan.md`) | Diseño modular, diagramas, contratos y alineación constitucional en .specify/specs/023-ai-market-predictor/ | M1 | Survey (Explorer 3) & R3 |
| 10 | Desglose de Tareas (`tasks.md`) | Tareas ordenadas y atómicas con checkboxes `[ ]` en .specify/specs/023-ai-market-predictor/ | M1 | Survey (Explorer 3) & R3 |
| 11 | Validación SDD y Registro en Memoria | Validación con `validate-spec.ps1` y actualización de `memory.md` | M1 | Survey (Explorer 3) & R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Sistema de Inteligencia Macroeconómica y Predicción de Mercado (Spec 023) | Documentación taxonómica (`docs/macro_usdt_taxonomy.md`), paquete SDD completo (`.specify/specs/023-ai-market-predictor/` con `spec.md`, `plan.md`, `tasks.md`), validación con `validate-spec.ps1` y registro en `memory.md` | none | DONE |

## Interface Contracts
### Buscador ➔ Predictor (`MacroContextPayload`)
- `events`: List[MacroEventItem] (evento normalizado, categoría, peso, fuente, fecha/hora, resumen verificado)
- `market_snapshot`: Dict (tasa P2P actual, tasa oficial BCV, brecha cambiaria %)
- `metadata`: Dict (timestamp_utc, fuentes_consultadas, filtro_antirruido_status)

### Predictor ➔ Revisor (`DraftPrediction`)
- `direccion_propuesta`: Enum ["SUBE", "BAJA", "ESTABLE"]
- `lapso_estimado`: str (ej. "24h-48h", "3-5 dias", "semanal")
- `confiabilidad_calculada`: float (0.0 a 100.0)
- `cadena_razonamiento`: str (análisis de fuerzas vectoriales alcistas vs bajistas)
- `factores_determinantes`: List[str]
- `riesgos_invalidacion`: List[str]

### Revisor ➔ Salida Final (`FinalUSDTPrediction`)
- `veredicto`: Enum ["APROBADO", "CORREGIDO", "AJUSTADO_FAIL_CLOSED", "RECHAZADO"]
- `direccion`: Enum ["SUBE", "BAJA", "ESTABLE"]
- `lapso_estimado`: str
- `confiabilidad_porcentaje`: float (acotada a <= 75.0% si fue corregido)
- `justificacion_auditada`: str
- `audit_metadata`: Dict (modelo_revisor, hash_sha256, signature, timestamp)

## Code Layout
- `docs/macro_usdt_taxonomy.md`: Taxonomía y documentación canónica macroeconómica (414 líneas, 14 eventos, modelos matemáticos y schemas).
- `.specify/specs/023-ai-market-predictor/spec.md`: Requerimientos funcionales y no funcionales evaluados (134 líneas, RF-01..RF-10, AC-01..AC-08).
- `.specify/specs/023-ai-market-predictor/plan.md`: Arquitectura, Round-Robin, modelos y system prompts (495 líneas, benchmark 6 LLMs, circuit breaker, sha-256).
- `.specify/specs/023-ai-market-predictor/tasks.md`: Lista ordenada de 26 tareas secuenciales en 6 fases TDD.
- `memory.md`: Registro del nuevo paquete 023 y estado del sistema (ADR 056).
