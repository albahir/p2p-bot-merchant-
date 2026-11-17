# Remediation Strategy: Macro Activation Function Floor & Schema Harmonization

**Target Artifacts:** `docs/macro_usdt_taxonomy.md` and `.specify/specs/023-ai-market-predictor/plan.md`  
**Author:** Explorer M1_IT2_3 (Macro Activation & Schema Strategist)  
**Date:** 2026-11-17T00:50:00Z  
**Context:** Milestone 1 Gate Iteration 2 (Remediation based on Challenger M1_1 report)  
**Status:** READY FOR WORKER IMPLEMENTATION  

---

## 1. Executive Summary

Challenger M1_1's empirical stress test (`tests/unit/test_macro_challenge_m1.py`) verified that the mathematical framework of 14 Venezuelan macroeconomic shocks is structurally sound, decaying predictably and bounding conflicting shocks under 45% (well below the 65% ceiling). However, two critical vulnerabilities and discrepancies were identified:

1. **Sign-Inversion Vulnerability with Negative $\Delta t$ ($\Delta t_i < 0$):** In `docs/macro_usdt_taxonomy.md` Section 2.4.1, the linear ramp-up function $\alpha_i(\Delta t_i) = \Delta t_i / L_i$ lacked a defensive zero floor. When an event is scheduled or announced ahead of its effective occurrence date ($t < t_i \implies \Delta t_i < 0$), $\alpha_i$ evaluates to a negative number, multiplying into the force vector $F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i \cdot D_i$ and inverting its sign (e.g., an anticipated bullish bonus payment turns bearish).
2. **Schema Divergence and Missing `code: str` in `plan.md`:** `plan.md` Section 8 defined `MacroEventItem` without the `code: str` attribute, preventing downstream quantitative lookup of canonical constants ($w_i, d_i, L_i, h_i$), while simultaneously diverging from the canonical category enums in `docs/macro_usdt_taxonomy.md`.

This document provides the exact, production-ready remediation strategy, complete LaTeX formulas, code diffs, mapping tables, and verification methods for the worker agent.

---

## 2. Problem Analysis & Root Cause

### 2.1 Issue 1: Activation Sign-Inversion Vulnerability ($\Delta t_i < 0$)

#### Theoretical Context
In economic news ingestion (BCV official press releases, Gaceta Oficial, Sistema Patria announcements), events are frequently captured prior to execution:
- *"BCV convoca a las mesas cambiarias para subasta de $90M el lunes a las 09:00 VET"* (captured Friday, $t < t_i$, $\Delta t_i = -40\text{ h}$).
- *"Patria programó la asignación del Bono Contra la Guerra Económica para mañana"* ($\Delta t_i = -16\text{ h}$).
- *"Vencimiento de anticipos de IVA del SENIAT fijado para el 22 del mes"* ($\Delta t_i < 0$).

#### Mathematical Flaw in `docs/macro_usdt_taxonomy.md` (Lines 88-91)
The existing piecewise function in Section 2.4.1 is:
$$\alpha_i(\Delta t_i) = \begin{cases}
\frac{\Delta t_i}{L_i} & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

Because $L_i > 0$, any negative $\Delta t_i$ satisfies $\Delta t_i < L_i$. Thus, $\alpha_i(-4.0\text{ h}) = -4.0 / 1.0 = -4.0$.  
Plugging this into the force equation:
$$F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$
For a bullish event ($d_i = +1.0, w_i = 0.90$):
$$F_i(t) = (+1.0) \times 0.90 \times 1.00 \times (-4.0) \times 1.00 = -3.60 \quad (\text{BEARISH!})$$
The anticipation of a massive liquidity injection calculates as downward pressure on the exchange rate, directly corrupting the directional prediction.

---

### 2.2 Issue 2: Schema Divergence & Missing `code: str` in `plan.md`

