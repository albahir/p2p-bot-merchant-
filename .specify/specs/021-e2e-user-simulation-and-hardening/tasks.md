# Tasks: SPEC-021 Simulación Integral de Usuario E2E, Corrección Contable/Fiscal y Hardening de Seguridad

## Fase 1: Suite TDD de Simulación Real de Usuario (Rojo)
- [x] T21.1: Crear `tests/e2e/test_user_simulation_audit.py` simulando a un usuario real en las 8 pantallas web, cálculos financieros, persistencia en BD y todos los roles/comandos del Bot de Telegram (`INVITADO`, `TRADER`, `ADMIN`), verificando fallo inicial en rojo.

## Fase 2: Correcciones Críticas de Seguridad, Autenticación y Persistencia (Verde Backend)
- [x] T21.2: Eliminar filtración de `debug_code` OTP en `POST /api/auth/recover-password`, soportar recuperación por `telegram_id`, y permitir registro web sin error 500 de operadores pre-autorizados en `app_users`.
- [x] T21.3: Corregir vulnerabilidad en `sanitize_message` (`src/integrations/telegram_notifier.py`) que exponía claves hexadecimales de 64 caracteres en texto plano.
- [x] T21.4: Corregir encadenamiento SHA-256 (`JournalEntryRepository.get_last_entry`), idempotencia de asientos, desglose multi-banco en `get_live_theoretical_balance`, normalización timezone en `reconcile_orphan_vouchers` y validación Fail-closed de OCR en `BankReceiptOCR`.
- [x] T21.5: Poblar `bcv_rate` real en sincronización/importación de órdenes (`BinanceHistorySyncer`), soportar `cost_method` (`FIFO` | `AVG`) y métricas `VES`/`USDT` en `/api/fiscal/summary`, persistir snapshots reales en `POST /api/fiscal/reconcile` + `GET /api/fiscal/snapshot`, y escalar `amount_usdt` / corregir comisión bancaria unilateral en `SpreadMonitor`.
- [x] T21.6: Corregir flujos del Bot de Telegram (`/estado` para Traders/Admins, envío de `/cierre` al `chat_id` solicitante, creación de asientos contables al subir comprobante OCR por Telegram, eliminación de duplicados en `/vtype:`, ocultamiento de botones Admin a Traders, bloqueo limpio en `/revocar`, persistencia compartida de `/pause` y migraciones `init_db` limpias para PostgreSQL/Neon).

## Fase 3: Correcciones Frontend Next.js ("P2P Merchant OS")
- [x] T21.7: Reemplazar enlaces `<a href="...?token=...">` (HTTP 401 y fuga de JWT en URL) por descarga autenticada con `Authorization: Bearer` (`Blob`) en `/orders` y `/accounting`, y eliminar tormenta de reconexión en `useWebSocket.ts`.
- [x] T21.8: Conectar selector `FIFO / Costo Promedio` y unidades reales en `/orders`, conectar `CERRAR-MES` persistente y etiquetas de 6 piezas (`USDT` vs `Bs.`) en `/accounting`, validar `res.success` en `/sheets`, y preservar métricas en vivo en `/settings`.

## Fase 4: Verificación Integral, Auditoría de Seguridad y Documentación
- [x] T21.9: Ejecutar suite de pruebas (`pytest`), `mypy`, `ruff check .`, compilación de producción Next.js (`npm run build`), auditoría preventiva `security-review` y actualizar `memory.md`.
- [x] T21.10: Alinear `tests/unit/test_api_auth_routes.py::test_password_recovery_and_reset_flow` con la eliminación de `debug_code` OTP en respuestas HTTP (Regla #5 Constitución: Cero Secretos), validando la entrega del código OTP vía `TelegramNotifier.send_alert` y verificando la suite completa en CI.
