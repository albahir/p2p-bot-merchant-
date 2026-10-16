# Plan de Arquitectura 011: Resiliencia de Telegram y Operación Continua con Sandbox

## 1. Módulos Afectados
1. `config/settings.py`:
   - Añadir `TELEGRAM_PROXY_URL: str | None = None`
   - Añadir `TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"`
   - Añadir `USE_SANDBOX: bool = True` (por defecto en desarrollo)
2. `src/integrations/telegram_notifier.py`:
   - Enriquecer `TelegramNotifier` con:
     - Configuración de proxy y base URL en `httpx.Client`.
     - Fallback automático ante HTTP 400 (reintento con `parse_mode=None`).
     - Detección de HTTP 429 (`retry_after` parameter) y backoff.
     - Cola asíncrona de fondo `TelegramQueueDispatcher` (hilo worker daemon).
     - Hilo de escucha continua `TelegramCommandPoller` (polling con `getUpdates`).
3. `src/main.py`:
   - Soportar `use_sandbox` en `P2PBotEngine`.
   - Cuando esté en Sandbox o falten claves reales, usar `MockBinanceP2PClient` para simular actividad periódica de compra/venta y enviar resúmenes a Telegram.
   - Iniciar el poller de comandos en segundo plano para atender `/status`, `/pause`, etc.
4. `src/reporting/dashboard/components/control_actions.py`:
   - Integrar alertas de Telegram al sincronizar órdenes y al generar nuevos ciclos en Sandbox.
5. `tests/unit/test_telegram_resilience.py`:
   - Tests para fallback HTTP 400, rate limit 429 y cola de mensajes.