#### Analysis of Discrepancies
| Dimension | `docs/macro_usdt_taxonomy.md` (Canonical) | `plan.md` Section 8 (Divergent) | Impact |
| :--- | :--- | :--- | :--- |
| **Event Code** | `code: str` (e.g. `EVT_BCV_INTERVENCION_REGULAR`) | **MISSING** | Engine cannot look up $w_i, d_i, L_i, h_i$ in `taxonomy.py` |
| **Category Enum** | `MacroCategoryEnum` (7 canonical categories) | `TaxonomyCategory` (7 different names) | `ValidationError` on cross-module payload transfer |
| **Field Naming** | `resumen_factico` (ASCII) | `resumen_fáctico` (non-ASCII with accent) | Encoding errors, attribute access mismatches |
| **Short Codes** | Table 3.1 lists canonical codes only | No short codes specified | LLMs generate long strings prone to typos; higher token costs |

Without `code: str`, LLM Rol 1 (Buscador) outputs an unstructured list of news items without a semantic foreign key. The mathematical vector engine in Rol 2 (Analyst) is left unable to determine whether an intervention was regular ($d=-1, w=0.70$) or deficit-driven ($d=+1, w=0.85$), which would flip the market direction.

---

## 3. Remediation Strategy for `docs/macro_usdt_taxonomy.md`

### 3.1 Activation Function Fix (Section 2.4.1)

#### Exact Markdown & LaTeX Replacement

**Location:** `c:\p2p-bot-merchant\docs\macro_usdt_taxonomy.md`, lines 84-93.

**Target Content to Replace:**
```markdown
#### 2.4.1 Función de Activación de Propagación ($\alpha_i$)

La transmisión de una inyección de liquidez o de una intervención cambiaria no es instantánea. Requiere un tiempo de procesamiento interbancario y de difusión cognitiva:

$$\alpha_i(\Delta t_i) = \begin{cases}
\frac{\Delta t_i}{L_i} & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$
```

**Replacement Content:**
```markdown
#### 2.4.1 Función de Activación de Propagación ($\alpha_i$) con Cota Inferior Defensiva

La transmisión de una inyección de liquidez o de una intervención cambiaria no es instantánea. Requiere un tiempo de procesamiento interbancario y de difusión cognitiva. Para evitar anomalías matemáticas causadas por noticias de eventos programados en el futuro ($\Delta t_i < 0$), la función incorpora una cota inferior defensiva estricta ($\max(0.0, \Delta t_i / L_i)$) que impide la inversión espuria del sentido del vector de fuerza:

$$\alpha_i(\Delta t_i) = \begin{cases}
\max\left(0.0, \frac{\Delta t_i}{L_i}\right) & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
0.0 & \text{si } \Delta t_i \le 0 \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

O de forma analítica compacta:
$$\alpha_i(\Delta t_i) = \begin{cases}
\max\left(0.0, \frac{\Delta t_i}{L_i}\right) & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

* **Comportamiento ante eventos futuros ($\Delta t_i < 0$):** Si un evento está pautado para ejecutarse en el futuro ($t < t_i$), $\alpha_i(\Delta t_i) = 0.0$. La fuerza efectiva inicial es cero, garantizando que un shock alcista nunca se registre como bajista antes de ocurrir.
* **Comportamiento en ventana de rezago ($0 < \Delta t_i < L_i$):** El impacto escala linealmente de $0.0$ a $1.0$ a medida que los fondos circulan interbancariamente.
* **Comportamiento en maduración ($L_i \le \Delta t_i$):** El impacto alcanza el $100\%$ de su fuerza base ($1.0$) y posteriormente queda sujeto exclusivamente a la función de decaimiento temporal $D_i(\Delta t_i)$.
```

---

### 3.2 Canonical Short Code Mapping (Section 3.1)

To support concise, zero-typo token generation by LLMs while maintaining strict mathematical consistency, enrich Table 3.1 by adding the standard alphanumeric code column (`Código Corto`):

