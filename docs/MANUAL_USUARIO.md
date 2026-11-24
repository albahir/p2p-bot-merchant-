# Manual de Uso — Comerciante P2P

Guía rápida de referencia: **qué hace cada módulo** y **en qué orden usarlo** en el día a día y al cierre de cada mes.

---

## 1. Mapa Rápido de Módulos

| Sección | Ruta | ¿Para qué sirve? |
|---|---|---|
| **Matriz** | `/` | Ver tasas Binance P2P vs BCV en vivo, brecha y las mejores rutas de arbitraje según **Mis bancos** o **Todos**. |
| **Velas P2P** | `/market` | Analizar tendencia histórica (velas, medias móviles, fuerza RSI, profundidad por monto y brecha BCV). |
| **Calculadora** | `/calculator` | Simular un ciclo de compra/venta antes de operar: capital necesario, punto de equilibrio, comisiones y ganancia neta. |
| **Órdenes** | `/orders` | Consultar y sincronizar tus compras y ventas completadas de Binance P2P (fuente oficial para la contabilidad). |
| **Contabilidad** | `/accounting` | Controlar saldos por banco y USDT, conciliar pagos (OCR, PDF/Excel bancario o manual), cerrar el mes y exportar reportes SENIAT. |
| **Google Sheets** | `/sheets` | Sincronizar tus movimientos y expediente de respaldo con tu hoja personal de Google Sheets. |
| **Configuración** | `/settings` | Conectar tu API Key de Binance (solo *Lectura* + *P2P*), verificar correo/Cédula/RIF, pregunta secreta y llave maestra. |

---

## 2. Primer Uso (Configuración Inicial — Solo 1 vez)

1. **Crea tu cuenta (`/register`):**
   - **Paso 1:** Nombre, correo (pulsa **Verificar correo** para validar el código SMTP) y Cédula/RIF (aparecerá en tus reportes fiscales).
   - **Paso 2:** ID de Telegram (pídelo al bot con `/id`), contraseña segura y pregunta secreta. **Guarda tu Llave Maestra** al finalizar.
   - **Paso 3:** Selecciona los bancos con los que operas y (opcional) tu Google Sheet.
2. **Conecta Binance (`/settings`):**
   - Agrega tu API Key y Secret Key con permisos mínimos (**Lectura + P2P**, nunca retiros) y restricción de IP.

---

## 3. Rutina Diaria (Antes y Después de Operar)

1. **Detecta oportunidad (`/` Matriz):**
   - Activa **Mis bancos** para ver solo rutas donde tienes cuenta activa, o cambia a **Todos** para ver el mercado completo.
2. **Valida tendencia (`/market` Velas P2P):**
   - Revisa la temporalidad (`5m`, `15m`, `1h`), tu banco y el monto en Bs que planeas mover.
   - Si quieres una lectura en vivo inmediata de Binance, pulsa **Capturar ahora**.
3. **Simula antes de publicar (`/calculator`):**
   - Coloca tu capital en USDT, banco de compra y banco de venta.
   - Revisa la **Tasa Equilibrio**: si tu tasa de venta queda por debajo, verás la alerta de pérdida y el botón para ajustarla.
4. **Registra tus pagos (`/accounting`):**
   - Sube capturas de Pago Móvil/transferencias (**OCR**), importa tu **estado de cuenta bancario** (PDF/Excel/CSV) o usa el **registro manual rápido** (`Alt+N`).

---

## 4. Flujo Contable Mensual (`/accounting`)

El sistema detecta automáticamente si elegiste un **Mes Pasado (Auditoría Histórica)** o el **Mes en Curso (En vivo)** y muestra una barra de 4 pasos:
`1. Apertura (Bs + USDT)` → `2. Órdenes y Pagos` → `3. Arqueo Final Real` → `4. Cerrar y Descargar`

