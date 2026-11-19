## 2026-11-17T00:08:17Z
You are Explorer 3: Spec Miner & Standards Specialist.
Your working directory is: c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_3\
You MUST read ORIGINAL_REQUEST.md at: c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md before starting.

OBJECTIVE:
Investigar la estructura existente del repositorio `c:\p2p-bot-merchant`, sus estándares de especificación (`.specify/`), memoria (`.specify/memory/constitution.md`, `memory.md`), reglas en `AGENTS.md`, especificaciones existentes (`.specify/specs/`), y estructurar la propuesta de integración para el nuevo paquete de predicción de IA con respecto a los paquetes existentes (001-security, 002-binance, 003-pricing, 004-banking, 005-reporting, 006-telegram).

SCOPE BOUNDARIES:
- Read-only exploration of repository specifications, code structure, and standards.
- Write your findings to: c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_3\survey_spec_standards_report.md
- Also provide handoff.md in your working directory.

TASKS:
1. Inspeccionar `.specify/` y `.specify/specs/`:
   - ¿Cuáles son las especificaciones previas (001, 002, 003, etc.)? ¿Qué estructura de archivos tienen (`spec.md`, `plan.md`, `tasks.md`, `contracts/`)?
   - ¿Qué número de spec corresponde asignar a este nuevo sistema de predicción macroeconómica con IA (ej. `007-ai-market-predictor` o `003-ai-macro-pricing` o similar)?
   - Revisar `.specify/memory/constitution.md` y `memory.md` para verificar principios arquitectónicos (Fail-closed, TDD, sanitización de credenciales, trazabilidad total con hash SHA-256).
2. Evaluar el encaje del nuevo sistema en la arquitectura de `p2p-bot-merchant`:
   - En `AGENTS.md` se menciona que el paquete 003 (pricing algorítmico) estaba pausado. ¿Cómo esta idea de predicción macroeconómica se relaciona con el pricing o funciona como un módulo de inteligencia de mercado independiente/advisory?
   - Definir los contratos de interfaz con los módulos existentes (`src/core/`, `src/security/`, `src/integrations/` para alertas de Telegram, `src/reporting/dashboard/` para visualización en Streamlit).
3. Diseñar la estructura exacta y el índice de contenidos para los 3 artefactos requeridos por el usuario en `.specify/specs/`:
   - `spec.md`: User stories, requisitos funcionales (FR-01..FR-XX), requisitos no funcionales (NFR-01..NFR-XX), criterios de aceptación.
   - `plan.md`: Arquitectura técnica, diagramas de secuencia, componentes del pipeline, diseño de clases y módulos, estrategia Round-Robin.
   - `tasks.md`: Lista ordenada y atómica de tareas secuenciales con checkboxes `[ ]`, dependencias y fases de implementación (Phase 1: Setup & Data Models, Phase 2: Macro Context Extractor, Phase 3: Multi-Provider LLM & Round-Robin Engine, Phase 4: Predictor & Reviewer Pipeline, Phase 5: Integration & CLI/Dashboard/Telegram, Phase 6: Verification & Tests).

COMPLETION CRITERIA:
Deliver a comprehensive report in `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_3\survey_spec_standards_report.md` and write `handoff.md` in your directory. Then send a completion message to your parent orchestrator.
