# Especificación 011: Resiliencia de Telegram, Prevención de Caídas y Operaciones Normales con Sandbox

## 1. Contexto y Diagnóstico
Durante la operación del bot, el usuario experimenta caídas intermitentes en el envío de mensajes a Telegram ("a veces no se envía") y el bot solo envía mensajes reactivamente al presionar el botón de prueba en la UI.
El diagnóstico de red profundo reveló:
1. **Bloqueo a nivel de ISP/CANTV/Operadoras**: ICMP ping a `api.telegram.org` (149.154.166.110) responde con 151 ms, pero conexiones TCP en puertos 443 y 8443 son filtradas/descartadas (TCP SYN timeout). Cloudflare (1.1.1.1:443) responde con éxito.
2. **Rechazo por formato Markdown (HTTP 400)**: Mensajes con caracteres especiales (`_`, `*`, `[`, etc.) son descartados de inmediato sin fallback a texto plano.
3. **Falta de Cola Asíncrona**: Las llamadas HTTP bloquean la UI y si hay latencia o timeouts, la app se congela.
4. **Falta de Polling de Comandos**: El bot no tiene un bucle activo de `getUpdates`, impidiendo que el usuario use comandos interactivos (`/status`, `/pause`, etc.) desde su app móvil.
5. **Inactividad del Engine en Modo Desarrollo**: El bucle continuo `P2PBotEngine` queda inerte si no hay credenciales reales de Binance en la DB, en vez de aprovechar el `MockBinanceP2PClient` (Sandbox) para simular ciclos comerciales y emitir alertas reales periódicas.

## 2. Requisitos Funcionales
- **RF-011.1 (Proxy y Endpoint Configurable)**: Soporte para `TELEGRAM_PROXY_URL` (HTTP/SOCKS5) y `TELEGRAM_API_BASE_URL` (para reverse proxy como Cloudflare Worker o VPS) en `Settings` y `TelegramNotifier`.
- **RF-011.2 (Fallback de Formato a Texto Plano)**: Si un envío falla con HTTP 400 por sintaxis Markdown, reintentar automáticamente como texto plano sin formato.
- **RF-011.3 (Manejo de Rate Limit HTTP 429)**: Respetar `retry_after` y aplicar backoff exponencial ante límites de velocidad.
- **RF-011.4 (Cola de Despacho en Segundo Plano)**: Cola thread-safe con trabajador en segundo plano para envíos no bloqueantes.
- **RF-011.5 (Escucha Activa de Comandos vía Long-Polling)**: Hilo daemon para responder comandos `/status`, `/pause`, `/resume`, `/report`, `/ayuda` en tiempo real solo a usuarios en lista blanca.
- **RF-011.6 (Operación Continua en Modo Sandbox)**: `P2PBotEngine` debe permitir operar con `MockBinanceP2PClient` cuando `USE_SANDBOX=True` o en desarrollo, emitiendo alertas operativas periódicas cuando se generen o sincronicen órdenes.
- **RF-011.7 (Notificaciones en Acciones de la UI)**: Al sincronizar o simular nuevos ciclos comerciales en el Panel de Control, despachar alertas a Telegram.

## 3. Criterios de Aceptación
- La suite de tests automatizada cubre fallback de formato, rate limiting y despacho en cola.
- `mypy src/` y `ruff check .` pasan con 0 errores.
- Todas las alertas y mensajes enviados respetan la regla constitucional de Cero Secretos.
