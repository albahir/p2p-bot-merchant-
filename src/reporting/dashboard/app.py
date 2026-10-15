"""Dashboard de monitoreo operativo, fiscal y de seguridad con Streamlit.
Opera en modo solo lectura para garantizar que nunca bloquee el motor de trading.
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime
from src.data.database import SessionLocal
from src.data.models import Order, SecurityEvent
from src.data.repositories import OrderRepository
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.dashboard.components.kpi_cards import render_kpis

st.set_page_config(
    page_title="P2P Merchant Bot — Dashboard",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 P2P Bot Merchant Binance — Panel de Control")

# Pestañas principales
tab_overview, tab_tax, tab_security = st.tabs(["📊 Visión General", "📑 Motor Fiscal (ISLR)", "🛡️ Auditoría de Seguridad"])

db = SessionLocal()

with tab_overview:
    st.subheader("Métricas Operativas")
    repo = OrderRepository(db)
    orders = repo.list_completed()

    if not orders:
        st.info("No hay órdenes completadas registradas en el sistema.")
    else:
        total_vol = sum(o.fiat_amount for o in orders)
        fifo_engine = FIFOCostMethod()
        results = fifo_engine.process_orders(orders)
        profit_ves = sum(r.net_profit_fiat for r in results)
        profit_usd = sum(r.net_profit_usd for r in results)

        render_kpis(len(orders), total_vol, profit_ves, profit_usd)

        st.divider()
        st.write("### Historial de Transacciones Recientes")
        data = [
            {
                "Orden": o.order_number,
                "Tipo": o.trade_type,
                "Activo": o.asset,
                "Monto Fíat (VES)": o.fiat_amount,
                "Monto Cripto": o.crypto_amount,
                "Precio Unitario": o.unit_price,
                "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for o in reversed(orders[-50:])
        ]
        st.dataframe(pd.DataFrame(data), use_container_width=True)

with tab_tax:
    st.subheader("Cálculo y Declaración Fiscal")
    method_choice = st.radio("Método Contable:", ["FIFO", "Costo Promedio Ponderado"], horizontal=True)

    if orders:
        engine = FIFOCostMethod() if method_choice == "FIFO" else WeightedAverageCostMethod()
        tax_results = engine.process_orders(orders)

        tax_data = [
            {
                "Orden": r.order_number,
                "Cripto": r.crypto_amount,
                "Ingreso (VES)": r.total_revenue_fiat,
                "Costo Adquisición (VES)": r.acquisition_cost_fiat,
                "Comisión (VES)": r.fee_fiat,
                "Ganancia Neta (VES)": r.net_profit_fiat,
                "Tasa BCV": r.bcv_rate,
                "Ganancia (USD)": r.net_profit_usd
            }
            for r in tax_results
        ]
        st.dataframe(pd.DataFrame(tax_data), use_container_width=True)

        if st.button("📥 Generar y Descargar Reporte Excel"):
            report_file = "reporte_fiscal_p2p.xlsx"
            ExcelReporter.generate_tax_report(tax_results, report_file)
            with open(report_file, "rb") as f:
                st.download_button(
                    label="Haga clic aquí para descargar el archivo Excel",
                    data=f.read(),
                    file_name="reporte_fiscal_p2p.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

with tab_security:
    st.subheader("Eventos de Auditoría (Append-Only SHA-256)")
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
        st.dataframe(pd.DataFrame(events_data), use_container_width=True)

db.close()