| Código Corto | Código Canónico | Nombre del Evento | Categoría | Dir. ($d_i$) | Peso ($w_i$) | Latencia ($L_i$) | Semivida ($h_i$) |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **GP-01** | `EVT_PATRIA_GUERRA_ACTIVOS` | Bono Guerra Económica: Activos y Cestaticket | `GASTO_PUBLICO_PATRIA` | **+1 (SUBE)** | 0.90 | 1.0 h | 36.0 h |
| **GP-02** | `EVT_PATRIA_GUERRA_JUBILADOS` | Bono Guerra Económica: Jubilados y Pensionados | `GASTO_PUBLICO_PATRIA` | **+1 (SUBE)** | 0.65 | 2.0 h | 24.0 h |
| **GP-03** | `EVT_PATRIA_AGUINALDOS_FRAC` | Desembolso de Fracción de Aguinaldos Públicos | `GASTO_PUBLICO_PATRIA` | **+1 (SUBE)** | 1.00 | 1.5 h | 72.0 h |
| **IC-01** | `EVT_BCV_INTERVENCION_REGULAR` | Intervención Cambiaria Semanal Ordinaria ($50M-$90M) | `INTERVENCION_CAMBIARIA_BCV` | **-1 (BAJA)** | 0.70 | 2.0 h | 36.0 h |
| **IC-02** | `EVT_BCV_INTERVENCION_AGRESIVA` | Intervención Extraordinaria / Shock (> $120M) | `INTERVENCION_CAMBIARIA_BCV` | **-1 (BAJA)** | 0.95 | 1.0 h | 48.0 h |
| **IC-03** | `EVT_BCV_INTERVENCION_DEFICIT` | Intervención Restringida / Insuficiente (< $40M) | `INTERVENCION_CAMBIARIA_BCV` | **+1 (SUBE)** | 0.85 | 3.0 h | 40.0 h |
| **PM-01** | `EVT_BCV_LIQUIDEZ_M2_SPIKE` | Expansión Semanal Acelerada de M2 (> 3.5%) | `POLITICA_MONETARIA_LIQUIDEZ` | **+1 (SUBE)** | 0.60 | 12.0 h | 96.0 h |
| **CF-01** | `EVT_SENIAT_PAGO_QUINCENA` | Vencimiento Anticipos IVA/ISLR Especiales | `CALENDARIO_FISCAL_SENIAT` | **-1 (BAJA)** | 0.65 | 0.5 h | 24.0 h |
| **CF-02** | `EVT_SENIAT_ZAFRA_ISLR_MAR` | Cierre de Zafra Anual ISLR (Marzo) | `CALENDARIO_FISCAL_SENIAT` | **-1 (BAJA)** | 0.85 | 24.0 h | 120.0 h |
| **OP-01** | `EVT_SUDEBAN_LUNES_BANCARIO` | Feriado Bancario Nacional / Lunes Bancario | `OPERATIVA_MERCADO_P2P` | **0 (NEUTRAL)** | 0.50 | 0.0 h | 18.0 h |
| **OP-02** | `EVT_CAIDA_PAGO_MOVIL_NAC` | Incidencia Crítica en Plataforma Interbancaria | `OPERATIVA_MERCADO_P2P` | **0 (NEUTRAL)** | 0.55 | 0.1 h | 6.0 h |
| **GPET-01** | `EVT_OFAC_LICENCIA_RENOVADA` | Renovación / Ampliación Licencia Petrolera OFAC | `GEOPOLITICA_PETROLERA` | **-1 (BAJA)** | 0.90 | 2.0 h | 168.0 h |
| **GPET-02** | `EVT_OFAC_LICENCIA_REVOCADA` | Revocación o Vencimiento de Licencia Petrolera | `GEOPOLITICA_PETROLERA` | **+1 (SUBE)** | 1.00 | 1.0 h | 240.0 h |
| **RB-01** | `EVT_REGULACION_FISCALIZACION` | Operativos SUNDDE/SENIAT sobre Tasa Oficial | `REGULACION_CAMBIARIA_BANCARIA` | **+1 (SUBE)** | 0.70 | 4.0 h | 48.0 h |

---

### 3.3 Schema Update in `docs/macro_usdt_taxonomy.md` Section 7

Update docstring of `code` in `MacroEventItem` (line 456):
```python
code: str = Field(
    ...,
    description=(
        "Código taxonómico del evento. Admite código canónico "
        "(ej. 'EVT_BCV_INTERVENCION_REGULAR') o alias corto normalizado (ej. 'IC-01', 'GP-01')"
    ),
)
```

