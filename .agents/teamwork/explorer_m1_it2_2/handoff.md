# Handoff Report: Tasks Harmonization Strategist (M1_IT2_2)

**Agent**: Explorer M1_IT2_2 (`explorer_m1_it2_2`)  
**Mission**: Tasks Harmonization Strategy for `tasks.md` (SPEC-023)  
**Date**: 2026-11-17T00:50:00Z  
**Recipient**: Orchestrator (`fefc4a8c-cb37-4d70-9d05-32d746794690`)  
**Status**: COMPLETE (Hard Handoff)  

---

## 1. Observation

Direct observations and evidence gathered during the investigation:

1. **Obs 1: Discrepancy in Direction and Horizon Enums in `tasks.md` vs `plan.md` & `PROJECT.md`**
   - **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\tasks.md`
   - **Line 5 (Task T23.1)**:
     ```markdown
     - Enumeraciones estrictas: `MacroEventType` (14 categorías normalizadas), `MarketDirection` (BULLISH, BEARISH, NEUTRAL), `TimeHorizon` (INMEDIATO_12H, CORTO_24_48H, MEDIANO_3_5D, SEMANAL), `ReviewVerdict` (APROBADO, RECHAZADO, AJUSTADO_FAIL_CLOSED) y `ModelProvider` (GEMINI, GROQ, DEEPSEEK, OPENAI, ANTHROPIC).
     ```
   - **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
   - **Lines 326–335**:
     ```python
     class PredictionDirection(str, Enum):
         SUBE = "SUBE"
         BAJA = "BAJA"
         ESTABLE = "ESTABLE"

     class TimeframeHorizon(str, Enum):
         HORIZONTE_24_48H = "24h-48h"
         HORIZONTE_3_5D = "3-5 dias"
         HORIZONTE_SEMANAL = "semanal"
     ```
   - **File**: `c:\p2p-bot-merchant\.agents\teamwork\orchestrator_1\PROJECT.md`
   - **Lines 46–47**:
     ```markdown
     - `direccion_propuesta`: Enum ["SUBE", "BAJA", "ESTABLE"]
     - `lapso_estimado`: str (ej. "24h-48h", "3-5 dias", "semanal")
     ```
   - **Finding**: T23.1 requires tests for `MarketDirection` (BULLISH/BEARISH/NEUTRAL) and `TimeHorizon` (INMEDIATO_12H, etc.), which contradicts `plan.md`, `PROJECT.md`, `spec.md`, and Prompt 7.2/7.3.

2. **Obs 2: Verdict Enum Incoherence between `tasks.md`, `plan.md`, and `PROJECT.md`**
   - **File**: `tasks.md` Line 5 & Line 68 (T23.15): `ReviewVerdict` (`APROBADO`, `RECHAZADO`, `AJUSTADO_FAIL_CLOSED`).
   - **File**: `plan.md` Line 338: `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`).
   - **File**: `PROJECT.md` Line 54: `veredicto`: Enum `["APROBADO", "RECHAZADO", "AJUSTADO_FAIL_CLOSED"]`.
   - **Finding**: Three different representations exist for the auditor verdict across core artifacts.

3. **Obs 3: Payload Container Name Discrepancy**
   - **File**: `tasks.md` Line 10 (T23.2): `MacroContextPayload`.
   - **File**: `PROJECT.md` Line 40: `MacroContextPayload`.
   - **File**: `plan.md` Line 359: `class MacroContextCollection(BaseModel):` (while Line 89 uses `MacroContextPayload`).
   - **Finding**: `MacroContextPayload` is the established standard in `PROJECT.md` and `tasks.md`, but `plan.md` introduced `MacroContextCollection`.

4. **Obs 4: Cryptographic Hashing Collision Vulnerability in T23.4**
   - **File**: `tasks.md` Line 15 (T23.4):
     ```markdown
     - [ ] T23.4: Implementar modelos SQLAlchemy `MacroEvent` y `MacroPrediction` en `src/data/models.py`, actualizar migración de esquema en `init_db()` (`src/data/database.py`), y crear `MacroRepository` en `src/data/repositories.py` con inserción idempotente, consulta por ventana temporal y cálculo de `prediction_hash = SHA256(prev_hash + payload)`.
     ```
   - **Empirical Execution Command**:
     ```powershell
     python -c "
     import hashlib
     prev = '0'*64; ts = '2026-11-17T00:00:00Z'; conf = '85.0'; just = 'test'
     p1 = (prev + ts + 'SUB' + 'E24h' + conf + just).encode()
     p2 = (prev + ts + 'SUBE' + '24h' + conf + just).encode()
     print('Collided without delimiter:', hashlib.sha256(p1).hexdigest() == hashlib.sha256(p2).hexdigest())
     "
     ```
   - **Output**: `Collided without delimiter: True`.
   - **Empirical Verification of Pipe-Delimited Formula**:
     ```powershell
     python -c "
     import hashlib
     prev = '0'*64; ts = '2026-11-17T00:00:00Z'; conf = '85.0'; just = 'test'; model = 'claude-3-5-sonnet'
     p1 = f'{prev}|{ts}|SUB|E24h|{conf}|{model}|{just}'.encode('utf-8')
     p2 = f'{prev}|{ts}|SUBE|24h|{conf}|{model}|{just}'.encode('utf-8')
     print('Collided with pipe:', hashlib.sha256(p1).hexdigest() == hashlib.sha256(p2).hexdigest())
     "
     ```
   - **Output**: `Collided with pipe: False`.

5. **Obs 5: Downstream Task Cascades**
   - Tasks T23.14, T23.15, T23.16, T23.20, and T23.23 in `tasks.md` directly depend on the harmonized enums and pipe-delimited hashing formula.

---

## 2. Logic Chain

1. **Enum Standardization (Obs 1 & 2)**:
   - System prompts 7.1, 7.2, and 7.3 instruct LLMs to produce structured JSON in Spanish with `SUBE`/`BAJA`/`ESTABLE` for direction and `24h-48h`/`3-5 dias`/`semanal` for horizon.
   - If tests in T23.1 enforce `MarketDirection` (BULLISH/BEARISH/NEUTRAL) and `TimeHorizon`, any test asserting contract compliance with `plan.md` or LLM outputs will immediately fail.
   - Therefore, T23.1 must be updated to require unit tests for `PredictionDirection` and `TimeframeHorizon`.

2. **Verdict Harmonization with Aliasing (Obs 2)**:
   - `AuditVerdictEnum` in `plan.md` defines `APROBADO`, `CORREGIDO`, `RECHAZADO`.
   - `PROJECT.md` and constitutional rules specify `AJUSTADO_FAIL_CLOSED` as a protective state.
   - By declaring `AuditVerdictEnum` with members `APROBADO`, `CORREGIDO`, `RECHAZADO` and incorporating a Pydantic `before` validator (or enum member alias) that normalizes `AJUSTADO_FAIL_CLOSED` to `AuditVerdictEnum.CORREGIDO`, 100% interoperability across all documents and runtime components is guaranteed.
   - Furthermore, attaching the validator `validar_confianza_maxima_si_corregido` caps confidence at $\le 75.0\%$ when veredicto is `CORREGIDO` / `AJUSTADO_FAIL_CLOSED`, fulfilling constitutional fail-closed requirements.

3. **Payload Name Harmonization (Obs 3)**:
   - `tasks.md` and `PROJECT.md` both use `MacroContextPayload`.
   - Reaffirming `MacroContextPayload` across T23.2 and notifying sibling explorer M1_IT2_1 to rename `MacroContextCollection` in `plan.md` ensures full cross-document naming consistency.

4. **Cryptographic Collision Elimination (Obs 4)**:
   - Concatenating un-delimited variable-length strings creates boundary-bleed collisions.
   - The pipe-delimited specification `f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}"` introduces unambiguous byte-level separators.
   - Updating T23.4 (and dependent tasks T23.3, T23.16, T23.23) eliminates cryptographic weakness and satisfies Challenger 2's requirement.

