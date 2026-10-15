# Tasks 006: Notificaciones Telegram

- [x] T-006.1 Configurar credenciales del bot de Telegram cifradas en Paquete 001.
- [x] T-006.2 Implementar `src/integrations/telegram_notifier.py` con envío asíncrono y sanitización.
- [x] T-006.3 Implementar validación de remitente (`TELEGRAM_ALLOWED_USER_IDS`).
- [x] T-006.4 Implementar dispatcher de comandos `/status`, `/pause`, `/resume`, `/report`.
- [x] T-006.5 Test unitario: ningún mensaje enviado contiene claves ni tokens.
- [x] T-006.6 Test integración: comandos no autorizados son rechazados silenciosamente y auditados.
