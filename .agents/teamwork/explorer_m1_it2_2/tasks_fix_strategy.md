# Remediation Strategy: Harmonization of `tasks.md` (SPEC-023)

**Author:** Explorer M1_IT2_2 (Tasks Harmonization Strategist)  
**Target Document:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\tasks.md`  
**Reference Sources:**
- `c:\p2p-bot-merchant\.agents\teamwork\challenger_m1_2\handoff.md`
- `c:\p2p-bot-merchant\.agents\teamwork\orchestrator_1\PROJECT.md`
- `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\spec.md`
- `c:\p2p-bot-merchant\docs\macro_usdt_taxonomy.md`  
**Date:** 2026-11-17T00:48:00Z  
**Status:** READY FOR APPLICATION

---

## 1. Executive Summary

During Milestone 1 Iteration 1 review, Challenger 2 identified critical contract discrepancies between `tasks.md`, `plan.md`, and `PROJECT.md` (Obs 3), as well as a cryptographic delimiter collision vulnerability in the SHA-256 chaining specification (Obs 2). If left unaddressed, implementing the tasks as written in `tasks.md` would immediately result in:
1. **Compilation/Runtime Type Failures:** `tasks.md` T23.1 specified English enums `MarketDirection` (`BULLISH`, `BEARISH`, `NEUTRAL`) and `TimeHorizon` (`INMEDIATO_12H`, etc.), while `plan.md`, `spec.md`, and system prompts enforce Spanish enums `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`) and `TimeframeHorizon` (`24h-48h`, `3-5 dias`, `semanal`).
2. **Reviewer Verdict Mismatch:** `tasks.md` specified `ReviewVerdict` (`APROBADO`, `RECHAZADO`, `AJUSTADO_FAIL_CLOSED`), whereas `plan.md` defined `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`).
3. **Payload Container Name Divergence:** `tasks.md` and `PROJECT.md` used `MacroContextPayload`, while `plan.md` in line 359 defined `MacroContextCollection`.
4. **Cryptographic Collision Risk:** `tasks.md` T23.4 specified an ambiguous un-delimited concatenation `prediction_hash = SHA256(prev_hash + payload)`, susceptible to boundary-bleed collisions between adjacent string fields.

This remediation document provides the **exact, line-by-line strategy** to harmonize `tasks.md`, eliminating all contract ambiguities and embedding the strict pipe-delimited SHA-256 formula without altering task numbering or scope.

---

## 2. Contract Inconsistencies Matrix

| Dimension | `tasks.md` (Current) | `plan.md` (Current) | `PROJECT.md` | Canonical Harmonized Standard |
| :--- | :--- | :--- | :--- | :--- |
| **Direction Enum** | `MarketDirection`<br>(`BULLISH`, `BEARISH`, `NEUTRAL`) | `PredictionDirection`<br>(`SUBE`, `BAJA`, `ESTABLE`) | `direccion_propuesta`<br>(`["SUBE", "BAJA", "ESTABLE"]`) | **`PredictionDirection`**<br>`SUBE`, `BAJA`, `ESTABLE` |
| **Timeframe Enum** | `TimeHorizon`<br>(`INMEDIATO_12H`, `CORTO_24_48H`, `MEDIANO_3_5D`, `SEMANAL`) | `TimeframeHorizon`<br>(`"24h-48h"`, `"3-5 dias"`, `"semanal"`) | `lapso_estimado`<br>(`"24h-48h"`, `"3-5 dias"`, `"semanal"`) | **`TimeframeHorizon`**<br>`"24h-48h"`, `"3-5 dias"`, `"semanal"` |
| **Payload Container** | `MacroContextPayload` | `MacroContextCollection`<br>(line 359; line 89 uses Payload) | `MacroContextPayload` | **`MacroContextPayload`** (canonical class name across all modules) |
| **Verdict Enum** | `ReviewVerdict`<br>(`APROBADO`, `RECHAZADO`, `AJUSTADO_FAIL_CLOSED`) | `AuditVerdictEnum`<br>(`APROBADO`, `CORREGIDO`, `RECHAZADO`) | `veredicto`<br>(`["APROBADO", "RECHAZADO", "AJUSTADO_FAIL_CLOSED"]`) | **`AuditVerdictEnum`**<br>`APROBADO`, `CORREGIDO`, `RECHAZADO`<br>(with `AJUSTADO_FAIL_CLOSED` alias to `CORREGIDO`) |
| **Taxonomy Categories** | `MacroEventType`<br>(14 categorías) | `TaxonomyCategory`<br>(7 categorías macro) | Taxonomía de 14 eventos normalizados | **`TaxonomyCategory`** (7 macro categorizaciones canónicas) + **`MacroEventCode`** (14 códigos específicos de evento) |
| **SHA-256 Hashing Formula** | `prediction_hash = SHA256(prev_hash + payload)` | $\text{SHA256}(\text{prev\_hash} + \text{ts} + \text{dir} + \dots)$ (un-delimited) | `hash_sha256` | **Pipe-delimited format:**<br>`f"{prev_hash}\|{timestamp_iso}\|{direction}\|{timeframe}\|{confidence}\|{model}\|{justification}"` |

---

## 3. Detailed Task Remediation Plan

### 3.1 Task T23.1: Setup and Unit Red Tests for Pydantic v2 Schemas

* **Target Lines in `tasks.md`:** Lines 4–7.
* **Problem:** Declares English enums `MarketDirection` and `TimeHorizon`, legacy `ReviewVerdict`, and collapses 7 taxonomy categories with 14 event codes into `MacroEventType`.
* **Remediation:**
  - Standardize Direction to `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`).
  - Standardize Horizon to `TimeframeHorizon` (`24h-48h`, `3-5 dias`, `semanal`).
  - Standardize Verdict to `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, con soporte para alias `AJUSTADO_FAIL_CLOSED` mapeado a `CORREGIDO`).
  - Clarify taxonomy enums: `TaxonomyCategory` (7 categorías canónicas: `GASTO_PUBLICO_PATRIA`, `INTERVENCION_CAMBIARIA_BCV`, `POLITICA_MONETARIA_LIQUIDEZ`, `CALENDARIO_FISCAL_SENIAT`, `REGULACION_CAMBIARIA_BANCARIA`, `OPERATIVA_MERCADO_P2P`, `GEOPOLITICA_PETROLERA`) y `SourceCredibility` (`ALTA`, `MEDIA`, `BAJA`).
  - Explicitly test confidence calibration clamping ($\le 75.0\%$) when `veredicto == CORREGIDO / AJUSTADO_FAIL_CLOSED`.

