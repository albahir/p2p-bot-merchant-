# Runbook de Operación y Respuesta a Incidentes

## Procedimiento de Rotación de Credenciales
1. A los 25 días de antigüedad, el bot emite una alerta crítica por Telegram.
2. Generar un nuevo par de llaves Ed25519 en Binance Merchant.
3. Ejecutar el script `scripts/rotate_api_keys.py`.
4. Ingresar la nueva llave pública/privada y verificar conectividad con `tests/unit/test_binance_client.py`.
5. Eliminar la llave anterior en la consola de Binance.

## Procedimiento ante Alerta Fail-Closed
1. El bot se detiene automáticamente si:
   - Falla la validación de IP contra la whitelist en el arranque.
   - La API de Binance retorna errores 5xx sostenidos o 429.
   - Hay discrepancia de firmas o tokens ausentes.
2. Acciones del operador:
   - Revisar `security_events` en la base de datos para ver el último hash de evento.
   - Comprobar la IP pública del servidor mediante `curl ifconfig.me`.
   - Reiniciar el servicio con `docker compose restart engine` una vez validado.
