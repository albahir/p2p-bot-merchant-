# Spec 010: Seguridad Avanzada de API, Control de Concurrencia y Resiliencia

## QUÉ
Un subsistema integral de hardening y resiliencia para la interacción con la API de Binance P2P y los controles de la UI. Protege contra desincronización horaria (clock drift), previene dobles peticiones simultáneas (race conditions), valida estrictamente la estructura de llaves privadas Ed25519 y ejecuta bloqueos fail-closed inmediatos ante rechazos de autenticación para salvaguardar la IP del comerciante frente a baneos (WAF).

---

## Requisitos Funcionales

### 1. Sincronización Horaria y Compensación de Deriva (Clock Drift)
- **RF-01**: Sincronizar periódicamente el reloj local contra el endpoint oficial `GET /api/v3/time`.
- **RF-02**: Calcular y aplicar el `time_offset_ms = serverTime - localTime` en cada llamada firmada (`timestamp = local_time + offset`), previniendo el error crítico `-1021 (TIMESTAMP_OUT_OF_RECVWINDOW)`.

### 2. Bloqueo de Concurrencia e Idempotencia (Concurrency Locking)
- **RF-03**: Implementar un semáforo / mutex de sincronización (`SyncLock`) en memoria para que múltiples clics en la interfaz o hilos paralelos nunca envíen solicitudes concurrentes a Binance P2P.
- **RF-04**: Si una sincronización está en curso, cualquier intento adicional debe ser rechazado inmediatamente con aviso visual ("Sincronización en curso, por favor espere").

### 3. Validación Estricta de Credenciales y Formato PEM
- **RF-05**: Antes de cifrar y almacenar una `binance_private_key`, validar mediante `cryptography` que:
  - Contiene encabezados válidos PEM (`-----BEGIN PRIVATE KEY-----`).
  - Es una clave decodificable válida (Ed25519 o RSA de al menos 2048 bits).
  - Si la clave está corrupta o incompleta, rechazar en el formulario con error claro sin registrarla.

### 4. Guardias Fail-Closed ante Códigos Críticos de Binance
- **RF-06**: Ante códigos HTTP 401, 403 o códigos internos `-2014` / `-2015` (API Key inválida o IP no autorizada):
  - Suspender de inmediato los reintentos automáticos para evitar el baneo automático de IP por WAF de Binance (HTTP 418).
  - Registrar evento crítico `SECURITY_AUTH_FAILURE` en `security_events`.
  - Emitir alerta prioritaria por Telegram al operador.

### 5. Validación Tipada de Payloads (Pydantic Runtime Validation)
- **RF-07**: Validar todas las respuestas de `listUserOrderHistory` y `search` contra esquemas Pydantic tipados (`BinanceOrderHistoryResponse`, `BinanceOrderMatchItem`), impidiendo que payloads inesperados o alterados contaminen la base de datos o el motor fiscal.

---

## Requisitos No Funcionales
- **RNF-01**: El cálculo de drift y chequeo de lock debe ejecutarse en menos de 5ms en memoria.
- **RNF-02**: Cero tolerancia a fugas: las trazas de error de validación nunca deben reflejar partes de la clave privada o del payload sin sanitizar.

---

## Criterios de Aceptación
- [ ] Un test verifica que llamadas con drift horario son corregidas con el offset del servidor.
- [ ] Un test verifica que dos solicitudes simultáneas de ingesta son serializadas sin duplicar llamadas.
- [ ] Un test verifica que una clave privada Ed25519 inválida es rechazada en la validación antes de guardarse.
- [ ] Un test verifica que un error 401 suspende los reintentos y no entra en bucle exponencial.