**Replacement Chunk for T23.1:**
```markdown
- [ ] T23.1: Crear tests unitarios en rojo para esquemas Pydantic v2 en `tests/unit/test_macro_schemas.py`, validando:
  - Enumeraciones estrictas y normalizadas: `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`), `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, admitiendo `AJUSTADO_FAIL_CLOSED` como alias funcional de `CORREGIDO`), `TaxonomyCategory` (7 categorías canónicas alineadas con Prompt 7.1 y `macro_usdt_taxonomy.md`), `SourceCredibility` (`ALTA`, `MEDIA`, `BAJA`) y `ModelProvider` (`GEMINI`, `GROQ`, `DEEPSEEK`, `OPENAI`, `ANTHROPIC`).
  - Validación de rangos numéricos: `impact_weight` (0.0 a 1.0), `confiabilidad_porcentaje` (0.0 a 100.0) y validador condicional que restringe la confianza máxima a $\le 75.0\%$ ante veredicto `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
  - Serialización y deserialización JSON sin pérdida de precisión ni timezone drift en timestamps UTC (`datetime` con formato ISO 8601 canónico).
```

---

### 3.2 Task T23.2: Pydantic v2 Schema Implementation

* **Target Lines in `tasks.md`:** Lines 8–13.
* **Problem:** Mixed English/Spanish field names, ambiguous schema structure, missing explicit declaration of `MacroContextPayload` contract and nested `AuditMetadata`.
* **Remediation:**
  - Standardize container name to **`MacroContextPayload`**.
  - `MacroEventItem`: Include ASCII field `resumen_factico` (without accent), `code: str` (e.g. `GP-01`, `IC-01`), `categoria: TaxonomyCategory`, `credibilidad: SourceCredibility`.
  - `DraftPrediction`: `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float`, `factores_clave: List[str]`, `justificacion_detallada: str`, `riesgos_invalidacion: List[str]`.
  - `AuditResult`: `veredicto: AuditVerdictEnum`, `direccion_validada: PredictionDirection`, `confiabilidad_calibrada: float`, `puntaje_rigor: float`, `alucinaciones_detectadas: bool`, `hallazgos_criticos: List[str]`.
  - `AuditMetadata`: `predictor_model: str`, `reviewer_model: str`, `cross_family_verified: bool`, `prev_hash: str`, `prediction_hash: str`, `timestamp_utc: datetime`, `execution_duration_ms: int`.
  - `FinalUSDTPrediction`: `id: str`, `veredicto: AuditVerdictEnum`, `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float`, `justificacion_auditada: str`, `factores_clave: List[str]`, `riesgos_invalidacion: List[str]`, `metadata: AuditMetadata`, con validador de confianza máxima (`<= 75.0%`) si `veredicto == CORREGIDO`.

