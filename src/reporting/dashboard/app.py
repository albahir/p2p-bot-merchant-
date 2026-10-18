"""Dashboard y Panel de Control (Mission Control) para el Bot P2P Merchant.
Opera en modo seguro, sin requerir comandos de terminal para tareas operativas comunes.
"""

import pandas as pd
import streamlit as st

from src.core.spread_monitor import SpreadMonitor
from src.data.database import SessionLocal
from src.data.models import Order, SecurityEvent
from src.data.repositories import OrderRepository
from src.reporting.dashboard.components.ai_telemetry import render_ai_telemetry
from src.reporting.dashboard.components.arbitrage_matrix import (
    render_arbitrage_matrix,
    render_maker_calculator,
)
from src.reporting.dashboard.components.control_actions import render_control_actions
from src.reporting.dashboard.components.credential_manager import render_credential_manager
from src.reporting.dashboard.components.fiscal_reconstruction_view import (
    render_fiscal_reconstruction,
)
from src.reporting.dashboard.components.kpi_cards import render_fintech_kpis
from src.reporting.dashboard.components.receipt_center import render_receipt_center
from src.reporting.dashboard.components.terminal_header import render_terminal_header
from src.reporting.dashboard.components.test_runner_view import render_test_runner
from src.reporting.dashboard.theme import apply_stitch_theme
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod

st.set_page_config(
    page_title="P2P Merchant Bot — Terminal & Mission Control",
    page_icon=":material/terminal:",
    layout="wide",
)

# Inyectar estilos Stitch Glassmorphism
apply_stitch_theme(st)

st.title(":material/terminal: P2P Merchant Bot — Terminal Operativa")

# Barra Superior de Telemetría
render_terminal_header(
    bot_mode="PRODUCTION",
    ip_address="Auto-detect",
    api_weight=120,
    fail_closed=True,
    st_module=st,
)

# Pestañas de navegación de la interfaz
tab_overview, tab_spread, tab_receipts, tab_reconcile, tab_tax, tab_control, tab_ai, tab_credentials, tab_tests, tab_security = st.tabs([
    "📊 Visión General",
    "📈 Monitor & Arbitraje P2P",
    "🧾 Comprobantes OCR",
    "⚖️ Reconstrucción 6 Piezas",
    "📑 Motor Fiscal (ISLR)",
    "🕹️ Panel de Tareas",
    "🤖 Telemetría IA",
    "🔑 Credenciales",
    "🧪 Suite de Tests",
    "🛡️ Auditoría",
])