### A. Mes 1 o Mes Pasado (ej. Octubre)
1. **Selecciona Mes y Año** arriba en `/accounting`.
2. **Sincroniza ese mes:** pulsa el botón **`Sincronizar <Mes>`** en la barra superior (descarga solo ese mes en hora VET y asigna la **tasa BCV histórica** de cada día). Si el mes supera el límite histórico de Binance API, sube el Excel/CSV de órdenes en `/orders`.
3. **Ingresa tus Saldos Iniciales (aislados a ese mes):**
   - En **Saldo total en mis bancos (VES)** → pulsa **Mis bancos** → escribe cuánto tenías el día 1 en cada banco.
   - En **Saldo USDT** → escribe en **Inicial USDT** cuántos USDT tenías en Binance el día 1 (el sistema estima automáticamente su costo inicial con la tasa BCV del día 1).
   - *Los saldos de cada mes se guardan de forma independiente: editar Octubre nunca sobrescribe Noviembre.*
4. **Concilia tus movimientos bancarios:**
   - Sube tu **estado de cuenta** (PDF/Excel/CSV), **capturas OCR** o registra pagos manuales (`Alt+N`) para empatar cada orden P2P con su referencia bancaria y deducir comisiones bancarias (0,30%).

### B. Arqueo Final Real, Cierre y Descargas
1. Revisa las **3 pestañas** de `/accounting`:
   - **Libro Diario:** Asientos en partida doble (`Debe = Haber`) en hora legal de Venezuela (VET).
   - **Libro Mayor:** Total acumulado por cuenta (con saldos iniciales reales).
   - **Ecuación Fiscal (6 Piezas):** Resumen del mes y **Utilidad Neta Fiscal (VES)** por método **PEPS (FIFO)**.
2. **Arqueo y Cierre:**
   - Pulsa **Cerrar mes**, escribe tu **Saldo Final Real** en Binance (USDT) y en cada banco (Bs).
   - Verifica el semáforo **✓ Cuadrado** o **Diferencia (Real − Teórico)** y escribe `CERRAR-MES` para sellar.
3. **Descarga tus soportes legales:**
   - **Excel (`.xlsx` — 7 pestañas):** *Libro Diario*, *Libro Mayor*, *Estado de Resultados*, *Balance General (VEN-NIF 12)*, *Kardex Inventario USDT*, *Conciliación Bancaria* y *Liquidación Fiscal SENIAT*.
   - **PDF (`.pdf` — multipágina):** Estado de Resultados PEPS, Estado de Situación Financiera (BA VEN-NIF 12), Kardex USDT con arqueo real, Libro Mayor, Libro Diario completo con Sumas Iguales y Conciliación/IGTF.

### C. Mes 2 en adelante (Arrastre automático)
- Al cambiar al mes siguiente, el sistema **hereda automáticamente** tu **Saldo Final Real** del mes anterior como **Saldo Inicial** del nuevo mes.

---

## 5. Recuperación de Cuenta y Comandos de Telegram

### Si olvidaste tu contraseña (`/login`)
- Pulsa **¿Olvidaste tu contraseña?**, escribe tu alias, correo o Telegram ID.
- El sistema mostrará tu **método principal** (por defecto código OTP de 6 dígitos al correo).
- Si prefieres otro canal, pulsa **Probar otra manera** para cambiar entre **OTP Correo**, **OTP Telegram**, **Pregunta Secreta** o **Llave Maestra**.

### Comandos útiles en el Bot de Telegram
| Comando | Qué hace |
|---|---|
| `/id` | Muestra tu Telegram ID numérico (requerido al registrarte). |
| `/otp` | Genera/consulta tu código temporal de recuperación. |
| `/spread` | Muestra las mejores tasas y oportunidades de arbitraje actuales. |
| `/prediccion` | Consulta el pronóstico de tendencia USDT/VES. |
| `/cierre_mensual` | Genera y envía tu cierre fiscal mensual en `.xlsx` directo al chat. |
| `/sheets_compliance` | Sincroniza el expediente de soporte bancario en Google Sheets. |