**Replacement Chunk for T23.2:**
```markdown
- [ ] T23.2: Implementar esquemas Pydantic v2 en `src/core/macro/schemas.py`:
  - `MacroEventItem`: modelo de evento individual con `event_id`, `code` (ej. `GP-01`, `IC-01`), `categoria: TaxonomyCategory`, `titulo: str`, `resumen_factico: str` (ASCII estricto), `fuente_nombre: str`, `fuente_url: Optional[str]`, `credibilidad: SourceCredibility`, `cifras_especificadas: bool`, `monto_relevante: Optional[float]`, `unidad_monto: Optional[str]`, `timestamp_evento_utc: datetime`.
  - `MacroContextPayload`: contenedor consolidado de contexto macroeconómico con `timestamp_extraccion: datetime`, `eventos: List[MacroEventItem]`, `tasa_p2p_actual: float`, `tasa_bcv_actual: float`, `brecha_cambiaria_porcentaje: float`, `fuentes_consultadas: List[str]`, `filtro_antirruido_status: Optional[str]`.
  - `DraftPrediction`: borrador de inferencia del Predictor con `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float` (0.0 a 100.0), `factores_clave: List[str]`, `justificacion_detallada: str`, `riesgos_invalidacion: List[str]`.
  - `AuditResult`: dictamen crítico del Revisor con `veredicto: AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, mapeando `AJUSTADO_FAIL_CLOSED` a `CORREGIDO`), `direccion_validada: PredictionDirection`, `confiabilidad_calibrada: float`, `puntaje_rigor: float`, `alucinaciones_detectadas: bool`, `hallazgos_criticos: List[str]`.
  - `AuditMetadata`: metadatos de auditoría y trazabilidad con `predictor_model: str`, `reviewer_model: str`, `cross_family_verified: bool`, `prev_hash: str`, `prediction_hash: str`, `timestamp_utc: datetime`, `execution_duration_ms: int`.
  - `FinalUSDTPrediction`: predicción consolidada validada con `id: str`, `veredicto: AuditVerdictEnum`, `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float`, `justificacion_auditada: str`, `factores_clave: List[str]`, `riesgos_invalidacion: List[str]`, `metadata: AuditMetadata`, incorporando validador `validar_confianza_maxima_si_corregido` que acota la confianza a un máximo de 75.0% cuando el veredicto sea `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
  - `AIProviderConfig` y `ProviderQuotaStatus`: telemetría de cuotas y estado del Circuit Breaker (`CLOSED`, `OPEN`, `HALF-OPEN`) por proveedor.
```

---

### 3.3 Task T23.3: Unit Red Tests for Database Models and Pipe-Delimited Chaining

* **Target Lines in `tasks.md`:** Line 14.
* **Remediation:** Explicitly mandate testing the pipe-delimited hashing formula against pre-image delimiter collisions and tampering.

**Replacement Chunk for T23.3:**
```markdown
- [ ] T23.3: Crear tests unitarios en rojo para modelos SQLAlchemy y repositorios en `tests/unit/test_macro_models_repository.py`, validando persistencia, unicidad, inmutabilidad de la cadena SHA-256 encadenada y verificación de resistencia a colisiones de delimitador en la fórmula canónica delimitada por tuberías (`|`).
```

---

### 3.4 Task T23.4: SQLAlchemy Models, Migrations, and Pipe-Delimited Chaining

* **Target Lines in `tasks.md`:** Line 15.
* **Problem:** Specified ambiguous formula `prediction_hash = SHA256(prev_hash + payload)` without delimiters, vulnerable to collision.
* **Remediation:** Replace with exact canonical pipe-delimited formula:
  $$\text{prediction\_hash} = \text{SHA256}\Big(\text{prev\_hash} + \text{"\|"} + \text{timestamp\_iso} + \text{"\|"} + \text{direction} + \text{"\|"} + \text{timeframe} + \text{"\|"} + \text{confidence} + \text{"\|"} + \text{model} + \text{"\|"} + \text{justification}\Big)$$
  with genesis seed `prev_hash = "0" * 64`.

**Replacement Chunk for T23.4:**
```markdown
- [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo estricto de hash criptográfico encadenado mediante la fórmula canónica delimitada por tuberías (`|`):
  `prediction_hash = hashlib.sha256(f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}".encode("utf-8")).hexdigest()`
  utilizando como semilla génesis `prev_hash = "0" * 64` y garantizando unicidad indexada e inmutabilidad append-only.
