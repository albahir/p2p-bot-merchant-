# Plan 001: Fundación de Seguridad

## Stack
- Python 3.12+
- `cryptography` (AES-256-GCM)
- `python-dotenv` (variables de entorno)
- `pydantic-settings` (validación de config)

## Arquitectura
- `src/security/api_key_manager.py`: cifra, descifra, rota.
- `src/security/audit_logger.py`: tabla `security_events` append-only.
- `src/security/permissions.py`: valida permisos de la API Key al arrancar.
- `config/settings.py`: clase `Settings` con Pydantic que valida la presencia
  de `MASTER_ENCRYPTION_KEY` y la IP del servidor.

## Decisiones
- **Por qué AES-256-GCM**: modo autenticado, detecta manipulación del ciphertext.
- **Por qué no Vault**: se puede migrar después; para empezar, variable de entorno
  cifrada es suficiente.
- **Por qué append-only**: la auditoría no debe poder modificarse retroactivamente.

## Dependencias
- Ninguna. Este es el primer paquete.
