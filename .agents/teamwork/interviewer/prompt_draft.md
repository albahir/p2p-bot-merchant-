El usuario solicita: "un grupo de agentes para evaluar una idea que tengo es la siguiente necesito que investigues con un agente que noticias afectan el precio del usdt en venezuela pagos de sueldos intervencio bancaria anuncios de bcv entre otros , otro agente que pueda evaluar los requerimientos otro que planifique y otro que cree las task todos por orden". Evaluar la idea y diseñar la arquitectura para un sistema de IA con estrategia de tolerancia a fallos Round-Robin y pipeline de tres roles especializados (búsqueda de contexto macroeconómico, predicción y revisión de respuesta final) que consuma noticias de Venezuela y prediga dirección (subirá o bajará), lapso temporal estimado y porcentaje de confiabilidad del precio del USDT, definiendo el perfil de cada agente, requerimientos, plan y tareas ordenadas.

Working directory: c:\p2p-bot-merchant
Integrity mode: development

## Requirements

### R1. Investigación de eventos macroeconómicos y noticias que impactan el precio de USDT en Venezuela
Investigar, clasificar y documentar los factores y noticias de alto impacto en el precio del USDT en Venezuela (pagos de nómina y bonos gubernamentales, intervenciones cambiarias del BCV, anuncios oficiales, emisión de liquidez monetaria, entre otros), detallando los mecanismos de transmisión hacia el precio y las fuentes públicas recomendadas de información y noticias.

### R2. Arquitectura de IA tolerante a fallos y pipeline multi-rol (Búsqueda, Predicción y Revisión)
Diseñar la arquitectura de IA con tolerancia a fallos mediante Round-Robin (gestión multi-clave y/o multi-proveedor para evitar caídas y agotamiento de cuotas) y una cadena de tres roles especializados:
1. Rol Buscador/Recopilador: extrae y estructura las noticias y eventos macroeconómicos relevantes.
2. Rol Analista/Predictor: perfil económico especializado que consume el contexto estructurado y genera la predicción direccional (sube/baja), el lapso temporal estimado y el porcentaje de confiabilidad.
3. Rol Revisor/Auditor: valida y verifica la fundamentación y coherencia de la respuesta final antes de su emisión.
Evaluar modelos viables (API de Google Gemini y alternativas) para cada rol según costos, latencia y precisión analítica.

### R3. Proceso secuencial de especificación, arquitectura y tareas
Estructurar el entregable siguiendo el flujo ordenado solicitado por el usuario: evaluación de requerimientos (`spec.md`), diseño y planificación de arquitectura (`plan.md`) y desglose secuencial de tareas (`tasks.md`) dentro de `.specify/specs/` en el repositorio existente.

## Acceptance Criteria

### Investigación y Taxonomía Económica
- [ ] Documento con la taxonomía y análisis detallado de noticias y eventos macroeconómicos en Venezuela que afectan el precio del USDT, junto con sus fuentes públicas recomendadas.

### Arquitectura de IA, Round-Robin y Pipeline Multi-Rol
- [ ] Comparativa técnica y económica entre la API de Gemini y modelos alternativos para cada uno de los roles del pipeline.
- [ ] Especificación de la estrategia de Round-Robin para rotación de claves y proveedores que garantice alta disponibilidad y mitigación de caídas o rate-limits.
- [ ] Especificación del perfil, system prompts y esquema de comunicación de los 3 roles: Buscador de noticias, Analista predictor y Revisor final.
- [ ] Esquema formal de salida de la predicción con: dirección proyectada (sube/baja), lapso o ventana temporal del comportamiento estimado, porcentaje de confiabilidad y justificación fundamentada en los eventos recopilados.

### Especificación y Secuencia de Tareas
- [ ] Especificación de requerimientos funcionales y técnicos (`spec.md`) evaluados en `.specify/specs/`.
- [ ] Plan de diseño y arquitectura (`plan.md`).
- [ ] Desglose secuencial de tareas (`tasks.md`) ordenadas y listas para su implementación.