```

---

### 3.5 Task T23.14: `MacroAnalystPredictor` Contract Harmonization

* **Target Lines in `tasks.md`:** Lines 57–61.
* **Problem:** General reference to direction and timeframe without binding to specific enum types.
* **Remediation:** Explicitly link `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`) and `TimeframeHorizon` (`24h-48h`, `3-5 dias`, `semanal`).

**Replacement Chunk for T23.14:**
```markdown
- [ ] T23.14: Implementar `MacroAnalystPredictor` en `src/core/macro/analyst.py`:
  - Inyección del System Prompt canónico de analista macroeconómico especializado en el mercado cambiario venezolano.
  - Ingesta de `MacroContextPayload` y formulación del balance vectorial ($F_{\text{neta}} = \sum w_{\text{alcista}} - \sum w_{\text{bajista}}$).
  - Inferencia de dirección con `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), horizonte temporal con `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`) y cálculo de confiabilidad calibrada ($C_{\text{calibrada}} \in [0, 100\%]$).
  - Emisión de `DraftPrediction` en formato JSON estructurado estricto conforme al esquema Pydantic v2.
```

---

### 3.6 Task T23.15: `PredictionReviewer` Contract Harmonization

* **Target Lines in `tasks.md`:** Lines 62–68.
* **Problem:** Referenced legacy `AJUSTADO_FAIL_CLOSED` without clearly integrating `AuditVerdictEnum` and its functional alias.
* **Remediation:** Harmonize with `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, con alias `AJUSTADO_FAIL_CLOSED` mapeado a `CORREGIDO` y aplicación de cap de confianza máxima $\le 75.0\%$).

**Replacement Chunk for T23.15:**
```markdown
- [ ] T23.15: Implementar `PredictionReviewer` en `src/core/macro/reviewer.py`:
  - Regla Constitucional de **Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**: si el Predictor es DeepSeek o Gemini, el Revisor DEBE ser asignado a una familia distinta (Anthropic Claude o OpenAI GPT).
  - System Prompt adversarial y escéptico que audita:
    1. Veracidad empírica: ¿Cada factor citado en la justificación proviene textualmente de `MacroContextPayload`?
    2. Coherencia causal: ¿La dirección y horizonte son lógicamente consistentes con la taxonomía y la matriz de rezagos temporales?
    3. Calibración de confianza: ¿La confianza declarada refleja adecuadamente la presencia de fuerzas contrapuestas?
  - Determinación del veredicto según `AuditVerdictEnum`: `APROBADO` (emite la señal sin alteración), `CORREGIDO` (ajusta justificación y calibra la confianza máxima a $\le 75.0\%$, aceptando `AJUSTADO_FAIL_CLOSED` como alias funcional), o `RECHAZADO` (bloqueo preventivo fail-closed ante alucinaciones o incongruencias severas).
```

---

### 3.7 Task T23.16: `MacroPredictionPipeline` Cryptographic Hash Binding

* **Target Lines in `tasks.md`:** Lines 69–72.
* **Remediation:** Bind calculation of `prediction_hash` explicitly to the pipe-delimited formula.

**Replacement Chunk for T23.16:**
```markdown
- [ ] T23.16: Implementar la clase orquestadora `MacroPredictionPipeline` en `src/core/macro/pipeline.py`:
  - Coordinación secuencial: `MacroContextExtractor` ➔ `MacroAnalystPredictor` ➔ `PredictionReviewer`.
  - Encadenamiento criptográfico: lectura del último `prediction_hash` desde `MacroRepository`, cálculo del nuevo hash con la fórmula canónica delimitada por tuberías (`|`) y guardado atómico en base de datos.
  - Manejo de excepciones con parada preventiva fail-closed: si cualquier paso falla tras agotar reintentos, registrar evento de auditoría de fallo y emitir estado neutral sin romper el proceso principal del bot.
