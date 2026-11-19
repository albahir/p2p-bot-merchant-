# Handoff Report: Spec & Architecture Strategy (Spec 023)

**De:** Explorer M1_2 (Spec & Architecture Designer)  
**Para:** Parent Orchestrator (`fefc4a8c-cb37-4d70-9d05-32d746794690`) / Worker M1_3  
**Fecha:** 2026-11-17T00:20:00Z  
**Tipo de Handoff:** Hard (Task complete)  
**Ruta del Entregable Principal:** `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_2\spec_plan_strategy.md`  

---

## 1. Observation

A partir de la inspección directa de los archivos del repositorio y los informes de investigación técnica:
1. `c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md`:
   - Líneas 15-20: Solicita arquitectura tolerante a fallos Round-Robin y pipeline de 3 roles especializados (Buscador, Predictor, Revisor).
   - Líneas 36-39: Exige proceso secuencial ordenado de `spec.md`, `plan.md` y `tasks.md` dentro de `.specify/specs/`.
2. `c:\p2p-bot-merchant\.agents\teamwork\orchestrator_1\PROJECT.md`:
   - Líneas 3-17: Define la arquitectura de IA, el subsistema `023-ai-market-predictor`, contratos de interfaz (`MacroContextPayload`, `DraftPrediction`, `FinalUSDTPrediction`) y alineación constitucional (Fail-Closed, Cero Secretos, SHA-256).
3. `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_2\survey_ai_architecture_report.md`:
   - Líneas 69-84: Benchmark técnico de LLMs (Gemini 2.0/2.5 Flash, DeepSeek-R1, GPT-4o-mini, Claude 3.5 Sonnet, Groq Llama 3.3 70B) y costo por ciclo (~$0.00502 USD).
   - Líneas 143-207: Mecanismo de rotación Round-Robin de claves, enfriamiento ante 429 y máquina de estados del Circuit Breaker (`CLOSED`, `OPEN`, `HALF-OPEN`).
   - Líneas 256-380: System prompts de producción verbatim para Rol 1, Rol 2 y Rol 3 con regla de verificación cruzada entre familias (Cross-Family).
   - Líneas 445-584: Modelos de datos Pydantic v2 completos (`MacroEventItem`, `MacroContextCollection`, `DraftPrediction`, `AuditResult`, `AuditMetadata`, `FinalUSDTPrediction`).
4. `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_3\survey_spec_standards_report.md`:
   - Líneas 64-72: Demuestra que la numeración correcta es `023-ai-market-predictor` (preservando el paquete 003 como pausado y respetando la monotonicidad append-only tras la spec 022).
   - Líneas 212-241: Define la estructura canónica requerida para `spec.md` con RF-01 a RF-10, RNF-01 a RNF-05 y criterios de aceptación.
5. `c:\p2p-bot-merchant\.specify\scripts\validate-spec.ps1`:
   - Líneas 8-15: Script validador que requiere estrictamente la presencia de `spec.md`, `plan.md` y `tasks.md` en cada subcarpeta de `.specify\specs`.

---

## 2. Logic Chain

1. **Premisa 1 (Identificación del Paquete y Desacoplamiento):** Con base en `survey_spec_standards_report.md:64-72` y `AGENTS.md`, el Paquete 003 está pausado para trading automatizado de anuncios. Asignar el número `023-ai-market-predictor` permite crear un subsistema de inteligencia macroeconómica y advisory sin interferir con la política de pausa ni romper la trazabilidad histórica de `memory.md`.
2. **Premisa 2 (Completitud de Requisitos Funcionales):** Al sintetizar la taxonomía de 14 eventos de Explorer 1 con el pipeline de 3 roles de Explorer 2, se derivaron 10 requerimientos funcionales (`RF-01` a `RF-10`) que abarcan desde la extracción de noticias, formulación direccional ternaria, balanceo Round-Robin, auditoría adversarial, hash SHA-256, integraciones en Telegram y Dashboard Streamlit, hasta la calibración histórica.
3. **Premisa 3 (Garantía Constitucional y Calidad):** Los 5 requisitos no funcionales (`RNF-01` a `RNF-05`) y los 8 criterios de aceptación (`AC-01` a `AC-08`) establecen umbrales cuantitativos concretos (< 15s de latencia, < $0.01 por corrida, fail-closed ante veredicto RECHAZADO, validación Pydantic v2).
4. **Premisa 4 (Plan de Arquitectura Turnkey):** El blueprint en `plan.md` incorpora los diagramas de clases, diagramas de secuencia, tabla comparativa de modelos, prompts verbatim, esquemas Pydantic v2, estados de Circuit Breaker y modelos SQLAlchemy de persistencia.
5. **Conclusión Lógica:** Con el documento `spec_plan_strategy.md`, el Worker dispone de una especificación detallada, exhaustiva y sin ambigüedades técnicas para generar de manera inmediata y conforme a SDD `.specify/specs/023-ai-market-predictor/spec.md` y `.specify/specs/023-ai-market-predictor/plan.md`.

---

## 3. Caveats

- **Generación de `tasks.md`:** Este reporte se enfoca exclusivamente en la estrategia y blueprint para `spec.md` y `plan.md`. El desglose secuencial de tareas (`tasks.md`) corresponde al siguiente hito del pipeline, aunque ya se incluye el marco de referencia en las dependencias.
- **Validación automatizada temprana:** Si se ejecuta `.specify/scripts/validate-spec.ps1` inmediatamente tras crear `spec.md` y `plan.md`, el script arrojará error hasta que `tasks.md` esté también presente en la misma carpeta. Esto es el comportamiento esperado del validador de tres piezas.
- **No se realizaron cambios en código fuente:** En estricto cumplimiento del rol de Explorer (Read-Only), no se modificó ningún archivo en `src/` ni en `.specify/`.

---

## 4. Conclusion

Se ha formulado y entregado la estrategia y blueprint integral en `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_2\spec_plan_strategy.md`. El documento contiene:
1. El diseño estructural completo de `spec.md` (QUÉ, HU-01..04, RF-01..10, RNF-01..05, AC-01..08 y tabla de 8 casos extremos).
2. El diseño estructural completo de `plan.md` (Stack, módulos, 5 componentes, tabla de LLMs, diagramas de clases y secuencia, 3 system prompts verbatim, modelos Pydantic v2, Circuit Breaker con Tenacity, modelos SQLAlchemy y alineación constitucional).
3. La guía de instrucciones paso a paso para que el Worker redacte ambos archivos con precisión milimétrica.

---

## 5. Verification Method

Para verificar independientemente el entregable de este hito:
1. **Inspección del Blueprint:**
   - Visualizar `c:\p2p-bot-merchant\.agents\teamwork\explorer_m1_2\spec_plan_strategy.md` y constatar la presencia de todas las secciones requeridas.
2. **Comprobación de Cobertura de Requisitos:**
   - Verificar que estén definidos RF-01 a RF-10 con criterios de entrada/salida.
   - Verificar que estén definidos RNF-01 a RNF-05 con métricas medibles.
   - Verificar que los 3 System Prompts estén transcritos textualmente.
   - Verificar que los esquemas de código Pydantic v2 sean sintácticamente válidos.
3. **Condición de Invalidación:**
   - El reporte quedaría invalidado si omitiera los system prompts, si no incluyera los 10 requisitos funcionales, o si asignara una numeración conflictiva con la historia del repositorio.
