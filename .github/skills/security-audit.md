# Skill: Auditoría y Seguridad Criptográfica

## Capacidades
- Cifrado simétrico autenticado AES-256-GCM para llaves de API, secrets y tokens en reposo.
- Gestión de clave maestra exclusivamente en memoria y variables de entorno.
- Registro append-only de accesos y rotaciones en tabla `security_events` con huella digital SHA-256 encadenada.
- Verificación fail-closed de dirección IP pública del servidor al inicio contra lista blanca configurada.
- Detección estricta de cadenas sensibles en formateadores de logs y trazas de error.
