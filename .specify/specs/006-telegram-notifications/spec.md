# Spec 006: Notificaciones Telegram

## QUÉ
Un bot de Telegram que envía alertas de eventos y recibe comandos de monitoreo y control operacional.

## Requisitos Funcionales
- RF-01: Enviar alerta inmediata ante nueva orden, error de API, advertencia de IP o anomalía.
- RF-02: Recibir comandos `/status`, `/pause`, `/resume`, `/report`.
- RF-03: Cero secretos: nunca exponer credenciales, API Keys ni datos sensibles en mensajes.
- RF-04: Enviar alerta a los 25 días de antigüedad de credenciales para rotación obligatoria.

## Criterios de Aceptación
- [ ] Test unitario verifica que ningún mensaje emitido contiene la API Key o secrets.
- [ ] Test verifica que `/status` responde con el estado de sincronización y weight de Binance.
- [ ] Test verifica que el token de Telegram se recupera descifrado desde el Paquete 001.