# 1. Visión General de Órdenes y KPIs
with tab_overview:
    st.subheader(":material/monitoring: Métricas Operativas de la Terminal")
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

                from src.data.models import BankVoucher
                vouchers = db.query(BankVoucher).all()
                tot_v = len(vouchers)
                mat_v = sum(1 for v in vouchers if v.verification_status == "MATCHED")
                ratio_str = f"{mat_v}/{tot_v}" if tot_v > 0 else "0/0"

                render_fintech_kpis(
                    orders_count=len(completed_orders),
                    volume_ves=total_vol,
                    net_profit_ves=profit_ves,
                    net_profit_usd=profit_usd,
                    vouchers_ratio=ratio_str,
                    bcv_spread="+4.5%",
                    st_module=st,
                )
            else:
                st.warning("Hay órdenes registradas pero ninguna en estado COMPLETED.")

            st.write("---")
            st.markdown(f"#### Historial de Transacciones (Mostrando {len(all_orders)} más recientes)")
            data = [
                {
                    "ID": o.id,
                    "Orden": o.order_number,
                    "Tipo": o.trade_type,
                    "Contraparte": o.counterparty_name or "-",
                    "Estado": o.order_status,
                    "Activo": o.asset,
                    "Monto Fíat (VES)": f"{o.fiat_amount:,.2f}",
                    "Monto Cripto": f"{o.crypto_amount:,.2f}",
                    "Precio Unitario": f"{o.unit_price:,.4f}",
                    "Comisión (VES)": f"{o.fee_fiat:,.2f}",
                    "Tasa BCV": f"{o.bcv_rate:,.2f}",
                    "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for o in all_orders
            ]
            st.dataframe(pd.DataFrame(data), width="stretch")
    finally:
        db.close()

# 2. Monitor de Spreads Bancarios y Calculadora Maker
with tab_spread:
    monitor = SpreadMonitor()
    market_quotes = monitor.get_market_quotes()
    bcv_rate = 820.0
    db = SessionLocal()
    try:
        from typing import Any, cast
        latest_order = db.query(Order).filter(cast(Any, Order.bcv_rate > 0)).order_by(Order.id.desc()).first()
        if latest_order and latest_order.bcv_rate:
            bcv_rate = float(latest_order.bcv_rate)
    finally:
        db.close()

    p2p_ref = market_quotes[0].buy_rate if market_quotes else 0.0
    bcv_gap = monitor.calculate_bcv_gap(p2p_price=p2p_ref, bcv_rate=bcv_rate)

    render_arbitrage_matrix(quotes=market_quotes, bcv_rate=bcv_rate, bcv_gap_pct=bcv_gap, st_module=st)
    st.divider()
    render_maker_calculator(st_module=st)

# 3. Centro de Comprobantes Bancarios OCR
with tab_receipts:
    db = SessionLocal()
    try:
        render_receipt_center(db=db)
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

                # Botones de Descarga Excel (Fiscal y Compliance Bancario)
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    report_file = "reporte_fiscal_p2p.xlsx"
                    ExcelReporter.generate_tax_report(tax_results, report_file)
                    with open(report_file, "rb") as f:
                        st.download_button(
                            label="📥 Descargar Reporte Fiscal (.xlsx)",
                            data=f.read(),
                            file_name="reporte_fiscal_p2p.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch"
                        )

                with col_dl2:
                    from src.data.models import BankVoucher
                    all_vouchers = db.query(BankVoucher).all()
                    compliance_file = "certificacion_origen_fondos.xlsx"
                    ExcelReporter.generate_compliance_report(
                        orders=orders,
                        vouchers=all_vouchers,
                        account_holder="COMERCIANTE P2P REGISTRADO",
                        rif="V-00000000-0",
                        period="Período Actual",
                        output_path=compliance_file,
                    )
                    with open(compliance_file, "rb") as cf:
                        st.download_button(
                            label="🏛️ Descargar Certificación Bancaria / Compliance (.xlsx)",
                            data=cf.read(),
                            file_name="certificacion_origen_fondos_p2p.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch",
                            help="Genera el informe institucional para prevención de bloqueos bancarios en Venezuela.",
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
                        if st.button("📊 Sincronizar Ahora con Google Sheets", width="stretch"):
                            exporter = SheetsExporter(
                                credentials_path=dashboard_settings.GOOGLE_CREDENTIALS_FILE,
                                credentials_json=dashboard_settings.GOOGLE_SERVICE_ACCOUNT_JSON,
                            )
                            if exporter.export(sheet_id, tax_results):
                                st.success(f"¡Sincronizado exitosamente! [Abrir Google Sheets]({sheet_url})")
                            else:
                                err_msg = exporter.last_error or "Revisa credenciales o permisos de la hoja."
                                st.error(f"Error al sincronizar con Google Sheets: {err_msg}")
                    else:
                        st.info("💡 Para activar la sincronización con Google Sheets, define `GOOGLE_SHEET_ID` en `config/.env` o variables de entorno.")
                except (ValueError, KeyError, OSError, RuntimeError) as ex:
                    st.warning(f"Configuración de Google Sheets no disponible: {ex}")
    finally:
        db.close()

# 3. Reconstrucción Contable de 6 Piezas y Consistencia
with tab_reconcile:
    render_fiscal_reconstruction()

# 5. Panel de Control de Tareas Operativas
with tab_control:
    render_control_actions()

# 6. Telemetría del Pool de Claves de IA (Gemini Vision)
with tab_ai:
    render_ai_telemetry()

# 7. Gestor de Credenciales Cifradas
with tab_credentials:
    render_credential_manager()

# 8. Suite de Tests Automatizados
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
