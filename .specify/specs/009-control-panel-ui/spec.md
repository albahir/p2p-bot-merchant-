# Spec 009: Panel de Control y UI de Operaciones (Mission Control)

## QUÉ
Una interfaz gráfica interactiva centralizada construida con Streamlit que elimina la necesidad de ejecutar comandos en la terminal para operar el bot, gestionar credenciales, disparar sincronizaciones, evaluar la salud del sistema y generar reportes fiscales.

---

## 🌟 Lo que la Interfaz DEBE tener (Alcance y Funcionalidades)

### 1. Panel de Estado y Control del Motor (Bot Lifecycle)
- **RF-01**: Indicadores visuales de estado en tiempo real:
  - Estado del motor: 🟢 En ejecución / ⏸️ Pausado / 🔴 Detenido.
  - Estado de IP Whitelist: 🛡️ Verificada / ⚠️ Alerta.
  - Estado de base de datos y peso de API Binance (`x-mbx-used-weight`).
- **RF-02**: Botones de acción directa:
  - **Iniciar Motor**: Lanza el proceso del motor en segundo plano sin terminal.
  - **Pausar / Detener Motor**: Envía la señal de apagado limpio y auditado.
  - **Sincronizar Órdenes Ahora**: Dispara la ingesta inmediata de órdenes de Binance sin esperar el sondeo de 30s.

### 2. Gestor Visual de Credenciales Cifradas
- **RF-03**: Formulario seguro con campos ocultos (`type="password"`) para registrar y actualizar:
  - Binance API Key
  - Binance Private Key (Ed25519 PEM)
  - Telegram Bot Token y Chat ID
- **RF-04**: Las credenciales introducidas se cifran directamente en memoria con **AES-256-GCM** mediante `ApiKeyManager` antes de persistirse en la base de datos.
- **RF-05**: Estado de credenciales: Mostrar insignias (*badges*) tipo "Configurada / No configurada", sin exponer jamás el secreto.

### 3. Diagnóstico de Salud y Chequeo de Seguridad (Health Check)
- **RF-06**: Botón **"Diagnosticar Sistema"** que comprueba:
  - IP pública actual vs. Whitelist configurada.
  - Conexión a la base de datos local y lectura de modelos.
  - Antigüedad de credenciales (alertando si tienen más de 25 días).

### 4. Ejecución Visual de Pruebas Automatizadas
- **RF-07**: Botón **"Ejecutar Tests de Verificación"** que corre la suite `pytest` en segundo plano y muestra en pantalla:
  - Total de tests aprobados / fallidos.
  - Resumen visual de tests de seguridad, cliente Binance y motor fiscal.

### 5. Descarga de Reportes Fiscales y Auditoría
- **RF-08**: Selector interactivo de método contable (**FIFO** vs. **Costo Promedio Ponderado**).
- **RF-09**: Botón de generación y descarga inmediata del archivo Excel oficial (`.xlsx`) con las dos pestañas obligatorias (*Detalle* y *Resumen*).
- **RF-10**: Visor de los últimos 50 eventos de auditoría append-only con verificación de hashes SHA-256.

---

## 🚫 Lo que la Interfaz NO DEBE tener (Restricciones y Anti-patrones)

1. **Cero Texto Plano de Claves**: Jamás mostrar contraseñas, tokens de Telegram o claves privadas completas en la pantalla, ni siquiera tras guardarlas.
2. **Sin Consola Arbitraria de Comandos**: No proveer un campo de entrada para ejecutar comandos Bash/PowerShell arbitrarios (evita vulnerabilidades de ejecución remota de comandos - RCE).
3. **Sin Liberación de Órdenes Sin Verificación**: La UI no contendrá botones para marcar pagos como recibidos sin la confirmación de la pasarela o comprobación estricta (cumplimiento del principio constitucional 3).
4. **Sin Operaciones Bloqueantes en el Hilo Principal**: Procesos largos (como ejecución de tests o consultas pesadas a Binance) deben aislarse en hilos o usar estados de carga (`st.spinner`) para no congelar la navegación.

---

## Criterios de Aceptación
- [ ] La interfaz permite iniciar y detener el motor del bot mediante botones visuales.
- [ ] El guardado de credenciales cifra correctamente con AES-256-GCM y registra el evento en `security_events`.
- [ ] El botón de sincronización de órdenes actualiza la tabla de transacciones sin requerir comandos de consola.
- [ ] El reporte Excel se genera y descarga directamente desde el navegador.
- [ ] La suite de tests se puede ejecutar desde el panel mostrando resultados claros.
