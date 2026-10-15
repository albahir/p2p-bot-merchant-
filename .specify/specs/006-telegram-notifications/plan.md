# Plan 006: Notificaciones Telegram

## Stack
- `python-telegram-bot` v22+ (asíncrono)
- `redis` / cola local para encolar alertas sin bloquear el ciclo de órdenes

## Arquitectura
- `src/integrations/telegram_notifier.py`: cliente asíncrono de envío de alertas y recepción de comandos.
- `src/core/event_bus.py`: cola de eventos desacoplada para alertas del sistema.

## Decisiones
- **Por qué cola asíncrona / Redis**: si la API de Telegram sufre retrasos o caída, las operaciones de Binance no se bloquean.
- **Fail-closed en comandos**: solo usuarios autorizados en `TELEGRAM_ALLOWED_USER_IDS` pueden interactuar.

## Dependencias
- Paquete 001 (token de Telegram cifrado y recuperado con `api_key_manager`).
