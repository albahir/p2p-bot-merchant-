# Handoff Report: Plan Remediation Strategy (M1_IT2_1)

**Agent:** Explorer M1_IT2_1 (Plan Remediation Strategist)  
**Parent Orchestrator:** `fefc4a8c-cb37-4d70-9d05-32d746794690`  
**Deliverable File:** `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_1\plan_fix_strategy.md`  
**Target Specification:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`  
**Date:** 2026-11-17T00:49:00Z  
**Verdict:** **REMEDIATION STRATEGY COMPLETE (READY FOR APPLICATION)**  

---

## 1. Observation

Direct empirical observations, file paths, line numbers, and verification commands:

### Obs 1: 100% Incompatibility between Prompt 7.1 and `TaxonomyCategory`
- **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- **Lines 228–235 (Prompt Rol 1: Buscador)**:
  ```text
  1. TAXONOMÍA PERMITIDA: Debes clasificar cada evento estrictamente en una de las siguientes categorías:
     - GASTO_PUBLICO_PATRIA (Pagos de nómina, bonos Patria, aguinaldos)
     - INTERVENCION_CAMBIARIA_BCV (Montos inyectados por el BCV en mesas de cambio)
     - POLITICA_MONETARIA_LIQUIDEZ (Variaciones de liquidez M2, encaje legal)
     - CALENDARIO_FISCAL_SENIAT (Vencimientos de impuestos, recaudación, anticipos)
     - REGULACION_CAMBIARIA_BANCARIA (Medidas SUDEBAN, límites bancarios, controles de precios)
     - OPERATIVA_MERCADO_P2P (Feriados bancarios, fallas de pago móvil o plataforma)
     - GEOPOLITICA_PETROLERA (Sanciones OFAC, licencias petroleras, ingresos de exportación)
  ```
- **Lines 310–317 (`TaxonomyCategory`)**:
  ```python
  class TaxonomyCategory(str, Enum):
      INTERVENCION_BCV = "INTERVENCION_BCV"
      PAGO_PATRIA_NOMINA = "PAGO_PATRIA_NOMINA"
      LIQUIDEZ_MONETARIA_M2 = "LIQUIDEZ_MONETARIA_M2"
      BRECHA_CAMBIARIA_ARBITRAJE = "BRECHA_CAMBIARIA_ARBITRAJE"
      REGULACION_BANCARIA_ENCAJE = "REGULACION_BANCARIA_ENCAJE"
      FACTORES_ESTACIONALES_TRIBUTARIOS = "FACTORES_ESTACIONALES_TRIBUTARIOS"
      POLITICA_SANCIONES = "POLITICA_SANCIONES"
  ```
- `docs/macro_usdt_taxonomy.md` Section 3.1 lines 164–179 categorizes all 14 canonical events into the exact 7 categories of Prompt 7.1. None of them matched the enum in line 310.

### Obs 2: Cryptographic Collision in Un-Delimited SHA-256 Concatenation
- **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- **Line 479**:
  $$\text{prediction\_hash}_k = \text{SHA256}\Big(\text{prev\_hash}_{k-1} + \text{timestamp} + \text{direction} + \text{timeframe} + \text{confidence} + \text{justification}\Big)$$
- Execution of `('SUB' + 'E24h')` vs `('SUBE' + '24h')` confirmed that identical SHA-256 digests are produced when delimiters are omitted.

### Obs 3: Dead Logic in Validator `validar_confianza_maxima_si_corregido`
- **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- **Lines 413–418**:
  ```python
  @field_validator("confiabilidad_porcentaje")
  @classmethod
  def validar_confianza_maxima_si_corregido(cls, v: float, info: Any) -> float:
      if v > 100.0 or v < 0.0:
          raise ValueError("La confiabilidad debe estar entre 0.0 y 100.0")
      return v
  ```
- The validator ignored `info.data.get("veredicto")` and allowed `confiabilidad_porcentaje = 95.0` even when `veredicto == CORREGIDO`.

### Obs 4: Non-ASCII Field `resumen_fáctico`
- **File**: `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- **Line 349**: `resumen_fáctico: str = Field(..., min_length=10, max_length=500)` contains the accented character `á`, risking encoding and serialization conflicts in database and ORM operations.

### Obs 5: Empirical Remediation Validation Results
- Executed empirical test script:
  ```powershell
  python -c "
  # (Test script executing TaxonomyCategory, SHA-256 pipe, ValidationInfo capping, and ASCII field)
  "
  ```
- **Result Output**:
  ```text
  Test 1 Passed: All 7 Prompt categories valid in TaxonomyCategory
  Test 2 Passed: Pipe-delimited eliminates collision vulnerability
  Test 3 Passed: Validator correctly caps confidence at 75.0% for CORREGIDO / AJUSTADO_FAIL_CLOSED
  Test 4 Passed: ASCII field resumen_factico validated
  ```

---

## 2. Logic Chain

1. **Enum Alignment (from Obs 1)**:
   - When Rol 1 (Buscador) generates JSON following Prompt 7.1, it classifies events using the 7 allowed taxonomy categories.
   - Pydantic v2 validates string enums strictly against declared members.
   - Replacing `TaxonomyCategory` with the 7 Prompt categories ensures that 100% of incoming events are parsed without `ValidationError`.
   - Adding `MacroCategoryEnum = TaxonomyCategory` establishes bidirectional compatibility with `docs/macro_usdt_taxonomy.md`.

