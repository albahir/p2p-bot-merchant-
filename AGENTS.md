# AGENTS.md — Bot P2P Binance (p2p-bot-merchant)

Sistema automatizado de comercio P2P en Binance con arquitectura Fail-closed, gestión fiscal y notificaciones por Telegram.

## 🛠️ Stack Técnico y Estructura

- **Lenguaje/Entorno**: Python 3.12+ / Docker Compose.
- **Librerías Clave**: `cryptography` (AES-256-GCM), `httpx`, `tenacity`, `pydantic-settings`, `sqlalchemy`, `streamlit`, `pandas`, `openpyxl`.
- **Bases de Datos**: PostgreSQL / SQLite (entorno local) y Redis (cola de eventos).
- **Módulos Principales**:
  - `src/security/`: Cifrado de credenciales (AES-256-GCM), auditoría SHA-256 append-only y verificación IP.
  - `src/core/`: Cliente oficial Binance P2P, monitoreo de `x-mbx-used-weight` e ingesta histórica de órdenes.
  - `src/integrations/`: Notificador de Telegram con sanitización estricta anti-filtración de credenciales y despacho de comandos.
  - `src/reporting/`: Motor fiscal puro (FIFO y Costo Promedio), conversión BCV y exportación a Excel.
  - `src/reporting/dashboard/`: Dashboard Streamlit para métricas operativas, fiscales y auditoría.

> **Nota sobre paquetes 003 y 004**: Los módulos de pricing algorítmico (003) y pasarela bancaria/Open Banking (004) están actualmente pausados por especificación del usuario.

## 📋 Comandos del Proyecto

- **Tests Automatizados**: `pytest` o `make test`
- **Revisión de Estilo/Types**: `ruff check .` && `mypy src/` o `make lint` / `make typecheck`
- **Entorno Local con Docker**: `docker compose -f docker/docker-compose.yml up -d` o `make dev`

## 🛡️ Reglas de Seguridad Innegociables (La Constitución)

1. **Seguridad Primero**: Permisos mínimos en API Keys (Solo *Reading* + *P2P Trading*). Whitelist de IP obligatoria. Cifrado AES-256-GCM en reposo.
2. **Comportamiento Fail-closed**: Ante cualquier timeout, error 5xx, IP no autorizada o ambigüedad, el bot SE DETIENE y alerta al humano.
3. **Trazabilidad Total**: Cada acción se audita con timestamp, hash encadenado SHA-256 y resultado en `security_events`.
4. **Límite de API Weight**: Monitorear el header `x-mbx-used-weight`. Si supera 5,000, pausar peticiones por 60 segundos.
5. **Cero Secretos en Logs**: Prohibido registrar API Keys, tokens de Telegram o contraseñas en logs, excepciones o mensajes salientes.
6. **Sin RPA No Oficial**: Solo utilizar la API oficial de Binance.

## 🔄 Protocolo Obligatorio para Agentes (SDD & TDD)

Todo agente de IA que opere en este repositorio **DEBE** cumplir estrictamente el siguiente ciclo:

1. **Lectura Previa Obligatoria**: Consultar `.specify/memory/constitution.md`, `memory.md` y la especificación activa (`.specify/specs/NNN-*/tasks.md`) antes de proponer o realizar cualquier modificación.
2. **Ciclo TDD**: Escribir la prueba unitaria/integración primero en rojo (`tests/`), verificar el fallo y luego escribir el código en verde (`src/`).
3. **Actualización Inmediata de `tasks.md`**:
   - Cada tarea atómica completada debe ser marcada **inmediatamente** con `[x]` en el archivo `.specify/specs/NNN-*/tasks.md` correspondiente.
   - No avanzar a la siguiente tarea sin haber marcado la actual.
4. **Actualización Continua de `memory.md`**:
   - Tras completar tareas o iteraciones, registrar en `memory.md` el estado actualizado de los paquetes, las decisiones arquitectónicas tomadas (ADRs) y el progreso atómico.
   - Mantener el usuario siempre al tanto del avance exacto.
5. **Jerarquía de Contratos**:
   `constitution.md` (principios raíz) → `spec.md` (requisitos) → `plan.md` (diseño) → `tasks.md` (pasos atómicos).

## 🚨 Límites de Autoridad del Agente

- ✅ **Permitido**: Crear y modificar código dentro de `src/` y `tests/` respetando los requisitos de la tarea activa en `tasks.md`.
- ⚠️ **Requiere Confirmación Humana**: Modificar el esquema de la base de datos o alterar dependencias en `pyproject.toml`.
- 🚫 **Estrictamente Prohibido**: Modificar la constitución (`constitution.md`) o eliminar tests existentes sin justificación.
