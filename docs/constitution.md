# Constitución del Proyecto P2P Bot (Copia de Referencia)

> Documento canónico: [`.specify/memory/constitution.md`](file:///c:/p2p-bot-merchant/.specify/memory/constitution.md)

## Principios No Negociables

1. **Seguridad primero**: API Keys con permisos mínimos (solo Reading + P2P Trading).
   Whitelist de IP obligatoria. Cifrado AES-256-GCM en reposo. Nunca en texto plano.

2. **Fail-closed**: Ante cualquier respuesta ambigua (timeout, error 5xx, webhook sin firma),
   el bot se detiene y alerta al humano. Nunca asume éxito.

3. **"Botón presionado ≠ pago confirmado"**: Ninguna liberación de cripto ocurre sin
   verificación bancaria real. El estado de la app no es fuente de verdad.

4. **Trazabilidad total**: Cada acción del bot se registra con timestamp, orderId,
   resultado y peso consumido de la API.

5. **Respeto a los límites de Binance**: Monitorear `x-mbx-used-weight`.
   Pausar antes de acercarse al límite de 6,000/min. Backoff exponencial siempre.

6. **Separación de responsabilidades**: El motor de trading no conoce la UI.
   El motor fiscal solo consume la tabla `orders`. Las integraciones son inyectables.

7. **Sin herramientas de terceros no autorizadas**: Solo la API oficial de Binance.
   Nunca RPA no oficial sobre Binance.

8. **Los secretos nunca se loguean**: Ni API Keys, ni credenciales bancarias,
   ni tokens de Telegram, ni en logs ni en excepciones.
