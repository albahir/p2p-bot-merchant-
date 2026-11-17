# Handoff Report: Explorer M1_IT2_3 — Macro Activation & Schema Strategist

**Target Artifacts:** `docs/macro_usdt_taxonomy.md` and `.specify/specs/023-ai-market-predictor/plan.md`  
**Author:** Explorer M1_IT2_3 (Macro Activation & Schema Strategist)  
**Date:** 2026-11-17T00:52:00Z  
**Type:** Hard Handoff  

---

## 1. Observation

Direct empirical observations, file paths, line numbers, and test command results:

### 1.1 Activation Function Sign Inversion
- **File:** `c:\p2p-bot-merchant\docs\macro_usdt_taxonomy.md`
- **Lines 88-91:**
  ```latex
  $$\alpha_i(\Delta t_i) = \begin{cases}
  \frac{\Delta t_i}{L_i} & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
  1.0 & \text{si } \Delta t_i \ge L_i
  \end{cases}$$
  ```
- **Line 101:** $F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$
- **Observation:** If an event is scheduled or announced prior to occurrence ($t < t_i$), $\Delta t_i = t - t_i < 0$. Because $L_i > 0$, $\Delta t_i < L_i$ is satisfied, resulting in $\alpha_i < 0$. Multiplying by $d_i = +1.0$ (bullish shock) yields $F_i(t) < 0$ (bearish shock), inverting the direction of the vector prior to occurrence.
- **Empirical test:** `tests/unit/test_macro_challenge_m1.py::TestMacroModelEmpiricalValidation::test_vulnerability_negative_delta_t` PASSED, demonstrating that naive $\alpha_i(-4.0 / 8.0) = -0.5$ inverts sign from $+0.45$ to $-0.45$, whereas defensive `max(0.0, dt / L)` clamps $\alpha_i = 0.0$ and effective force to $0.0$.

### 1.2 Schema Divergence in `plan.md`
- **File:** `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`
- **Lines 344-357 (`MacroEventItem`):**
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
- **Observations:**
  1. `code: str` is completely missing from `MacroEventItem`. Without `code`, the downstream vector calculation engine cannot look up canonical quantitative parameters ($w_i, d_i, L_i, h_i$) in `taxonomy.py`.
  2. `categoria` uses `TaxonomyCategory` (divergent from `MacroCategoryEnum` in `docs/macro_usdt_taxonomy.md` line 423).
  3. `resumen_fáctico` uses a non-ASCII accented vowel `á`, creating encoding fragility.
  4. System Prompt for Rol 1 (Buscador) in lines 228-240 does not instruct the LLM to output taxonomy event codes.

### 1.3 Test Suite Execution Status
- **Command executed:** `pytest tests/unit/test_macro_challenge_m1.py -v`
- **Result:** 14 passed in 0.25s (Python 3.13.4, pytest-9.1.1).

---

## 2. Logic Chain

1. **Vulnerability Mechanism (Obs 1.1)**:
   - Financial news scrapers ingest scheduled announcements (e.g., BCV intervention auctions scheduled for Monday 09:00 VET or scheduled Patria bonus payouts).
   - Ingesting an event prior to its execution date produces $\Delta t_i = t - t_i < 0$.
   - A mathematical model with $\alpha_i = \Delta t_i / L_i$ without a lower floor evaluates to a negative number.
   - When multiplied by vector direction $d_i$, $(+1.0) \times (-0.5) = -0.5$. A bullish event becomes bearish before it occurs.
   - Adding a lower bound floor $\max(0.0, \Delta t_i / L_i)$ strictly guarantees that $\alpha_i \ge 0.0$ for all $\Delta t_i$, yielding $\alpha_i = 0.0$ when $\Delta t_i \le 0$ and preserving vector direction.

2. **Schema Integrity & Semantic Linkage (Obs 1.2)**:
   - In a multi-agent pipeline, Rol 1 (Buscador) extracts news facts, but Rol 2 (Analyst) requires canonical parameters ($w_i, d_i, L_i, h_i$) to compute $F_{\text{net}}$.
   - These parameters cannot be inferred reliably from free-text titles without high error rates.
   - `code: str` serves as the unambiguous foreign key linking extracted news to canonical taxonomy constants.
   - Providing concise short codes (`GP-01`, `IC-01`, etc.) alongside canonical identifiers (`EVT_BCV_INTERVENCION_REGULAR`) allows LLMs to output compact, typo-free codes in JSON schemas.
   - Harmonizing `MacroEventItem` with `code: str`, `MacroCategoryEnum`, and ASCII `resumen_factico` ensures 100% schema consistency between `docs/macro_usdt_taxonomy.md` and `plan.md`.

---

## 3. Caveats

1. **Scope of Action:** As an Explorer agent under read-only mode, no direct modifications were applied to `docs/macro_usdt_taxonomy.md` or `.specify/specs/023-ai-market-predictor/plan.md`. All remediations are provided as exact drop-in replacements in `macro_schema_fix_strategy.md`.
2. **Anticipation vs Immediate Reaction:** Clamping $\alpha_i = 0.0$ for $\Delta t_i \le 0$ treats future scheduled shocks as having zero mechanical force until they take effect. Psychological market front-running is captured once rumors or announcements produce observable P2P rate movements (`brecha_cambiaria_porcentaje`), avoiding artificial mathematical speculation.
3. **Coordinated Work:** General plan fixes (hashing formula, validator for `validar_confianza_maxima_si_corregido`) are being coordinated in parallel by `explorer_m1_it2_1`.

---

## 4. Conclusion

The remediation strategy formulated in `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_3\macro_schema_fix_strategy.md` completely resolves both findings from Challenger 1:

1. **Activation Function Floor:**
   - Updated formula in `docs/macro_usdt_taxonomy.md` Section 2.4.1 to:
     $$\alpha_i(\Delta t_i) = \begin{cases} \max\left(0.0, \frac{\Delta t_i}{L_i}\right) & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\ 1.0 & \text{si } \Delta t_i \ge L_i \end{cases}$$
   - Updated Section 3.4 in `plan.md` with explicit Python specification of `calc_activation()`.
2. **Schema Harmonization & `code: str`:**
   - Master Table 3.1 enriched with 14 short codes (`GP-01` to `GP-03`, `IC-01` to `IC-03`, `PM-01`, `CF-01` to `CF-02`, `OP-01` to `OP-02`, `GPET-01` to `GPET-02`, `RB-01`).
   - `MacroEventItem` in `plan.md` Section 8 updated to include `code: str`, `MacroCategoryEnum`, ASCII `resumen_factico`, and optional quantitative attributes for `taxonomy.py` enrichment.
   - Rol 1 Prompt (Section 7.1) updated to instruct LLM extraction of taxonomy codes.

---

## 5. Verification Method

To independently verify the mathematical robustness and schema compliance:

```powershell
# 1. Run the empirical stress test harness
pytest tests/unit/test_macro_challenge_m1.py -v

# 2. Verify code quality and styling
ruff check tests/unit/test_macro_challenge_m1.py
```

### Invalidation Conditions
- If `calc_activation(dt, latency) < 0` for any `dt < 0`, this verification is invalidated.
- If `MacroEventItem` in `plan.md` fails to require `code: str`, this verification is invalidated.
- If short code `IC-01` fails to map to canonical event `EVT_BCV_INTERVENCION_REGULAR`, this verification is invalidated.
