# Tasks: SPEC-020 Migración Integral a Interfaz Institucional "P2P Merchant OS"

## Fase 1: Endpoints Backend de Soporte (TDD)
- [x] T20.1: Escribir tests unitarios en rojo (`tests/unit/test_stitch_ui_backend_endpoints.py`) para registro con `google_sheet_id`, origen de permisos RBAC (`.env` vs BD), autorización web de Telegram ID, estado sanitizado de Telegram y sincronización manual de Sheets.
- [x] T20.2: Implementar esquemas y endpoints en `src/api/schemas/auth.py`, `src/api/schemas/settings.py`, `src/api/routes/auth.py`, `src/api/routes/users.py` y `src/api/routes/settings.py` hasta pasar tests en verde.

## Fase 2: Sistema de Diseño, Remoción de UI Anterior y Shell Institucional
- [x] T20.3: Configurar tokens de `DESIGN (2).md` en `frontend/tailwind.config.ts`, `frontend/src/app/globals.css`, `frontend/src/app/layout.tsx`, `frontend/src/lib/theme-context.tsx` y extender `frontend/src/lib/api.ts`.
- [x] T20.4: Eliminar componentes obsoletos de la interfaz anterior (`terminal-header.tsx`, `telegram-mini-app-bar.tsx`, `binance-settings-card.tsx`) y crear `frontend/src/components/app-shell.tsx`.

## Fase 3: Implementación de las 8 Pantallas Corregidas
- [x] T20.5: Implementar Pantalla 1 (`/login`) y Pantalla 2 (`/register`) con diseño Obsidian, validación de contraseña, SSO Telegram y vinculación opcional de Sheet.
- [x] T20.6: Implementar Pantalla 3 (`/` Matriz de Spreads & Bancos) y Pantalla 4 (`/calculator` Calculadora Instantánea de Ciclos P2P con comisión Pago Móvil 0.3%).
- [x] T20.7: Implementar Pantalla 5 (`/orders` Ganancias Reales & Órdenes) y Pantalla 6 (`/accounting` Contabilidad, Libro Diario/Mayor SENIAT & OCR).
- [x] T20.8: Implementar Pantalla 7 (`/sheets` Sincronización Google Sheets) y Pantalla 8 (`/settings` Configuración API, Seguridad Fail-Closed & Operadores RBAC), redirigiendo `/admin` y `/fiscal`.

## Fase 4: Verificación Integral y Documentación
- [x] T20.9: Ejecutar compilación estricta de producción en Next.js (`npm run build`), suite `pytest` y linter `ruff check`, y actualizar `memory.md`.
