## 2026-11-17T00:50:49Z
You are Worker M1_2: Contract & Schema Remediation Specialist.
Your working directory is: c:\p2p-bot-merchant\.agents\teamwork\worker_m1_2\

You MUST read ORIGINAL_REQUEST.md at: c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md before starting.
You MUST read PROJECT.md at: c:\p2p-bot-merchant\.agents\teamwork\orchestrator_1\PROJECT.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

WRITE OWNERSHIP:
You have EXCLUSIVE write ownership of the following target files:
- c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md
- c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\tasks.md
- c:\p2p-bot-merchant\docs\macro_usdt_taxonomy.md

INPUT BLUEPRINTS:
Read and follow carefully:
1. `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_1\plan_fix_strategy.md`
2. `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_2\tasks_fix_strategy.md`
3. `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_it2_3\macro_schema_fix_strategy.md`
4. `c:\p2p-bot-merchant\.agents\teamwork\challenger_m1_2\handoff.md`
5. `c:\p2p-bot-merchant\.agents\teamwork\challenger_m1_1\handoff.md`

TASKS:
1. Update `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\plan.md`:
   - Replace the legacy 7 `TaxonomyCategory` enum values with the 7 canonical categories matching System Prompt 7.1 and `macro_usdt_taxonomy.md`: `GASTO_PUBLICO_PATRIA`, `INTERVENCION_CAMBIARIA_BCV`, `POLITICA_MONETARIA_LIQUIDEZ`, `CALENDARIO_FISCAL_SENIAT`, `REGULACION_CAMBIARIA_BANCARIA`, `OPERATIVA_MERCADO_P2P`, `GEOPOLITICA_PETROLERA`.
   - Update `prediction_hash` formula in Section 10.2 to the pipe-delimited format:
     f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}"
   - Update `MacroEventItem`: add `code: str = Field(..., description='Código corto del evento (ej. GP-01, IC-01)')`, change `resumen_fáctico` to ASCII `resumen_factico: str`.
   - Update `validar_confianza_maxima_si_corregido` to inspect `info.data.get('veredicto')` and enforce `min(v, 75.0)` if `veredicto in [AuditVerdictEnum.CORREGIDO, AuditVerdictEnum.AJUSTADO_FAIL_CLOSED]`.
   - Add reference function `calc_activation()` implementing the activation floor `max(0.0, dt / L)` in Section 3.4.
2. Update `c:\p2p-bot-merchant\.specify\specs\023-ai-market-predictor\tasks.md`:
   - Harmonize contract enums across T23.1, T23.2, T23.4:
     * `PredictionDirection` (SUBE, BAJA, ESTABLE)
     * `TimeframeHorizon` ("24h-48h", "3-5 dias", "semanal")
     * `MacroContextPayload`
     * `AuditVerdictEnum` (APROBADO, CORREGIDO, RECHAZADO with AJUSTADO_FAIL_CLOSED alias)
     * `TaxonomyCategory` (the 7 canonical categories)
   - Update T23.4 to explicitly require pipe-delimited SHA-256 chaining.
3. Update `c:\p2p-bot-merchant\docs\macro_usdt_taxonomy.md`:
   - In Section 2.4.1, update activation formula to include floor: $\alpha_i(\Delta t_i) = \max(0.0, \Delta t_i / L_i)$.
4. Run verification commands:
   - `python -m ruff check .`
   - `pytest tests/unit/test_macro_challenge_m1.py`
   - Test schema instantiation to ensure zero `ValidationError`.
5. Deliverables & Handoff:
   - Write `handoff.md` in `c:\p2p-bot-merchant\.agents\teamwork\worker_m1_2\handoff.md` with the 5 required sections.
   - Send completion message to parent orchestrator.
