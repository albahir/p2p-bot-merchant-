## 2026-11-17T00:08:08Z
You are Explorer 2: AI Architecture & Pipeline Specialist.
Your working directory is: c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_2\
You MUST read ORIGINAL_REQUEST.md at: c:\p2p-bot-merchant\.agents\teamwork\ORIGINAL_REQUEST.md before starting.

OBJECTIVE:
Investigar y diseñar la arquitectura técnica del sistema de IA con tolerancia a fallos Round-Robin y el pipeline de 3 roles especializados (Buscador, Predictor, Revisor) para la predicción del USDT en Venezuela.

SCOPE BOUNDARIES:
- Read-only research, architecture modeling and analysis. Do not modify production code.
- Write your findings to: c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_2\survey_ai_architecture_report.md
- Also provide handoff.md in your working directory.

TASKS:
1. Comparativa técnica y económica de modelos para cada rol:
   - Google Gemini API (Gemini 2.5 Flash, Gemini 1.5 Pro, Flash-Lite) vs alternativas (OpenAI GPT-4o-mini / GPT-4o, Groq Llama 3.3 70B, DeepSeek V3 / R1, Anthropic Claude 3.5 Sonnet / Haiku).
   - Evaluar para cada uno de los 3 roles:
     * Rol 1: Buscador/Recopilador (necesita context window amplio, extracción JSON rápida, bajo coste, alta velocidad de procesamiento de textos largos o web search).
     * Rol 2: Analista/Predictor (necesita razonamiento económico profundo, capacidad de síntesis, cálculo de confianza calibrado, rigor analítico).
     * Rol 3: Revisor/Auditor (necesita pensamiento crítico, detección de sesgos, verificación de coherencia entre premisas y conclusión, validación de alucinaciones).
   - Análisis de costos por millón de tokens (input/output) y latencia estimada por rol.
2. Estrategia de Tolerancia a Fallos Round-Robin y Fallback:
   - Gestión multi-clave (rotación de múltiples API keys del mismo proveedor para distribuir límites de cuota/RPM/TPM).
   - Gestión multi-proveedor (failover en cascada o Round-Robin ponderado entre Google Gemini, Groq, DeepSeek, OpenAI).
   - Algoritmo de rotación (Round-Robin con estado de salud / Circuit Breaker): detección de errores 429 (rate limit), 5xx (server error), timeout, degradación de latencia.
   - Políticas de reintento con backoff exponencial y jitter (usando p.ej. Tenacity).
3. Especificación detallada de los 3 roles:
   - Perfil de cada agente (rol, objetivo, temperatura, top_p, restricciones).
   - System prompts completos y estructurados para:
     * Buscador / Recopilador de contexto macroeconómico.
     * Analista / Predictor macroeconómico de USDT.
     * Revisor / Auditor de coherencia y veracidad.
   - Flujo de interacción y esquema de paso de mensajes entre roles.
4. Esquema Formal de Datos y Salida:
   - JSON Schema estricto (Pydantic model) para la salida final de la predicción:
     * `direccion`: enum ["SUBE", "BAJA", "ESTABLE"]
     * `lapso_estimado`: ventana temporal (ej. "24h-48h", "3-5 dias", "semanal")
     * `confiabilidad_porcentaje`: float entre 0.0 y 100.0 (calibrado)
     * `factores_clave`: lista de factores que sustentan la predicción
     * `justificacion_detallada`: texto explicativo con lógica de transmisión económica
     * `riesgos_invalidacion`: factores que podrían revertir la predicción
     * `metadata_auditoria`: timestamps, modelos usados, resultado de revisión

COMPLETION CRITERIA:
Deliver a comprehensive architecture report in `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_2\survey_ai_architecture_report.md` and write `handoff.md` in your directory. Then send a completion message to your parent orchestrator.
