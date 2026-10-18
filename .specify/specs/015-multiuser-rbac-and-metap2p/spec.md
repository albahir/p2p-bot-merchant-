# Spec 015: Autenticación Multi-Capa, Roles (RBAC) y Conector Seguro MetaP2P

## 1. QUÉ (Objetivo del Paquete)
Transformar el sistema de un modelo de operador único a una plataforma multi-usuario con Control de Acceso Basado en Roles (**RBAC**: `ADMIN`, `TRADER`, `INVITADO`), soporte de autenticación desacoplada para Telegram y Dashboard Web (Streamlit), aislamiento visual y funcional estricto para invitados, y un conector seguro para consulta de cédulas contra la API de MetaP2P (`api.metap2p.io`) con credenciales cifradas (AES-256-GCM) y fallback resiliente.

---

## 2. REQUISITOS FUNCIONALES

### RF-01: Modelo de Datos de Usuarios y Persistencia
- **RF-01.1**: Entidad `User` en SQLAlchemy (`src/data/models.py`) con los campos:
  - `id`: Entero autoincremental, clave primaria.
  - `username`: String único (nombre de usuario para web).
  - `password_hash`: String con el hash seguro de contraseña (salt criptográfico).
  - `telegram_id`: String/BigInteger único e indexado (opcional, para vincular cuenta de Telegram).
  - `role`: Enum/String con valores estrictos: `ADMIN`, `TRADER`, `INVITADO`.
  - `is_active`: Booleano (por defecto `True`).
  - `created_at`: Timestamp UTC.
- **RF-01.2**: Repositorio `UserRepository` en `src/data/repositories.py`:
  - `get_by_telegram_id(telegram_id: str | int) -> User | None`.
  - `get_by_username(username: str) -> User | None`.
  - `create_user(username, password_hash, role, telegram_id) -> User`.
  - `update_role(user_id, role) -> User`.
  - `set_active_status(user_id, is_active: bool) -> User`.
  - `list_all() -> list[User]`.

### RF-02: Servicio de Autenticación y Criptografía (`AuthService`)
- **RF-02.1**: Implementar `AuthService` en `src/security/auth_service.py`:
  - Hashing seguro y verificación de contraseñas mediante derivación PBKDF2-HMAC-SHA256 con salt de 16 bytes y 100,000 iteraciones (o bcrypt si está disponible), sin dependencias externas frágiles.
  - Generación y verificación de tokens de sesión temporales para la interfaz web.
  - Inicialización automática: Si no existe ningún usuario `ADMIN` en la base de datos, inicializar automáticamente al Admin principal con el `TELEGRAM_ALERT_CHAT_ID` / `TELEGRAM_ALLOWED_USER_IDS` configurado en `config/.env`.

### RF-03: Control de Acceso y Aislamiento en Telegram
- **RF-03.1**: Identificación y Enrutamiento por Rol:
  - Cuando un usuario interactúa con el bot (comando o botón), consultar su rol en `UserRepository` (con respaldo en `TELEGRAM_ALLOWED_USER_IDS` como `ADMIN`).
- **RF-03.2**: Aislamiento Estricto para el Rol `INVITADO`:
  - **Teclado Táctil en Móvil (`ReplyKeyboard`)**: Solo contiene `[📈 Spreads P2P]`, `[🏛️ Tasa BCV]` y `[❓ Ayuda]`. Ocultar órdenes, comprobantes, cédula, balances y Google Sheets.
  - **Botones de Mensajes (`InlineKeyboard`)**: Solo botones táctiles de Spreads y BCV.
  - **Menú de Comandos Nativo (`BotCommandScopeChat`)**: Al registrar comandos para un invitado, solo listar `/spread`, `/bcv` y `/ayuda`.
  - **Mensaje de `/ayuda`**: Adaptado para no revelar la existencia de funciones de conciliación, órdenes o cédulas.
  - **Bloqueo Fail-closed**: Si un invitado intenta forzar un comando restringido (`/cedula`, `/status`, `/conciliacion`, `/pause`, etc.), responder: `⛔ Opción reservada para Traders y Administradores` y registrar el evento en `security_events`.
  - **Rate Limit**: Máximo 10 peticiones por hora para evitar saturación de la API.
- **RF-03.3**: Flujo de Solicitud y Aprobación Dinámica para Nuevos Usuarios:
  - Si un usuario no registrado escribe al bot, el bot le informa su ID y envía una alerta al Administrador con botones táctiles: `[✅ Aprobar Invitado]`, `[💼 Aprobar Trader]`, `[⛔ Bloquear]`.
  - El Administrador puede aprobar o revocar sin reiniciar el bot.
- **RF-03.4**: Comandos de Gestión para el Administrador:
  - `/usuarios`: Lista de usuarios registrados, roles y estado.
  - `/autorizar <telegram_id> <ROL>`: Asignar o promover rol.
  - `/revocar <telegram_id>`: Desactivar acceso de inmediato.

### RF-04: Autenticación y Renderizado Condicional en Streamlit
- **RF-04.1**: Pantalla de Login `login_view.py` en `src/reporting/dashboard/views/` con el tema Obsidian Glassmorphism:
  - Formulario de credenciales (`username`, `password`) validado contra `AuthService`.
  - Estado de sesión en `st.session_state["user"]` y `st.session_state["user_role"]`.
  - Botón de cierre de sesión (*Logout*) en la barra lateral.
- **RF-04.2**: Renderizado Condicional de Pestañas en `app.py`:
  - Si el rol es `INVITADO`: Renderizar únicamente la pestaña `📈 Monitor & Arbitraje P2P`. Ocultar y proteger las pestañas de conciliación, órdenes, comprobantes y configuración.
  - Si el rol es `TRADER` o `ADMIN`: Renderizar todas las pestañas operativas y de cumplimiento.
  - Badge de rol visible en el `terminal_header`.

### RF-05: Conector Seguro para Búsqueda de Cédulas MetaP2P
- **RF-05.1**: Cliente `MetaP2PClient` en `src/integrations/metap2p_client.py`:
  - Base URL: `https://api.metap2p.io/api`.
  - Autenticación: `POST /api/login` con correo y contraseña para obtener `access_token`.
  - Búsqueda: `GET /api/dni/search?dni={cedula}` con cabecera `Authorization: Bearer <access_token>`.
  - Parseo del JSON de respuesta (`full_name`, `dni_prefix`, `dni_number`, `rif`, `birth_date`, `cne`).
  - Detección de errores: Capturar `HTTP 400` con `RECORD_NOT_FOUND` y `HTTP 401` para auto-renovación de token.
- **RF-05.2**: Cero Secretos en Texto Plano:
  - Guardar credenciales de MetaP2P cifradas con AES-256-GCM en la tabla `encrypted_secrets` mediante `ApiKeyManager`.
- **RF-05.3**: Integración en `IdentityService`:
  - Cascada de resolución de identidades:
    1. Caché local en SQLite (`identities`).
    2. MetaP2P API.
    3. SENIAT Oficial XML.
    4. CNE Ciudadano.
- **RF-05.4**: Permisos de Ejecución:
  - Exclusivo para `ADMIN` y `TRADER`. Prohibido para `INVITADO`.
