# Plan 009: Panel de Control y UI de Operaciones (Mission Control)

## Stack Técnico
- **Framework UI**: Streamlit 1.35+
- **Librerías de Soporte**: `sqlalchemy`, `cryptography` (AES-256-GCM), `pandas`, `openpyxl`, `pytest`
- **Componentes**: `st.navigation`, `st.container(border=True)`, `st.form`, `st.status`, `st.download_button`

## Arquitectura de la Interfaz
La interfaz se organiza modularmente dentro de `src/reporting/dashboard/`:
- `app.py`: Punto de entrada principal con navegación por pestañas y estado global (`st.session_state`).
- `components/control_actions.py`: Botones para iniciar/pausar motor, sincronización manual y health-check.
- `components/credential_manager.py`: Formulario cifrado para API Keys y tokens con `ApiKeyManager`.
- `components/kpi_cards.py`: Tarjetas de resumen métrico y P&L.
- `components/test_runner_view.py`: Ejecutor interactivo de la suite de pruebas `pytest`.

```text
Streamlit Dashboard (src/reporting/dashboard/app.py)
   ├── 🕹️ Control del Motor      ---> Controla P2PBotEngine / Ingesta
   ├── 🔑 Credenciales Cifradas   ---> ApiKeyManager (AES-256-GCM)
   ├── 📊 Métricas & Órdenes      ---> OrderRepository & SQLite
   ├── 📑 Motor Fiscal           ---> TaxEngine & ExcelReporter (.xlsx)
   └── 🧪 Diagnóstico & Tests     ---> Health Check & Pytest Runner
```

## Decisiones de Arquitectura (ADRs)
1. **Streamlit Unificado**: Se extiende la aplicación existente de Streamlit en lugar de introducir un framework externo (como React o Vue) para evitar dependencias de Node.js, mantener una única base de código en Python 3.12 y garantizar acceso directo a los repositorios y servicios criptográficos.
2. **Control del Motor en Subproceso / Hilo Seguro**: Para permitir arrancar y detener el motor sin congelar la interfaz web, el estado de ejecución se coordina mediante banderas en base de datos o subprocesos controlados.
3. **Cifrado en Formulario**: Al presionar "Guardar Credenciales", la UI invoca directamente a `ApiKeyManager.store_secret`, asegurando que el secreto se cifre con AES-256-GCM antes de tocar la base de datos.

## Dependencias
- Paquete 001 (Seguridad y cifrado AES-256-GCM).
- Paquete 002 (Cliente Binance P2P e Ingesta).
- Paquete 005 (Motor Fiscal y Excel).
- Paquete 006 (Telegram Notifier).
