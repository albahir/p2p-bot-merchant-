# SPEC-013: Mejoras de Producción — Google Sheets, Diagnóstico, VPS con IP Fija, Google Stitch y Monitor de Spread

## 1. Visión General y Objetivos
Esta especificación consolida las mejoras prioritarias requeridas para la operación comercial en producción del Bot P2P de Binance, abarcando desde la resiliencia en la nube y diagnóstico detallado de integraciones externas, hasta la infraestructura de IP estática y modernización de interfaces con IA.

---

## 2. Requisitos Funcionales

### RF-01: Diagnóstico Detallado y Recuperación de Google Sheets
- **Problema**: El comando `/sheets` y el Dashboard muestran mensajes genéricos cuando la exportación falla, impidiendo saber si falta el archivo de credenciales, si la cuenta de servicio no fue autorizada en Google Drive, o si las APIs no están habilitadas.
- **Requisito**:
  1. `SheetsExporter` debe exponer `last_error: str | None` y `client_email: str | None`.
  2. Detección precisa de causas:
     - Falta de credenciales (`GOOGLE_SERVICE_ACCOUNT_JSON` / `config/google_credentials.json`).
     - Error HTTP 403 (Permiso denegado): Informar el correo exacto de la cuenta de servicio al que se le debe dar rol de "Editor".
     - Error HTTP 404 (Hoja no encontrada): Verificar el `GOOGLE_SHEET_ID`.
     - Error de APIs no activadas en Google Cloud.
  3. Los mensajes de Telegram y del Dashboard deben presentar el diagnóstico exacto y accionable.

### RF-02: Infraestructura VPS con IPv4 Estática Dedicada (Whitelist Binance)
- **Problema**: Render opera con un pool dinámico de IPs salientes compartidas. Binance exige la restricción obligatoria "Restrict access to trusted IPs only" para comercio P2P. Si la IP rota, Binance rechaza con `-2015: Invalid API-key, IP, or permissions`.
- **Requisito**:
  1. Diseñar y documentar la arquitectura de despliegue en VPS (Hetzner / DigitalOcean / AWS Lightsail / Oracle Cloud) con IPv4 pública fija y permanente.
  2. Script de aprovisionamiento automatizado en Bash (`scripts/deploy_vps.sh`) para levantar el stack productivo (`docker compose -f docker/docker-compose.yml up -d`).
  3. Soporte de proxy estático saliente (`BINANCE_PROXY_URL`) como puente opcional para entornos serverless.
  4. Auto-detección y reporte de la IP pública activa en las alertas de inicio del bot en Telegram.

### RF-03: Modernización de Interfaz con Google Stitch y MCP
- **Problema**: La interfaz básica de Streamlit carece de componentes visuales avanzados de terminal financiero.
- **Requisito**:
  1. Documentar y configurar la conexión al servidor MCP de Google Stitch (`stitch.withgoogle.com`).
  2. Diseñar la terminal P2P en Stitch e importar sus tokens visuales (Glassmorphism, paleta oscura, indicadores de spread, cards de métricas).
  3. Incorporar los estilos y componentes en el Dashboard de Streamlit o frontend desacoplado.

### RF-04: Monitor de Brecha Cambiaria (Spread BCV vs P2P en Tiempo Real)
- **Problema**: El comerciante necesita saber cuándo la cotización del mercado P2P se distancia de la tasa oficial del BCV para ajustar precios y maximizar márgenes.
- **Requisito**:
  1. Servicio de comparación en segundo plano que contraste el promedio de anuncios activos en Binance P2P contra la tasa viva de `bcv.org.ve`.
  2. Notificación proactiva a Telegram cuando el spread supere el umbral configurado (ej. > 5% o > 10%).

### RF-05: Cierre Fiscal Mensual Automatizado a Telegram
- **Problema**: La generación del reporte fiscal en Excel (.xlsx) requiere solicitud manual.
- **Requisito**:
  1. Tarea programada que el último día de cada mes a medianoche compile los resultados FIFO/Promedio Ponderado y despache el archivo `.xlsx` directamente al chat privado de Telegram del comerciante.

---

## 3. Principios de Seguridad y Reglas Innegociables
1. **Cero Secretos**: Ni tokens de Google, ni API Keys de Binance, ni IP privadas deben exponerse en logs, excepciones no controladas o mensajes de error públicos.
2. **Fail-Closed**: Ante fallos de conexión con Google Sheets o Binance, el bot no detiene la persistencia local en SQLite/PostgreSQL ni corrompe el historial contable.
3. **100% Cobertura de Pruebas**: Nuevos módulos y correcciones deben contar con pruebas unitarias con mocks de red y validación en CI.
