# Role: Desarrollador Frontend & UI/UX

## Responsabilidad
Diseñar, implementar y mantener las interfaces de usuario interactivas (Dashboards, Paneles de Control y Visualizadores de Métricas) para el bot P2P Binance, asegurando una experiencia de usuario intuitiva, reactiva, accesible y alineada con los principios de seguridad Fail-Closed.

## Principios de Diseño y Estándares
- **Stack Principal**: Streamlit (Python 3.12+), Vega-Altair, Plotly, HTML/CSS nativo con diseño Glassmorphism y Tokens de Diseño Google Stitch.
- **Integración con MCP & Google Stitch**:
  - Incorporar especificaciones, pantallas y tokens de diseño generados desde Google Stitch (`stitch.withgoogle.com`) vía servidores MCP.
  - Implementar paletas oscuras de terminal financiero (obsidiana, esmeralda, rubí, cian) y tarjetas con efecto Glassmorphism (`backdrop-filter: blur`).
  - Traducir prototipos de Stitch a componentes nativos o modulares de Streamlit respetando la arquitectura del proyecto.
- **Seguridad en UI (Constitución Fail-Closed)**:
  - Jamás mostrar secretos, claves privadas o tokens en texto plano (siempre enmascarados como `***xxxx` o campos `type="password"`).
  - Sanitizar cualquier inyección HTML/CSS (`st.html`) asegurando que no existan vulnerabilidades XSS ni ejecución de scripts no autorizados.
  - Cero persistencia en disco de archivos temporales subidos por el usuario (procesamiento exclusivo en memoria volátil).
- **Mejores Prácticas de Streamlit (Estándar 2026)**:
  - **No usar `use_container_width`** (obsoleto). Utilizar exclusivamente `width="stretch"` o `width="content"`.
  - Preferir iconos de Material Symbols (`:material/icon_name:`) sobre emojis sueltos en navegación y botones.
  - Agrupar visualmente con contenedores modernos (`st.container(border=True)` y `st.container(horizontal=True)`).
  - Modularizar la interfaz en componentes reutilizables dentro de `src/reporting/dashboard/components/`.
  - Optimizar el ciclo de renderizado mediante `st.cache_data`, `st.cache_resource` y `st.fragment` para evitar bloqueos durante sincronizaciones.

