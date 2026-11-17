## 2026-11-17T00:15:50Z
You are Explorer M1_2: Spec & Architecture Designer.
Your working directory is: c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_2\
You MUST read ORIGINAL_REQUEST.md at: c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md before starting.
You MUST read PROJECT.md at: c:\p2p-bot-merchant\.agents\teamwork\orchestrator_1\PROJECT.md.

OBJECTIVE:
Synthesize the technical findings from `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_2\survey_ai_architecture_report.md` and `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_3\survey_spec_standards_report.md` to define the exact content blueprint and fix strategy for the Worker to create:
- `.specify/specs/023-ai-market-predictor/spec.md`
- `.specify/specs/023-ai-market-predictor/plan.md`

TASKS:
1. Define the exact structure of `spec.md` conforming to SDD standards: User Stories, Functional Requirements (RF-01 to RF-10), Non-Functional Requirements (RNF-01 to RNF-05), Acceptance Criteria, and Edge Cases.
2. Define the exact structure of `plan.md`: System Architecture, Component Breakdown (MacroNewsCollector, RoundRobinEngine, MultiProviderPool, USDTPredictor, PredictionAuditor), Class Diagrams, Sequence Flows, Model Comparison Table, System Prompts for the 3 roles, Pydantic v2 schemas, Circuit Breaker logic, and Constitutional Alignment (Fail-Closed, Zero Secrets, SHA-256 hash chaining).
3. Provide step-by-step instructions for the Worker on how to author both files.

OUTPUT:
Deliver your report in `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_2\spec_plan_strategy.md` and write `handoff.md` in your directory. Then send a completion message to the parent orchestrator.