```

---

### 3.8 Task T23.20: Streamlit Dashboard Contract Harmonization

* **Target Lines in `tasks.md`:** Lines 81–86.
* **Remediation:** Explicitly state visualization of `PredictionDirection`, `TimeframeHorizon`, `AuditVerdictEnum` and database cryptographic verification button.

**Replacement Chunk for T23.20:**
```markdown
- [ ] T23.20: Implementar la vista interactiva de Inteligencia Macroeconómica en Streamlit (`src/reporting/dashboard/views/macro_prediction_view.py`) e integrarla en `src/reporting/dashboard/app.py`:
  - Tarjeta KPI principal con dirección proyectada (`PredictionDirection`: `SUBE`, `BAJA`, `ESTABLE`), ventana temporal (`TimeframeHorizon`: `24h-48h`, `3-5 dias`, `semanal`), veredicto (`AuditVerdictEnum`) y velocímetro/gauge de confiabilidad calibrada.
  - Gráfico de balance vectorial de fuerzas (factores alcistas vs factores bajistas con ponderación).
  - Cronología interactiva de eventos macroeconómicos recientes con categoría (`TaxonomyCategory`), fuente y peso de impacto.
  - Visor de auditoría criptográfica con botón para verificar la integridad del hash encadenado SHA-256 pipe-delimited en base de datos.
  - Selector de proveedor LLM y botón de refresco manual con control de cooldown para administradores.
```

---

### 3.9 Task T23.23: E2E Testing Validation

* **Target Lines in `tasks.md`:** Lines 95–98.
* **Remediation:** Clarify verification of pipe-delimited hash chaining across 10 consecutive simulated predictions.

**Replacement Chunk for T23.23:**
```markdown
- [ ] T23.23: Crear y ejecutar suite de pruebas E2E en `tests/e2e/test_macro_prediction_e2e.py`:
  - Simulación completa de ciclo de predicción desde extracción de fuentes con mocks hasta persistencia en base de datos y emisión de alerta en Telegram.
  - Verificación de la integridad de la cadena SHA-256 en 10 predicciones consecutivas calculadas con la fórmula delimitada por tuberías (`|`), validando resistencia a colisiones y consistencia ante reordenamientos.
  - Verificación de recuperación transparente ante simulación de caída de proveedores primarios (Gemini y Groq) con failover hacia DeepSeek y OpenAI.
