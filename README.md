# 🤖 Bot P2P Merchant Binance (`p2p-bot-merchant`)

Sistema profesional, auditable y seguro para comercio y gestión de órdenes P2P en Binance, desarrollado bajo la metodología **Spec-Driven Development (SDD)** con arquitectura **Fail-Closed**.

---

## 🌟 Características Principales

- 🛡️ **Fundación de Seguridad (Paquete 001)**: Cifrado en reposo con **AES-256-GCM**, auditoría inmutable append-only con encadenamiento de hash **SHA-256** y control estricto de whitelist de IP.
- ⚡ **Conector Binance P2P (Paquete 002)**: Conexión a la API oficial C2C, monitoreo activo del header `x-mbx-used-weight` (pausa preventiva ante > 5,000) y control de ventana máxima de 30 días para consultas.
- 📊 **Motor Fiscal e Historial (Paquete 005)**: Cálculo de ganancia acumulada y costo de adquisición con métodos **FIFO** y **Costo Promedio Ponderado**, comisiones integradas y exportación a **Excel** (dos hojas: Detalle y Resumen) y Google Sheets.
- 📱 **Alertas Telegram (Paquete 006)**: Notificador asíncrono con sanitización previa y estricta para evitar cualquier fuga accidental de secretos o tokens.
- 📈 **Dashboard de Control (Paquete 007)**: Panel web interactivo con **Streamlit** en modo solo lectura para monitorear volumen, P&L, transacciones recientes y registros de seguridad.
- 🚀 **CI/CD e Infraestructura (Paquete 008)**: Workflows de GitHub Actions (`ci.yml`, `security.yml`, `cd.yml`) con escaneo de secretos por `gitleaks`, auditoría de dependencias y despliegue en Docker Compose.

> **Nota**: Los paquetes 003 (Estrategia de Pricing) y 004 (Verificación Bancaria) están pausados/diferidos por decisión estratégica.

---

## 🏗️ Estructura del Proyecto

```text
p2p-bot-merchant/
│
├── .github/
│   ├── agents/                  # Prompts de roles (PM, Arquitecto, Backend, QA, DevOps)
│   ├── skills/                  # Skills de integración, seguridad y verificación
│   ├── workflows/               # CI/CD (ci.yml, cd.yml, security.yml)
│   └── prompts/                 # Prompt maestro del pipeline SDD
│
├── .specify/
│   ├── memory/constitution.md   # La Constitución: 8 principios no negociables
│   ├── specs/                   # Especificaciones (001, 002, 005, 006, 007, 008)
│   ├── templates/               # Plantillas para spec, plan y tasks
│   └── scripts/                 # Scripts de validación de specs y setup
│
├── .agents/
│   ├── rules/global-rules.md    # Reglas activas para agentes de IA
│   ├── skills/                  # Skills locales (binance-p2p, logging-dashboard)
│   └── workflows/               # Workflows de desarrollo guiado por especificación
│
├── src/
│   ├── core/                    # Cliente Binance P2P e Ingesta histórica
│   ├── integrations/            # Alertas y comandos de Telegram
│   ├── data/                    # Modelos SQLAlchemy, conexión DB y repositorios
│   ├── reporting/               # Motor fiscal (FIFO/Promedio) y reportes Excel
│   │   └── dashboard/           # Dashboard interactivo Streamlit
│   └── security/                # Cifrado AES-256-GCM, auditoría SHA-256 y permisos
│
├── tests/
│   ├── unit/                    # Pruebas unitarias de seguridad, cliente y fiscal
│   ├── integration/             # Pruebas de integración (rotación de claves)
│   ├── e2e/                     # Ciclo completo simulado
│   └── mocks/                   # Respuestas simuladas de la API de Binance
│
├── docs/                        # Constitución, arquitectura, referencia API y runbook
├── scripts/                     # Inicialización de DB, datos de prueba y rotación
├── config/                      # Configuración Pydantic, logging y plantilla .env
├── docker/                      # Dockerfiles multi-stage y docker-compose.yml
├── Makefile                     # Comandos rápidos (test, lint, typecheck, dev)
├── pyproject.toml               # Dependencias y configuración de herramientas
├── AGENTS.md                    # Instrucciones globales para agentes
├── memory.md                    # Memoria persistente y estado por paquetes
└── README.md                    # Documentación principal del repositorio
```

---

## 🚀 Inicio Rápido

### 1. Configuración de Variables de Entorno

Copia el archivo de plantilla y define tu clave maestra (mínimo 32 caracteres):

```bash
cp config/.env.example config/.env
```

### 2. Comandos de Desarrollo

```bash
# Ejecutar suite de pruebas
make test

# Verificar linter y tipos estáticos
make lint
make typecheck

# Levantar infraestructura local con Docker
make dev
```