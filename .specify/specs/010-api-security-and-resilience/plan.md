# Plan 010: Seguridad Avanzada de API, Control de Concurrencia y Resiliencia

## Stack Técnico
- `pydantic` (modelos de validación en tiempo de ejecución)
- `cryptography` (validación de estructura PEM y tipos de clave)
- `threading` (`Lock` thread-safe para sincronización idempotente)
- `httpx` y `tenacity` (control granular de reintentos)

## Arquitectura de Componentes
- `src/core/binance_schemas.py`: Modelos Pydantic tipados de ordenes, anuncios y respuestas de servidor.
- `src/core/concurrency.py`: `SyncLockManager` singleton para exclusión mutua de operaciones de red.
- `src/security/key_validator.py`: Validador de formato criptográfico PEM para claves Ed25519/RSA.
- `src/core/binance_client.py`: Integración de compensación de drift temporal y clasificación fail-closed de errores.
- `src/reporting/dashboard/components/credential_manager.py`: Integración de validación previa en UI.

## Decisiones de Arquitectura (ADRs)
1. **Locking en Memoria (Singleton Lock)**: Para evitar dependencias adicionales y latencia innecesaria en operaciones locales de sincronización, se implementa un `threading.Lock` robusto con control de tiempo de expiración (lease timeout de 60s) en caso de caída imprevista.
2. **Validación Pre-Cifrado**: Validar la clave privada antes de cifrarla con AES-256-GCM asegura que no se almacenen claves corruptas o incompletas en la base de datos.
3. **No-Retry ante Errores de Autenticación**: Los errores 401/403 o `-2014`/`-2015` son definitivos. Reintentar solo acelera el baneo de IP por parte del cortafuegos de Binance.

## Dependencias
- Paquete 001 (Fundación de Seguridad)
- Paquete 002 (Conector Binance P2P)
- Paquete 009 (Panel de Control UI)
