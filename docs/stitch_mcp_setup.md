# Guía de Integración: Google Stitch MCP & Terminal UI

## 1. Visión General
Google Stitch (`stitch.withgoogle.com`) es la plataforma de diseño y prototipado generativo de interfaces de usuario impulsada por IA. A través del protocolo **MCP (Model Context Protocol)**, el bot puede conectar herramientas de diseño con el código de la terminal Streamlit (`src/reporting/dashboard/`).

---

## 2. Configuración del Servidor MCP de Stitch

El servidor MCP de Stitch se encuentra registrado en el archivo de configuración global de Gemini/Antigravity:
`C:\Users\jonan\.gemini\config\mcp_config.json`

```json
{
  "mcpServers": {
    "stitch": {
      "command": "C:\\p2p-bot-merchant\\.bin\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@google/stitch-mcp"
      ],
      "env": {
        "STITCH_API_KEY": "TU_API_KEY_DE_STITCH"
      }
    }
  }
}
```

### Pasos para Configurar tu Clave de Stitch:
1. Accede a [Google Stitch](https://stitch.withgoogle.com) con tu cuenta de Google Cloud / Workspace.
2. Ve a **Settings / Integrations / Developer API**.
3. Genera una **Stitch API Key**.
4. Coloca la clave en la variable de entorno `STITCH_API_KEY` dentro de `mcp_config.json` o en tu entorno de sistema.

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
