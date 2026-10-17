"""Dashboard y Panel de Control (Mission Control) para el Bot P2P Merchant.
Opera en modo seguro, sin requerir comandos de terminal para tareas operativas comunes.
"""

import pandas as pd
import streamlit as st

from src.data.database import SessionLocal
from src.data.models import Order, SecurityEvent
from src.data.repositories import OrderRepository
from src.reporting.dashboard.components.control_actions import render_control_actions
from src.reporting.dashboard.components.credential_manager import render_credential_manager
from src.reporting.dashboard.components.kpi_cards import render_kpis
from src.reporting.dashboard.components.test_runner_view import render_test_runner
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod

st.set_page_config(
    page_title="P2P Merchant Bot — Mission Control",
    page_icon=":material/smart_toy:",
    layout="wide"
)

st.title(":material/smart_toy: P2P Merchant Bot — Panel de Control")

# Pestañas de navegación de la interfaz
tab_control, tab_credentials, tab_overview, tab_tax, tab_tests, tab_security = st.tabs([
    "🕹️ Panel de Tareas",
    "🔑 Credenciales",
    "📊 Visión General",
    "📑 Motor Fiscal (ISLR)",
    "🧪 Suite de Tests",
    "🛡️ Auditoría"
])

# 1. Panel de Tareas (Acciones directas sin consola)
with tab_control:
    render_control_actions()

# 2. Gestor de Credenciales Cifradas
with tab_credentials:
    render_credential_manager()

# 3. Visión General de Órdenes y KPIs
with tab_overview:
    st.subheader(":material/monitoring: Métricas Operativas")
    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        completed_orders = repo.list_completed()
        all_orders = db.query(Order).order_by(Order.id.desc()).limit(100).all()

        if not all_orders:
            st.info("No hay órdenes registradas en el sistema. Ejecuta una sincronización o simulación desde el Panel de Tareas.")
        else:
            if completed_orders:
                total_vol = sum(o.fiat_amount for o in completed_orders)
                fifo_engine = FIFOCostMethod()
                results = fifo_engine.process_orders(completed_orders)
                profit_ves = sum(r.net_profit_fiat for r in results)
                profit_usd = sum(r.net_profit_usd for r in results)

                render_kpis(len(completed_orders), total_vol, profit_ves, profit_usd)
            else:
                st.warning("Hay órdenes registradas pero ninguna en estado COMPLETED.")

            st.write("---")
            st.markdown(f"#### Historial de Transacciones (Mostrando {len(all_orders)} más recientes)")
            data = [
                {
                    "ID": o.id,
                    "Orden": o.order_number,
                    "Tipo": o.trade_type,
                    "Estado": o.order_status,
                    "Activo": o.asset,
                    "Monto Fíat (VES)": f"{o.fiat_amount:,.2f}",
                    "Monto Cripto": f"{o.crypto_amount:,.2f}",
                    "Precio Unitario": f"{o.unit_price:,.4f}",
                    "Comisión (VES)": f"{o.fee_fiat:,.2f}",
                    "Tasa BCV": f"{o.bcv_rate:,.2f}",
                    "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M")
                }
                for o in all_orders
            ]
            st.dataframe(pd.DataFrame(data), width="stretch")
    finally:
        db.close()

# 4. Motor Fiscal con Descarga Directa
with tab_tax:
    st.subheader(":material/calculate: Cálculo y Declaración Fiscal")
    method_choice = st.segmented_control("Método Contable:", ["FIFO", "Costo Promedio Ponderado"], default="FIFO")

    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        orders = repo.list_completed()
        if not orders:
            st.info("No hay órdenes completadas para calcular impuestos.")
        else:
            engine = FIFOCostMethod() if method_choice == "FIFO" else WeightedAverageCostMethod()
            tax_results = engine.process_orders(orders)

            if not tax_results:
                st.info("No se han registrado ventas (SELL) aún para liquidar inventario.")
            else:
                tax_data = [
                    {
                        "Orden Venta": r.order_number,
                        "Cripto Vendida": f"{r.crypto_amount:,.2f} USDT",
                        "Ingreso Bruto (VES)": f"{r.total_revenue_fiat:,.2f} Bs.",
                        "Costo Adquisición (VES)": f"{r.acquisition_cost_fiat:,.2f} Bs.",
                        "Comisión (VES)": f"{r.fee_fiat:,.2f} Bs.",
                        "Ganancia Neta (VES)": f"{r.net_profit_fiat:,.2f} Bs.",
                        "Tasa BCV Oficial": f"{r.bcv_rate:,.2f}",
                        "Ganancia Neta (USD)": f"${r.net_profit_usd:,.2f}"
                    }
                    for r in tax_results
                ]
                st.dataframe(pd.DataFrame(tax_data), width="stretch")

                # Botón de Descarga Excel
                report_file = "reporte_fiscal_p2p.xlsx"
                ExcelReporter.generate_tax_report(tax_results, report_file)
                with open(report_file, "rb") as f:
                    st.download_button(
                        label="📥 Descargar Reporte Fiscal en Excel (.xlsx)",
                        data=f.read(),
                        file_name="reporte_fiscal_p2p.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch"
                    )

                # Sincronización con Google Sheets
                st.write("---")
                st.markdown("#### :material/table_chart: Sincronización con Google Sheets")
                from config.settings import Settings
                from src.reporting.sheets_exporter import SheetsExporter

                try:
                    dashboard_settings = Settings()
                    sheet_id = dashboard_settings.GOOGLE_SHEET_ID
                    if sheet_id:
                        sheet_url = SheetsExporter.get_sheet_url(sheet_id)
                        st.markdown(f"🔗 **Documento vinculado**: [{sheet_id}]({sheet_url})")
                        if st.button("📊 Sincronizar Ahora con Google Sheets", use_container_width=True):
                            exporter = SheetsExporter(
                                credentials_path=dashboard_settings.GOOGLE_CREDENTIALS_FILE,
                                credentials_json=dashboard_settings.GOOGLE_SERVICE_ACCOUNT_JSON,
                            )
                            if exporter.export(sheet_id, tax_results):
                                st.success(f"¡Sincronizado exitosamente! [Abrir Google Sheets]({sheet_url})")
                            else:
                                st.error("Error al sincronizar con Google Sheets. Revisa credenciales o permisos.")
                    else:
                        st.info("💡 Para activar la sincronización con Google Sheets, define `GOOGLE_SHEET_ID` en `config/.env` o variables de entorno.")
                except (ValueError, KeyError, OSError, RuntimeError) as ex:
                    st.warning(f"Configuración de Google Sheets no disponible: {ex}")
    finally:
        db.close()

# 5. Suite de Tests Automatizados
with tab_tests:
    render_test_runner()

# 6. Auditoría de Seguridad (SHA-256)
with tab_security:
    st.subheader(":material/security: Eventos de Auditoría (Append-Only SHA-256)")
    db = SessionLocal()
    try:
        events = db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(100).all()
        if not events:
            st.info("No se han registrado eventos de seguridad aún.")
        else:
            events_data = [
                {
                    "ID": e.id,
                    "Timestamp (UTC)": e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo de Evento": e.event_type,
                    "Identificador": e.key_identifier,
                    "IP": e.ip_address,
                    "Estado": e.status,
                    "Hash Evento": e.event_hash[:16] + "..."
                }
                for e in events
            ]
            st.dataframe(pd.DataFrame(events_data), width="stretch")
    finally:
        db.close()