---

## 3. Caveats

- **No modifications made to `tasks.md` directly**: In adherence to the read-only explorer role, the changes are formulated as an actionable diff and strategy document (`tasks_fix_strategy.md`) for the parent orchestrator and worker agent to apply.
- **`plan.md` alignment**: Sibling agent `explorer_m1_it2_1` is responsible for updating `plan.md` with the matching `MacroContextPayload` and `validar_confianza_maxima_si_corregido` logic.
- **Task numbering**: All 26 tasks (`T23.1` to `T23.26`) are preserved without addition or removal to prevent breaking SDD validation scripts.

---

## 4. Conclusion

The remediation strategy for `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\tasks.md` has been fully formulated and delivered in:
`c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_2\tasks_fix_strategy.md`

Key remediations defined:
1. **T23.1**: Replaced `MarketDirection` with `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`), `TimeHorizon` with `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`), `ReviewVerdict` with `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO` with `AJUSTADO_FAIL_CLOSED` alias), and added `TaxonomyCategory` (7 categories).
2. **T23.2**: Reaffirmed `MacroContextPayload`, added ASCII field `resumen_factico`, `AuditResult`, `AuditMetadata`, and validator capping confidence at 75.0% on corrected predictions.
3. **T23.4**: Explicitly mandated canonical pipe-delimited SHA-256 chaining formula:
   `prediction_hash = hashlib.sha256(f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}".encode("utf-8")).hexdigest()`.
