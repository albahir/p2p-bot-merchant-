# Spec 001: Fundación de Seguridad

## QUÉ
Un módulo que gestiona el ciclo de vida de las credenciales del bot
(API Keys de Binance, tokens de Telegram)
de forma cifrada, auditable y con rotación programada.

## Requisitos Funcionales
- RF-01: Almacenar API Keys cifradas con AES-256-GCM.
- RF-02: La clave maestra de cifrado vive en variable de entorno, nunca en disco.
- RF-03: Auditar cada acceso a credenciales en tabla append-only con hash SHA-256.
- RF-04: Alertar vía Telegram cuando una API Key cumpla 25 días sin rotar.
- RF-05: Verificar en startup que la IP del servidor coincide con la whitelist.

## Requisitos No Funcionales
- RNF-01: El descifrado debe ocurrir en memoria, nunca en disco temporal.
- RNF-02: Si la verificación de IP falla, el bot no arranca (fail-closed).

## Criterios de Aceptación
- [ ] Un test unitario verifica que la API Key nunca aparece en logs.
- [ ] Un test de integración verifica que la rotación de claves no interrumpe operaciones.
- [ ] Un test de seguridad verifica que la clave maestra ausente bloquea el arranque.