---

## 4. Remediation Strategy for `plan.md`

### 4.1 Section 3.4 Expansion: `USDTPredictor` Vectorial Engine Specification

**Location:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`, line 88-90.

**Target Content to Replace:**
```markdown
### 3.4 `USDTPredictor` (`MacroAnalystPredictor`)
* **Misión:** Ejecutar el Rol 2. Procesa el `MacroContextPayload` estructurado, calcula la resultante de fuerzas vectoriales $F_{\text{net}}(t) = \sum F_i(t)$ considerando pesos y rezagos, y emite el borrador `DraftPrediction`.
```

**Replacement Content:**
```markdown
### 3.4 `USDTPredictor` (`MacroAnalystPredictor`)
* **Misión:** Ejecutar el Rol 2. Procesa el `MacroContextPayload` estructurado, computa la resultante macroeconómica de fuerzas vectoriales $F_{\text{net}}(t) = \sum F_i(t)$ y emite el borrador calibrado `DraftPrediction`.
* **Motor Matemático Vectorial y Activación con Floor Defensivo:**
  La fuerza efectiva instantánea de cada evento $i$ se calcula como:
  $$F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$
  Donde:
  - $\alpha_i(\Delta t_i) = \max(0.0, \Delta t_i / L_i)$ para $\Delta t_i < L_i$ con $L_i > 0$, garantizando cota cero para eventos futuros ($\Delta t_i \le 0$) para erradicar cualquier inversión de signo.
  - $D_i(\Delta t_i) = \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$ modela el enfriamiento exponencial posterior a la absorción.
  - El software implementa la función determinista `calc_activation(dt: float, latency: float) -> float`:
    ```python
    def calc_activation(dt: float, latency: float) -> float:
        if latency > 0.0 and dt < latency:
            return max(0.0, dt / latency)
        if dt < 0.0:
            return 0.0
        return 1.0
    ```
```

---

### 4.2 Section 7.1 Update: Prompt Rol 1 (Buscador) with Code Generation

**Location:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`, lines 228-236.

Update Rule 1 of Prompt 7.1 to explicitly mandate extracting both `code` and `categoria`:
```markdown
1. TAXONOMÍA PERMITIDA Y CÓDIGOS DE EVENTO: Debes clasificar cada evento asignando estrictamente su código taxonómico (código canónico o alias corto) y su categoría canónica:
   - GASTO_PUBLICO_PATRIA: GP-01 (EVT_PATRIA_GUERRA_ACTIVOS), GP-02 (EVT_PATRIA_GUERRA_JUBILADOS), GP-03 (EVT_PATRIA_AGUINALDOS_FRAC)
   - INTERVENCION_CAMBIARIA_BCV: IC-01 (EVT_BCV_INTERVENCION_REGULAR), IC-02 (EVT_BCV_INTERVENCION_AGRESIVA), IC-03 (EVT_BCV_INTERVENCION_DEFICIT)
   - POLITICA_MONETARIA_LIQUIDEZ: PM-01 (EVT_BCV_LIQUIDEZ_M2_SPIKE)
   - CALENDARIO_FISCAL_SENIAT: CF-01 (EVT_SENIAT_PAGO_QUINCENA), CF-02 (EVT_SENIAT_ZAFRA_ISLR_MAR)
   - REGULACION_CAMBIARIA_BANCARIA: RB-01 (EVT_REGULACION_FISCALIZACION)
   - OPERATIVA_MERCADO_P2P: OP-01 (EVT_SUDEBAN_LUNES_BANCARIO), OP-02 (EVT_CAIDA_PAGO_MOVIL_NAC)
   - GEOPOLITICA_PETROLERA: GPET-01 (EVT_OFAC_LICENCIA_RENOVADA), GPET-02 (EVT_OFAC_LICENCIA_REVOCADA)
```

---

### 4.3 Section 8 Schema Harmonization: `MacroEventItem` in `plan.md`

