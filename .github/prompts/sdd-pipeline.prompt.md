# SDD Pipeline Master Prompt

## Propósito
Este prompt orquesta el ciclo de vida de desarrollo guiado por especificaciones (Spec-Driven Development - SDD) para el proyecto `p2p-bot-merchant`.

## Jerarquía de Contratos
1. **Constitución (`.specify/memory/constitution.md`)**: Reglas no negociables (Fail-closed, Cero secretos, API weight, Seguridad primero).
2. **Especificación (`spec.md`)**: Define el QUÉ (requisitos funcionales RF y no funcionales RNF).
3. **Plan de Arquitectura (`plan.md`)**: Define el CÓMO (stack técnico, componentes, decisiones ADR).
4. **Tareas Atómicas (`tasks.md`)**: Define los PASOS (checklist ejecutable bajo TDD).

## Flujo de Trabajo
1. Seleccionar el paquete activo en `memory.md`.
2. Validar que la tarea a ejecutar en `tasks.md` no viole la Constitución.
3. Escribir prueba unitaria en rojo (TDD).
4. Implementar la funcionalidad mínima para pasar la prueba en verde.
5. Ejecutar linter y comprobación de tipos (`ruff check .`, `mypy src/`).
6. Marcar la tarea como completada en `tasks.md` y actualizar `memory.md`.
