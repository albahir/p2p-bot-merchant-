# Especificación 012: Asistente de IA para Consultas Naturales en Telegram

## 1. Visión General y Propósito
Permitir que el comerciante P2P consulte el estado de su operación, métricas financieras, cálculos fiscales, análisis de spread y auditoría directamente desde su chat de Telegram utilizando lenguaje natural humano (ej. *"¿Cuánto gané hoy en USDT y VES?"*, *"¿A qué tasa cerró el BCV?"*, *"¿Cuál fue mi orden con mejor margen?"*).

La arquitectura implementa un modelo **Híbrido y Seguro con Function Calling (Tools)** que preserva los principios de la Constitución:
1. **Comandos Estructurados Deterministas**: `/status`, `/pause`, `/resume`, `/report` se ejecutan sin latencia ni consumo de tokens.
2. **Consultas en Lenguaje Natural**: Procesadas por un modelo de lenguaje (ej. Google Gemini 2.0 Flash o OpenAI) con llamadas a funciones controladas del repositorio local.
3. **Cero Secretos y Fail-Closed**: El LLM solo accede a resúmenes numéricos y estados de órdenes sanitizadas. Las herramientas son estrictamente de solo lectura (**Read-Only**); ninguna IA tiene capacidad de ejecutar transferencias ni modificar llaves privadas.

---

## 2. Requisitos Funcionales

### RF-012.1: Enrutamiento Inteligente de Mensajes
- Si el mensaje inicia con `/`, se despacha directamente al motor de comandos existente de Telegram.
- Si el mensaje es texto libre (lenguaje natural):
  - Si el usuario **no está autorizado** (`TELEGRAM_ALLOWED_USER_IDS`), se deniega el acceso de inmediato sin consultar al LLM.
  - Si el usuario está autorizado y `AI_API_KEY` está configurada, se procesa mediante el agente de IA.
  - Si `AI_API_KEY` no está configurada, se responde con un mensaje guiado invitando a configurarla o usar comandos directos.

### RF-012.2: Catálogo de Herramientas de Solo Lectura (Function Calling)
El agente de IA tendrá a su disposición las siguientes funciones locales para fundamentar sus respuestas en datos reales de la base de datos:
1. `obtener_metricas_fiscales(dias_atras: int, metodo: str)`: Retorna ganancia neta en VES y USD, volumen comercializado y margen porcentual según FIFO o Costo Promedio.
2. `consultar_ordenes_recientes(limite: int, tipo: str)`: Devuelve las últimas N transacciones con su precio unitario, criptoactivo y contraparte.
3. `consultar_tasa_bcv()`: Retorna la tasa oficial del Banco Central de Venezuela vigente.
4. `consultar_estado_sistema()`: Informa si el bot está en modo Sandbox o Producción, estado de la base de datos y consumo de peso de API de Binance.

### RF-012.3: Casos de Uso y Capacidades Conversacionales
- **Analista Financiero Personal**: Comparativa de rendimiento diario vs semanal y cálculo de ganancias netas.
- **Auditor Fiscal**: Explicación en lenguaje sencillo de por qué una venta tuvo determinado costo de adquisición según el método contable.
- **Radar de Arbitraje P2P**: Detección de spreads favorables en el histórico comercial.
- **Asistente de Soporte Operativo**: Explicación de estados de órdenes o alertas del sistema.

### RF-012.4: Seguridad y Sanitización Anti-Filtración
- Los prompts del sistema (*system instructions*) instruyen explícitamente a la IA a no revelar claves, contraseñas ni rutas internas del servidor.
- La salida de la IA pasa por `sanitize_message()` antes de enviarse al usuario de Telegram.

---

## 3. Criterios de Aceptación
- Las consultas en lenguaje natural responden con datos verídicos obtenidos de SQLite/PostgreSQL.
- Si la IA falla o la API externa no responde, el bot informa el error limpiamente sin bloquear el bucle de Telegram.
- Pruebas unitarias con mocks verificando el flujo completo de Function Calling sin llamadas reales a la red durante los tests de CI.