**Location:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`, lines 344-357.

**Target Content to Replace:**
```python
class MacroEventItem(BaseModel):
    """Evento macroeconómico individual normalizado por el Buscador."""
    event_id: str = Field(..., description="Identificador único del evento")
    categoria: TaxonomyCategory
    titulo: str = Field(..., min_length=5, max_length=150)
    resumen_fáctico: str = Field(..., min_length=10, max_length=500)
    fuente_nombre: str
    fuente_url: Optional[str] = None
    credibilidad: SourceCredibility
    cifras_especificadas: bool = False
    monto_relevante: Optional[float] = None
    unidad_monto: Optional[str] = None
    timestamp_evento_utc: datetime
```

**Replacement Content:**
```python
class MacroEventItem(BaseModel):
    """Evento macroeconómico individual normalizado por el Buscador y enriquecido por la taxonomía."""
    event_id: str = Field(..., description="Identificador único, ej. EVT-202611-BCV-INT-001")
    code: str = Field(..., description="Código canónico (ej. 'EVT_BCV_INTERVENCION_REGULAR') o alias corto (ej. 'IC-01', 'GP-01')")
    categoria: MacroCategoryEnum = Field(..., description="Categoría de taxonomía canónica")
    titulo: str = Field(..., min_length=5, max_length=150)
    resumen_factico: str = Field(..., min_length=10, max_length=500, description="Resumen objetivo del hecho")
    fuente_nombre: str
    fuente_url: Optional[str] = None
    credibilidad: SourceCredibility
    cifras_especificadas: bool = False
    monto_relevante: Optional[float] = None
    unidad_monto: Optional[str] = None
    timestamp_evento_utc: datetime
    # Parámetros cuantitativos resueltos automáticamente desde taxonomy.py:
    base_weight: Optional[float] = Field(None, ge=0.10, le=1.00, description="Peso intrínseco w_i")
    vector_direction: Optional[int] = Field(None, description="Dirección d_i: +1 (SUBE), -1 (BAJA), 0 (ESTABLE)")
    latency_hours: Optional[float] = Field(None, ge=0.0, description="Latencia inicial L_i en horas")
    half_life_hours: Optional[float] = Field(None, gt=0.0, description="Semivida de decaimiento h_i en horas")
```

#### Why this structure is optimal:
1. **Contains `code: str`:** Satisfies the mandatory requirement and enables instantaneous quantitative lookup.
2. **Uses `MacroCategoryEnum`:** Resolves enum naming collisions across the codebase.
3. **Uses ASCII `resumen_factico`:** Prevents unicode encoding runtime crashes.
4. **Has Optional Quantitative Attributes:** Rol 1 (LLM) only needs to output factual news data + `code`; `MacroNormalizer` fills in $w_i, d_i, L_i, h_i$ upon repository lookup without needing disjoint classes.

---

## 5. Verification Method & Test Automation

The remediation is verified by executing the existing empirical challenge suite and adding explicit alias lookup tests.

### 5.1 Command Execution
```powershell
# Execute the full macro challenge suite
pytest tests/unit/test_macro_challenge_m1.py -v

# Style and syntax check
ruff check tests/unit/test_macro_challenge_m1.py
```

### 5.2 Deterministic Assertion in `test_macro_challenge_m1.py`
The vulnerability and its fix are verified in `test_vulnerability_negative_delta_t`:
```python
def test_vulnerability_negative_delta_t(self):
    dt_future = -4.0  # Scheduled in 4 hours
    latency = 8.0

    # Defensive activation with floor:
    safe_alpha = calc_activation(dt_future, latency)
    assert safe_alpha == 0.0, "Defensive activation must be 0.0 for future event"

    # Bullish force cannot turn negative:
    effective_force = (+1.0) * 0.90 * safe_alpha
    assert effective_force == 0.0, "Force must be 0.0 prior to execution"
```

### 5.3 Invalidation Criteria
- If `safe_alpha < 0` for any $\Delta t_i < 0$, verification FAILS.
- If `MacroEventItem` can be instantiated without `code`, verification FAILS.
- If `code="GP-01"` fails to resolve to `w=0.90, d=+1.0, L=1.0, h=36.0`, verification FAILS.
