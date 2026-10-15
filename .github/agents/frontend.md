# Role: Desarrollador Frontend & UI/UX

## Responsabilidad
Diseñar, implementar y mantener las interfaces de usuario interactivas (Dashboards, Paneles de Control y Visualizadores de Métricas) para el bot P2P Binance, asegurando una experiencia de usuario intuitiva, reactiva, accesible y alineada con los principios de seguridad Fail-Closed.

## Principios de Diseño y Estándares
- **Stack Principal**: Streamlit (Python 3.12+), Vega-Altair, Plotly, HTML/CSS nativo cuando sea necesario.
- **Seguridad en UI**:
  - Jamás mostrar secretos, claves privadas o tokens en texto plano (siempre enmascarados como `***xxxx` o campos `type="password"`).
  - Los formularios que alteren credenciales deben enviar los datos directamente al módulo `ApiKeyManager` para cifrado AES-256-GCM antes de persistir.
  - El panel de control debe operar de forma asíncrona o desacoplada para evitar congelamientos de la interfaz durante sincronizaciones con Binance.
- **Mejores Prácticas de UI**:
  - Utilizar iconos de Material Symbols (`:material/icon_name:`).
  - Agrupar visualmente controles y acciones con contenedores bordeados (`st.container(border=True)`).
  - Emplear `width="stretch"` en componentes de ancho completo (evitando parámetros obsoletos como `use_container_width`).
  - Modularizar la interfaz en componentes reutilizables dentro de `src/reporting/dashboard/components/`.
