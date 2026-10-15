---
name: logging-dashboard
description: Prácticas de observabilidad, sanitización de logs y visualización de métricas en Streamlit.
---

# Logging & Dashboard Skill

Instrucciones para agentes sobre registro seguro y visualización.

## Reglas Clave
1. Enmascarar automáticamente cualquier secreto o clave en los formatters de logging (`config/logging.yaml`).
2. Consultas del dashboard hacia la base de datos deben ser estrictamente en modo solo lectura (`read_only`).
3. Métricas de API weight y latencia deben registrarse con timestamps UTC consistentes.