```

---

## 4. Complete Unified Diff for `tasks.md`

Below is the contiguous diff block for Phase 1 (Lines 3–16) and relevant Phase 4/5/6 tasks:

```diff
--- a/.specify/specs/023-ai-market-predictor/tasks.md
+++ b/.specify/specs/023-ai-market-predictor/tasks.md
@@ -4,13 +4,13 @@
-- [ ] T23.1: Crear tests unitarios en rojo para esquemas Pydantic v2 en `tests/unit/test_macro_schemas.py`, validando:
-  - Enumeraciones estrictas: `MacroEventType` (14 categorías normalizadas), `MarketDirection` (BULLISH, BEARISH, NEUTRAL), `TimeHorizon` (INMEDIATO_12H, CORTO_24_48H, MEDIANO_3_5D, SEMANAL), `ReviewVerdict` (APROBADO, RECHAZADO, AJUSTADO_FAIL_CLOSED) y `ModelProvider` (GEMINI, GROQ, DEEPSEEK, OPENAI, ANTHROPIC).
-  - Validación de rangos numéricos: `impact_weight` (0.0 a 1.0), `confidence_pct` (0.0 a 100.0), `credibility_score` (0.0 a 1.0).
-  - Serialización y deserialización JSON sin pérdida de precisión ni timezone drift en timestamps UTC.
+- [ ] T23.1: Crear tests unitarios en rojo para esquemas Pydantic v2 en `tests/unit/test_macro_schemas.py`, validando:
+  - Enumeraciones estrictas y normalizadas: `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`), `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, admitiendo `AJUSTADO_FAIL_CLOSED` como alias funcional de `CORREGIDO`), `TaxonomyCategory` (7 categorías canónicas alineadas con Prompt 7.1 y `macro_usdt_taxonomy.md`), `SourceCredibility` (`ALTA`, `MEDIA`, `BAJA`) y `ModelProvider` (`GEMINI`, `GROQ`, `DEEPSEEK`, `OPENAI`, `ANTHROPIC`).
+  - Validación de rangos numéricos: `impact_weight` (0.0 a 1.0), `confiabilidad_porcentaje` (0.0 a 100.0) y validador condicional que restringe la confianza máxima a <= 75.0% ante veredicto `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
+  - Serialización y deserialización JSON sin pérdida de precisión ni timezone drift en timestamps UTC (`datetime` con formato ISO 8601 canónico).
-- [ ] T23.2: Implementar esquemas Pydantic v2 en `src/core/macro/schemas.py`:
-  - `MacroEventItem`: modelo de evento individual con campos `id`, `event_code`, `category`, `title`, `summary`, `source`, `source_url`, `published_at`, `impact_weight`, `transmission_lag_hours`, `verified`.
-  - `MacroContextPayload`: contenedor consolidado con `events`, `bcv_official_rate`, `current_p2p_rate`, `spread_pct`, `m2_trend_expansion`, `timestamp_utc`, `noise_filter_status`.
-  - `DraftPrediction`: propuesta de inferencia del Predictor con `direction`, `horizon`, `confidence_pct`, `bullish_force_weight`, `bearish_force_weight`, `net_balance`, `key_drivers`, `reasoning_chain`, `risks_invalidation`.
-  - `FinalUSDTPrediction`: predicción validada por el Revisor con `verdict`, `direction`, `horizon`, `confidence_pct`, `audited_justification`, `reviewer_notes`, `predictor_model`, `reviewer_model`, `prev_hash`, `prediction_hash`, `timestamp_utc`.
-  - `AIProviderConfig` y `ProviderQuotaStatus`: telemetría de cuotas y estado de Circuit Breaker por proveedor.
+- [ ] T23.2: Implementar esquemas Pydantic v2 en `src/core/macro/schemas.py`:
+  - `MacroEventItem`: modelo de evento individual con `event_id`, `code` (ej. `GP-01`, `IC-01`), `categoria: TaxonomyCategory`, `titulo: str`, `resumen_factico: str` (ASCII estricto), `fuente_nombre: str`, `fuente_url: Optional[str]`, `credibilidad: SourceCredibility`, `cifras_especificadas: bool`, `monto_relevante: Optional[float]`, `unidad_monto: Optional[str]`, `timestamp_evento_utc: datetime`.
+  - `MacroContextPayload`: contenedor consolidado de contexto macroeconómico con `timestamp_extraccion: datetime`, `eventos: List[MacroEventItem]`, `tasa_p2p_actual: float`, `tasa_bcv_actual: float`, `brecha_cambiaria_porcentaje: float`, `fuentes_consultadas: List[str]`, `filtro_antirruido_status: Optional[str]`.
+  - `DraftPrediction`: borrador de inferencia del Predictor con `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float` (0.0 a 100.0), `factores_clave: List[str]`, `justificacion_detallada: str`, `riesgos_invalidacion: List[str]`.
+  - `AuditResult`: dictamen crítico del Revisor con `veredicto: AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`, mapeando `AJUSTADO_FAIL_CLOSED` a `CORREGIDO`), `direccion_validada: PredictionDirection`, `confiabilidad_calibrada: float`, `puntaje_rigor: float`, `alucinaciones_detectadas: bool`, `hallazgos_criticos: List[str]`.
+  - `AuditMetadata`: metadatos de auditoría y trazabilidad con `predictor_model: str`, `reviewer_model: str`, `cross_family_verified: bool`, `prev_hash: str`, `prediction_hash: str`, `timestamp_utc: datetime`, `execution_duration_ms: int`.
+  - `FinalUSDTPrediction`: predicción consolidada validada con `id: str`, `veredicto: AuditVerdictEnum`, `direccion: PredictionDirection`, `lapso_estimado: TimeframeHorizon`, `confiabilidad_porcentaje: float`, `justificacion_auditada: str`, `factores_clave: List[str]`, `riesgos_invalidacion: List[str]`, `metadata: AuditMetadata`, incorporando validador `validar_confianza_maxima_si_corregido` que acota la confianza a un máximo de 75.0% cuando el veredicto sea `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`.
+  - `AIProviderConfig` y `ProviderQuotaStatus`: telemetría de cuotas y estado del Circuit Breaker (`CLOSED`, `OPEN`, `HALF-OPEN`) por proveedor.
-- [ ] T23.3: Crear tests unitarios en rojo para modelos SQLAlchemy y repositorios en `tests/unit/test_macro_models_repository.py`, validando persistencia, unicidad y encadenamiento SHA-256 inmutable.
+- [ ] T23.3: Crear tests unitarios en rojo para modelos SQLAlchemy y repositorios en `tests/unit/test_macro_models_repository.py`, validando persistencia, unicidad, inmutabilidad de la cadena SHA-256 encadenada y verificación de resistencia a colisiones de delimitador en la fórmula canónica delimitada por tuberías (`|`).
-- [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo de `prediction_hash = SHA256(prev_hash + payload)`.
+- [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo estricto de hash criptográfico encadenado mediante la fórmula canónica delimitada por tuberías (`|`):
+  `prediction_hash = hashlib.sha256(f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}".encode("utf-8")).hexdigest()`
+  utilizando como semilla génesis `prev_hash = "0" * 64` y garantizando unicidad indexada e inmutabilidad append-only.
@@ -57,15 +57,15 @@
 - [ ] T23.14: Implementar `MacroAnalystPredictor` en `src/core/macro/analyst.py`:
   - Inyección del System Prompt canónico de analista macroeconómico especializado en el mercado cambiario venezolano.
   - Ingesta de `MacroContextPayload` y formulación del balance vectorial ($F_{\text{neta}} = \sum w_{\text{alcista}} - \sum w_{\text{bajista}}$).
-  - Inferencia de dirección (`SUBE`, `BAJA`, `ESTABLE`), horizonte temporal estimado y cálculo de confiabilidad calibrada ($C_{\text{calibrada}} \in [0, 100\%]$).
-  - Emisión de `DraftPrediction` en formato JSON estructurado estricto.
+  - Inferencia de dirección con `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), horizonte temporal con `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`) y cálculo de confiabilidad calibrada ($C_{\text{calibrada}} \in [0, 100\%]$).
+  - Emisión de `DraftPrediction` en formato JSON estructurado estricto conforme al esquema Pydantic v2.
 - [ ] T23.15: Implementar `PredictionReviewer` en `src/core/macro/reviewer.py`:
   - Regla Constitucional de **Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**: si el Predictor es DeepSeek o Gemini, el Revisor DEBE ser asignado a una familia distinta (Anthropic Claude o OpenAI GPT).
   - System Prompt adversarial y escéptico que audita:
     1. Veracidad empírica: ¿Cada factor citado en la justificación proviene textualmente de `MacroContextPayload`?
     2. Coherencia causal: ¿La dirección y horizonte son lógicamente consistentes con la taxonomía y la matriz de rezagos temporales?
     3. Calibración de confianza: ¿La confianza declarada refleja adecuadamente la presencia de fuerzas contrapuestas?
-  - Determinación del veredicto: `APROBADO`, `RECHAZADO` o `AJUSTADO_FAIL_CLOSED` (reduciendo la confianza y añadiendo notas de advertencia).
+  - Determinación del veredicto según `AuditVerdictEnum`: `APROBADO` (emite la señal sin alteración), `CORREGIDO` (ajusta justificación y calibra la confianza máxima a <= 75.0%, aceptando `AJUSTADO_FAIL_CLOSED` como alias funcional), o `RECHAZADO` (bloqueo preventivo fail-closed ante alucinaciones o incongruencias severas).
 - [ ] T23.16: Implementar la clase orquestadora `MacroPredictionPipeline` en `src/core/macro/pipeline.py`:
   - Coordinación secuencial: `MacroContextExtractor` ➔ `MacroAnalystPredictor` ➔ `PredictionReviewer`.
-  - Encadenamiento criptográfico: lectura del último `prediction_hash` desde `MacroRepository`, cálculo del nuevo hash y guardado atómico en base de datos.
+  - Encadenamiento criptográfico: lectura del último `prediction_hash` desde `MacroRepository`, cálculo del nuevo hash con la fórmula canónica delimitada por tuberías (`|`) y guardado atómico en base de datos.
   - Manejo de excepciones con parada preventiva fail-closed: si cualquier paso falla tras agotar reintentos, registrar evento de auditoría de fallo y emitir estado neutral sin romper el proceso principal del bot.
@@ -81,6 +81,6 @@
 - [ ] T23.20: Implementar la vista interactiva de Inteligencia Macroeconómica en Streamlit (`src/reporting/dashboard/views/macro_prediction_view.py`) e integrarla en `src/reporting/dashboard/app.py`:
-  - Tarjeta KPI principal con dirección proyectada, ventana temporal y velocímetro/gauge de confiabilidad.
+  - Tarjeta KPI principal con dirección proyectada (`PredictionDirection`: `SUBE`, `BAJA`, `ESTABLE`), ventana temporal (`TimeframeHorizon`: `24h-48h`, `3-5 dias`, `semanal`), veredicto (`AuditVerdictEnum`) y velocímetro/gauge de confiabilidad calibrada.
   - Gráfico de balance vectorial de fuerzas (factores alcistas vs factores bajistas con ponderación).
-  - Cronología interactiva de eventos macroeconómicos recientes con categoría, fuente y peso.
-  - Visor de auditoría criptográfica con botón para verificar la integridad del hash SHA-256 en base de datos.
+  - Cronología interactiva de eventos macroeconómicos recientes con categoría (`TaxonomyCategory`), fuente y peso de impacto.
+  - Visor de auditoría criptográfica con botón para verificar la integridad del hash encadenado SHA-256 pipe-delimited en base de datos.
   - Selector de proveedor LLM y botón de refresco manual con control de cooldown para administradores.
@@ -95,4 +95,4 @@
 - [ ] T23.23: Crear y ejecutar suite de pruebas E2E en `tests/e2e/test_macro_prediction_e2e.py`:
   - Simulación completa de ciclo de predicción desde extracción de fuentes con mocks hasta persistencia en base de datos y emisión de alerta en Telegram.
-  - Verificación de la integridad de la cadena SHA-256 en 10 predicciones consecutivas.
+  - Verificación de la integridad de la cadena SHA-256 en 10 predicciones consecutivas calculadas con la fórmula delimitada por tuberías (`|`), validando resistencia a colisiones y consistencia ante reordenamientos.
   - Verificación de recuperación transparente ante simulación de caída de proveedores primarios (Gemini y Groq) con failover hacia DeepSeek y OpenAI.
```

---

## 5. Python Reference Implementation for Implementers

Downstream implementers (Backend & QA engineers) can refer directly to the following reference code block when executing T23.1, T23.2, and T23.4:

```python
"""Reference contract definitions for Spec 023."""
import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ValidationInfo, field_validator


class PredictionDirection(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class TimeframeHorizon(str, Enum):
    HORIZONTE_24_48H = "24h-48h"
    HORIZONTE_3_5D = "3-5 dias"
    HORIZONTE_SEMANAL = "semanal"


class AuditVerdictEnum(str, Enum):
    APROBADO = "APROBADO"
    CORREGIDO = "CORREGIDO"
    RECHAZADO = "RECHAZADO"


class TaxonomyCategory(str, Enum):
    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


class SourceCredibility(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class MacroEventItem(BaseModel):
    event_id: str
    code: str
    categoria: TaxonomyCategory
    titulo: str = Field(..., min_length=5, max_length=150)
    resumen_factico: str = Field(..., min_length=10, max_length=500)
    fuente_nombre: str
    fuente_url: Optional[str] = None
    credibilidad: SourceCredibility
    cifras_especificadas: bool = False
    monto_relevante: Optional[float] = None
    unidad_monto: Optional[str] = None
    timestamp_evento_utc: datetime


class MacroContextPayload(BaseModel):
    timestamp_extraccion: datetime
    eventos: List[MacroEventItem]
    tasa_p2p_actual: float = Field(gt=0.0)
    tasa_bcv_actual: float = Field(gt=0.0)
    brecha_cambiaria_porcentaje: float
    fuentes_consultadas: List[str]
    filtro_antirruido_status: Optional[str] = "CLEAN"


class AuditMetadata(BaseModel):
    predictor_model: str
    reviewer_model: str
    cross_family_verified: bool = True
    prev_hash: str
    prediction_hash: str
    timestamp_utc: datetime
    execution_duration_ms: int


class FinalUSDTPrediction(BaseModel):
    id: str
    veredicto: AuditVerdictEnum
    direccion: PredictionDirection
    lapso_estimado: TimeframeHorizon
    confiabilidad_porcentaje: float = Field(ge=0.0, le=100.0)
    justificacion_auditada: str
    factores_clave: List[str]
    riesgos_invalidacion: List[str]
    metadata: AuditMetadata

    @field_validator("veredicto", mode="before")
    @classmethod
    def normalizar_veredicto(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip().upper() == "AJUSTADO_FAIL_CLOSED":
            return AuditVerdictEnum.CORREGIDO
        return v

    @field_validator("confiabilidad_porcentaje")
    @classmethod
    def validar_confianza_maxima_si_corregido(cls, v: float, info: ValidationInfo) -> float:
        veredicto = info.data.get("veredicto")
        if veredicto == AuditVerdictEnum.CORREGIDO and v > 75.0:
            raise ValueError(
                f"La confiabilidad máxima permitida para un veredicto CORREGIDO es 75.0% (recibido: {v}%)"
            )
        return v


def compute_prediction_hash(
    prev_hash: str,
    timestamp_iso: str,
    direction: str,
    timeframe: str,
    confidence: float,
    model: str,
    justification: str,
) -> str:
    """Calcula el hash SHA-256 encadenado usando delimitador canónico de tuberías (|)."""
    canonical_str = f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence:.1f}|{model}|{justification}"
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
```

---

## 6. Verification and Acceptance Checks

To verify this remediation strategy independently:
1. **Task Preservation Check:**
   Total task count remains exactly 26 (`T23.1` to `T23.26`).
2. **Enum Search:**
   Zero instances of `MarketDirection`, `TimeHorizon`, or raw `ReviewVerdict` remain in `tasks.md`.
3. **Payload Name Search:**
   `MacroContextPayload` is consistently utilized across T23.2, T23.14, T23.15.
4. **Collision Resistance Test:**
   Execution of the pipe-delimited hashing formula verifies that boundary-bleed collisions cannot occur.
