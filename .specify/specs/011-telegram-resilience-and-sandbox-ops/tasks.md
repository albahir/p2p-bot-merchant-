# Tasks 011: Resiliencia de Telegram y Operación Continua con Sandbox

- [x] T-011.1 Actualizar `config/settings.py` con `TELEGRAM_PROXY_URL`, `TELEGRAM_API_BASE_URL` y `USE_SANDBOX`.
- [x] T-011.2 Escribir tests unitarios en rojo para resiliencia de Telegram (`tests/unit/test_telegram_resilience.py`).
- [x] T-011.3 Implementar en `src/integrations/telegram_notifier.py`: fallback a texto plano ante HTTP 400, manejo de 429 con `retry_after`, proxy y cola en segundo plano (`TelegramQueueDispatcher`).
- [x] T-011.4 Implementar hilo poller de comandos Telegram (`TelegramCommandPoller`) en `src/integrations/telegram_notifier.py` para responder `/status`, `/pause`, `/resume`, `/report`, `/ayuda`.
- [x] T-011.5 Actualizar `src/main.py` para operar en bucle normal con Sandbox activo (`MockBinanceP2PClient`), escuchando comandos e interactuando con Telegram.
- [x] T-011.6 Actualizar `src/reporting/dashboard/components/control_actions.py` para emitir notificaciones a Telegram ante sincronizaciones y nuevos ciclos comerciales.
- [x] T-011.7 Verificar suite de pruebas completa, tipado `mypy` y `ruff check`, y actualizar `memory.md`.
