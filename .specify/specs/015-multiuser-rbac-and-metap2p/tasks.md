# Tareas Atómicas: SPEC-015 (Multi-usuario, RBAC y MetaP2P)

## 📌 Lista de Tareas

### Fase 1: Modelo de Datos y Servicio de Autenticación
- [x] **T01**: Crear modelo `User` en `src/data/models.py` (`id`, `username`, `password_hash`, `telegram_id`, `role`, `is_active`, `created_at`).
- [x] **T02**: Implementar `UserRepository` en `src/data/repositories.py` con consultas por username, telegram_id, listado y actualización de roles.
- [x] **T03**: Implementar `AuthService` en `src/security/auth_service.py` con hashing PBKDF2-HMAC-SHA256, verificación de contraseñas, control de sesiones y auto-seeding del Administrador principal.
- [x] **T04**: Escribir y verificar pruebas unitarias en `tests/unit/test_auth_service.py`.

### Fase 2: Conector Seguro MetaP2P
- [x] **T05**: Implementar `MetaP2PClient` en `src/integrations/metap2p_client.py` con login (`POST /api/login`), almacenamiento volátil de `access_token`, auto-renovación ante 401 y búsqueda de DNI (`GET /api/dni/search`).
- [x] **T06**: Integrar `MetaP2PClient` en `IdentityService` (`src/security/identity_service.py`) como fallback prioritario antes del SENIAT/CNE.
- [x] **T07**: Escribir y verificar pruebas unitarias en `tests/unit/test_metap2p_client.py`.

### Fase 3: Control de Acceso y Aislamiento en Telegram
- [x] **T08**: Actualizar `TelegramNotifier` y `TelegramCommandPoller` para soportar RBAC:
  - Teclado móvil persistente (`ReplyKeyboard`) reducido a 3 botones para `INVITADO`.
  - Botones táctiles (`InlineKeyboard`) filtrados para `INVITADO`.
  - Bloqueo y alerta Fail-closed en `handle_command` para comandos no autorizados.
  - Comandos de administración `/usuarios`, `/autorizar`, `/revocar` exclusivos para `ADMIN`.
  - Flujo de solicitud y aprobación interactiva con botones táctiles al Admin para nuevos usuarios.
- [x] **T09**: Escribir y verificar pruebas unitarias en `tests/unit/test_telegram_rbac.py`.

### Fase 4: Autenticación y Vistas Condicionales en Streamlit
- [x] **T10**: Implementar vista de Login `login_view.py` en `src/reporting/dashboard/views/` con tema Obsidian Glassmorphism y adaptar `src/reporting/dashboard/app.py` para renderizado condicional de pestañas según rol (`INVITADO` solo ve Monitor & Spreads P2P).

### Fase 5: Calidad, Verificación y Auditoría
- [x] **T11**: Ejecutar suite completa (`pytest`, `ruff check .`, `mypy src/`) y comprobar 0 errores (119/119 pruebas unitarias e integración en verde, mypy sin errores, ruff 100% limpio).
- [x] **T12**: Registrar progreso en `tasks.md` y documentar ADR 036 en `memory.md`.

### Fase 6: Resiliencia de Alertas, Arbitraje Interbancario y Persistencia de Cédulas
- [x] **T13**: Deduplicación inteligente anti-spam en `RateAlertService` (evitar alertas idénticas repetidas cada 10 min si las tasas no cambian).
- [x] **T14**: Garantizar arbitraje cruzado estrictamente entre entidades distintas en `SpreadMonitor.find_best_cross_arbitrage` (`q_buy.bank_name != q_sell.bank_name`).
- [x] **T15**: Persistencia permanente de identidades en base de datos con `IdentityRepository` y nuevo comando `/cedulas` en Telegram.
- [x] **T16**: Pestaña `"👤 Directorio Cédulas"` en Streamlit Dashboard con búsqueda en tiempo real e historial persistente.
- [x] **T17**: Suite de pruebas completa en verde con **123/123 tests pasando** y documentación en ADR 037 de `memory.md`.