4. **T23.14, T23.15, T23.16, T23.20, T23.23**: Synchronized with harmonized enums, payload name, and pipe-delimited hash verification.

---

## 5. Verification Method

To independently verify the strategy and reference implementation, execute:

```powershell
# 1. Verify Pydantic v2 alias and confidence capping logic:
python -c "
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ValidationInfo, field_validator

class AuditVerdictEnum(str, Enum):
    APROBADO = 'APROBADO'
    CORREGIDO = 'CORREGIDO'
    RECHAZADO = 'RECHAZADO'

class M(BaseModel):
    veredicto: AuditVerdictEnum
    conf: float = Field(ge=0.0, le=100.0)

    @field_validator('veredicto', mode='before')
    @classmethod
    def norm_verdict(cls, v: Any) -> Any:
        return AuditVerdictEnum.CORREGIDO if str(v).upper() == 'AJUSTADO_FAIL_CLOSED' else v

    @field_validator('conf')
    @classmethod
    def cap_conf(cls, v: float, info: ValidationInfo) -> float:
        if info.data.get('veredicto') == AuditVerdictEnum.CORREGIDO and v > 75.0:
            raise ValueError('Cap exceeded')
        return v

# Test normal execution:
m1 = M(veredicto='AJUSTADO_FAIL_CLOSED', conf=70.0)
assert m1.veredicto == AuditVerdictEnum.CORREGIDO
print('Verification 1 Passed: AJUSTADO_FAIL_CLOSED alias normalized')

# Test cap enforcement:
try:
    M(veredicto='AJUSTADO_FAIL_CLOSED', conf=85.0)
    assert False, 'Should have raised ValueError'
except ValueError:
    print('Verification 2 Passed: 75.0% confidence cap strictly enforced')
"

# 2. Verify delimiter collision absence:
python -c "
import hashlib
prev = '0'*64; ts = '2026-11-17T00:00:00Z'; conf = '85.0'; just = 'test'; model = 'claude-3-5-sonnet'
p1 = f'{prev}|{ts}|SUB|E24h|{conf}|{model}|{just}'.encode('utf-8')
p2 = f'{prev}|{ts}|SUBE|24h|{conf}|{model}|{just}'.encode('utf-8')
assert hashlib.sha256(p1).hexdigest() != hashlib.sha256(p2).hexdigest()
print('Verification 3 Passed: Pipe-delimited hashing prevents collision')
"
```
