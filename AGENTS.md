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
  - `src/reporting/dashboard/`: Panel de Control y Dashboard Streamlit (Mission Control) para métricas operativas, fiscales, auditoría y control de tareas sin comandos de consola.

> **Nota sobre paquetes 003 y 004**: Los módulos de pricing algorítmico (003) y pasarela bancaria/Open Banking (004) están actualmente pausados por especificación del usuario.

## 👥 Agentes de IA en el Repositorio (`.github/agents/`)
- `pm.md`: Product Manager y alineación con requisitos funcionales.
- `architect.md`: Arquitecto de software y decisiones ADR.
- `backend.md`: Desarrollador backend y servicios core (TDD).
- `frontend.md`: Desarrollador Frontend & UI/UX (Streamlit, componentes reactivos, seguridad de UI).
- `security.md`: Ingeniero de Ciberseguridad & Auditor Criptográfico (Hardening, validación de firmas, drift, rate limits).
- `qa.md`: QA Tester y cobertura de pruebas.
- `devops.md`: DevOps, Docker y pipelines de CI/CD.
- `researcher.md`: Investigador Técnico & Especialista en Documentación (APIs, benchmarking de librerías, cloud 24/7).

## 📋 Comandos del Proyecto

- **Iniciar Bot (Engine)**: `python -m src.main` o `make run`
- **Iniciar Panel / Dashboard**: `streamlit run src/reporting/dashboard/app.py` o `make dashboard`
- **Tests Automatizados**: `pytest` o `make test`
- **Revisión de Estilo/Types**: `ruff check .` && `mypy src/` o `make lint` / `make typecheck`
- **Entorno Local con Docker**: `docker compose -f docker/docker-compose.yml up -d` o `make dev`

## 🛡️ Reglas de Seguridad Innegociables (La Constitución)

1. **Seguridad Primero**: Permisos mínimos en API Keys (Solo *Reading* + *P2P Trading*). Whitelist de IP obligatoria. Cifrado AES-256-GCM en reposo.
2. **Comportamiento Fail-closed**: Ante cualquier timeout, error 5xx, IP no autorizada o ambigüedad, el bot SE DETIENE y alerta al humano.
3. **Trazabilidad Total**: Cada acción se audita con timestamp, hash encadenado SHA-256 y resultado en `security_events`.
4. **Límite de API Weight**: Monitorear el header `x-mbx-used-weight`. Si supera 5,000, pausar peticiones por 60 segundos.
5. **Cero Secretos en Logs o UI**: Prohibido registrar API Keys, tokens de Telegram o contraseñas en logs, excepciones, mensajes salientes o mostrarlas en texto plano en la UI.
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