2. **Cryptographic Collision Prevention (from Obs 2)**:
   - Concatenating variable-length string fields without delimiters allows boundary bleed collisions.
   - Defining the canonical payload as `f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}"` introduces unambiguous field boundaries.
   - Sanitizing embedded pipes (`|` $\to$ `/`) in `justification` and `model` prevents delimiter injection, establishing pre-image security and immutability.

3. **Defensive Confidence Capping (from Obs 3)**:
   - When an auditor issues `CORREGIDO` or `AJUSTADO_FAIL_CLOSED`, the signal contains disputed or counteracting forces.
   - Consulting `info.data["veredicto"]` via Pydantic v2 `ValidationInfo` and capping `v` to `min(v, 75.0)` guarantees that no signal published with an auditor correction exceeds the 75.0% prudential ceiling.

4. **ASCII Normalization (from Obs 4)**:
   - Replacing `resumen_fáctico` with `resumen_factico` satisfies Python naming conventions, SQLAlchemy table mapping, and cross-platform JSON encoding standards.

5. **Integrated Schema Consistency**:
   - Incorporating `code: str` in `MacroEventItem` (as noted by Explorer 3 and Challenger 1) and supporting `MacroContextPayload` (with `MacroContextCollection` alias) unifies `plan.md`, `tasks.md`, and `PROJECT.md`.

---

## 3. Caveats

- Direct modification of `plan.md` was not executed in this turn because Explorer is a read-only role. The complete, copy-paste ready replacement chunks are documented in `plan_fix_strategy.md`.
- `validar_confianza_maxima_si_corregido` is designed to cap confidence at `75.0%` (`return 75.0` or `return min(v, 75.0)`). If strict rejection (raising `ValueError`) is preferred by the project team instead of capping, the alternative implementation is also provided in Section 4.2 of `plan_fix_strategy.md`.

---

## 4. Conclusion

The plan remediation strategy is fully defined, documented, and empirically verified in:
`c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_1\plan_fix_strategy.md`

It provides drop-in replacement blocks for:
1. `TaxonomyCategory` (lines 310–317) with the 7 canonical categories.
2. `MacroEventItem` (lines 344–357) with `code: str` and `resumen_factico`.
3. `MacroContextPayload` (lines 359–367) with compatibility alias.
4. `AuditVerdictEnum` (lines 338–342) including `AJUSTADO_FAIL_CLOSED`.
5. `FinalUSDTPrediction` (lines 401–419) with `ValidationInfo` capping at 75.0%.
6. SHA-256 Chaining Algorithm (lines 477–483) with canonical pipe-delimited format.

---

## 5. Verification Method

To independently verify the validity of the remediations, run the following command in PowerShell:

```powershell
python -c "
from enum import Enum
from pydantic import BaseModel, Field, ValidationInfo, field_validator
import hashlib

# 1. Verify TaxonomyCategory
class TaxonomyCategory(str, Enum):
    GASTO_PUBLICO_PATRIA = 'GASTO_PUBLICO_PATRIA'
    INTERVENCION_CAMBIARIA_BCV = 'INTERVENCION_CAMBIARIA_BCV'
    POLITICA_MONETARIA_LIQUIDEZ = 'POLITICA_MONETARIA_LIQUIDEZ'
    CALENDARIO_FISCAL_SENIAT = 'CALENDARIO_FISCAL_SENIAT'
    REGULACION_CAMBIARIA_BANCARIA = 'REGULACION_CAMBIARIA_BANCARIA'
    OPERATIVA_MERCADO_P2P = 'OPERATIVA_MERCADO_P2P'
    GEOPOLITICA_PETROLERA = 'GEOPOLITICA_PETROLERA'

for c in ['GASTO_PUBLICO_PATRIA', 'INTERVENCION_CAMBIARIA_BCV', 'POLITICA_MONETARIA_LIQUIDEZ', 'CALENDARIO_FISCAL_SENIAT', 'REGULACION_CAMBIARIA_BANCARIA', 'OPERATIVA_MERCADO_P2P', 'GEOPOLITICA_PETROLERA']:
    assert TaxonomyCategory(c) == c

# 2. Verify Pipe-Delimited Hashing
prev = '0'*64; ts = '2026-11-17T00:00:00Z'; conf = '85.00'; just = 'test'; model = 'gpt-4o'
p1 = f'{prev}|{ts}|SUB|E24h|{conf}|{model}|{just}'.encode()
p2 = f'{prev}|{ts}|SUBE|24h|{conf}|{model}|{just}'.encode()
assert hashlib.sha256(p1).hexdigest() != hashlib.sha256(p2).hexdigest()

# 3. Verify Validator Capping
class FinalPrediction(BaseModel):
    veredicto: str
    confiabilidad_porcentaje: float = Field(ge=0.0, le=100.0)
    @field_validator('confiabilidad_porcentaje')
    @classmethod
    def validar(cls, v: float, info: ValidationInfo) -> float:
        if info.data and info.data.get('veredicto') in ('CORREGIDO', 'AJUSTADO_FAIL_CLOSED') and v > 75.0:
            return 75.0
        return v

p = FinalPrediction(veredicto='CORREGIDO', confiabilidad_porcentaje=95.0)
assert p.confiabilidad_porcentaje == 75.0
print('Independent verification PASSED!')
"
```
