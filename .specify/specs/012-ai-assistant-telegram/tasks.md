# Tasks 012: Asistente de IA para Consultas Naturales en Telegram

- [x] T-012.1 Añadir configuraciones `AI_PROVIDER`, `AI_API_KEY` y `AI_MODEL_NAME` a `config/settings.py`.
- [x] T-012.2 Diseñar e implementar el conjunto de herramientas seguras de consulta (Read-Only Tools) en `src/integrations/ai_assistant.py` conectadas con `OrderRepository`, `TaxEngine` y `BCVService`.
- [x] T-012.3 Implementar el agente conversacional `TelegramAIAgent` con soporte para Gemini Function Calling y sanitización estricta.
- [x] T-012.4 Conectar `TelegramCommandPoller` en `src/integrations/telegram_notifier.py` para enrutar consultas de texto libre hacia `TelegramAIAgent`.
- [x] T-012.5 Escribir tests unitarios con mocks para el flujo conversacional y llamadas a herramientas (`tests/unit/test_ai_assistant.py`).
- [x] T-012.6 Verificar tipado estático (`mypy`), reglas de linter (`ruff`) y certificar suite completa de pruebas.
- [x] T-012.7 Actualizar `memory.md` con el estado de la especificación 012.
- [x] T-012.8 Implementar pool dinámico de claves API (`AIKeyPool`) con rotación silenciosa y cooldown ante errores HTTP 429/403 en `src/integrations/ai_assistant.py`.
- [x] T-012.9 Añadir soporte en `config/settings.py` para múltiples claves separadas por coma (`AI_API_KEYS`).
- [x] T-012.10 Escribir pruebas unitarias de failover y rotación transparente de claves en `tests/unit/test_ai_assistant.py`.
