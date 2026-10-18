# Guía de Integración: Google Stitch MCP & Terminal UI

## 1. Visión General
Google Stitch (`stitch.withgoogle.com`) es la plataforma de diseño y prototipado generativo de interfaces de usuario impulsada por IA. A través del protocolo **MCP (Model Context Protocol)**, el bot puede conectar herramientas de diseño con el código de la terminal Streamlit (`src/reporting/dashboard/`).

---

## 2. Servidor MCP y Arquitectura Autónoma

Google Stitch (`stitch.withgoogle.com`) no cuenta con un paquete oficial de npm bajo el nombre `@google/stitch-mcp` (intentar invocarlo produce `HTTP 404 Not Found`). Los paquetes comunitarios existentes (como `stitch-mcp` o `@_davideast/stitch-mcp`) requieren credenciales de Google Cloud (`gcloud auth application-default login`) y un proyecto habilitado.

### Arquitectura Autónoma y Resiliente (Constitución Fail-Closed):
Para evitar depender de procesos Node.js externos o de servidores MCP de terceros que puedan fallar por falta de red o cambios de API, **el bot integra de forma nativa los tokens de diseño y componentes de Stitch en Python**:
- Todos los estilos, variables CSS y paleta Obsidian Fintech están compilados localmente en [`src/reporting/dashboard/theme.py`](file:///c:/p2p-bot-merchant/src/reporting/dashboard/theme.py).
- No es necesario mantener un servidor MCP de Stitch activo en `mcp_config.json` para ejecutar el Dashboard o el bot.

Si en el futuro deseas conectar un servidor MCP comunitario de Stitch:
```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["-y", "stitch-mcp"],
      "env": {
        "GOOGLE_CLOUD_PROJECT": "TU_PROJECT_ID"
      }
    }
  }
}
```

---

## 3. Tokens de Diseño Importados (Obsidian Fintech)

Para garantizar consistencia visual y no depender de llamadas de red en tiempo real durante la ejecución del bot en producción, los tokens de diseño de Stitch se encuentran compilados de forma nativa en:
[`src/reporting/dashboard/theme.py`](file:///c:/p2p-bot-merchant/src/reporting/dashboard/theme.py)

### Paleta Oficial
- **Fondo Principal (Deep Obsidian)**: `#0B0E14`
- **Superficie de Tarjetas (Glass Surface)**: `rgba(22, 27, 34, 0.75)` con `backdrop-filter: blur(16px)`
- **Bordes Translúcidos**: `rgba(255, 255, 255, 0.08)`
- **Verde Esmeralda (Inflows / Ganancias / Balanced)**: `#10B981`
- **Rojo Rubí (Outflows / Discrepancias / Errores)**: `#F43F5E`
- **Cian Neón (Volumen / Spread / Binance)**: `#06B6D4`
- **Ámbar (Comisiones / Comprobantes Pendientes)**: `#F59E0B`
- **Texto Principal**: `#F0F6FC`
- **Texto Secundario**: `#8B949E`

---

## 4. Arquitectura de Componentes Modulares

La interfaz moderna se compone de módulos independientes ubicados en `src/reporting/dashboard/components/`:
1. `terminal_header.py`: Barra superior de telemetría operativa en vivo (Fail-closed, Binance weight, IP pública).
2. `kpi_cards.py`: Tarjetas reactivas de resumen contable y de mercado P2P.
3. `receipt_center.py`: Centro interactivo de comprobantes bancarios y uploader OCR en memoria.
4. `ai_telemetry.py`: Telemetría en vivo del pool de claves Gemini Vision.

---

## 5. Reglas de Seguridad en UI (La Constitución)
1. **Cero Secretos**: Ninguna API Key (Binance, Gemini, Stitch) se renderiza jamás en texto plano en la interfaz ni en el código fuente HTML/CSS.
2. **Procesamiento Volátil (Memory-Only)**: Las imágenes subidas por el uploader web se procesan exclusivamente en memoria RAM (`io.BytesIO`) y nunca se guardan en el disco del servidor.
3. **Fail-Closed**: Si el servidor MCP o las APIs externas están inactivas, la interfaz carga los tokens locales de `theme.py` sin interrumpir la operación comercial.
