"""Componentes de tarjetas KPI para el dashboard Streamlit."""

import streamlit as st

def render_kpis(total_orders: int, total_volume_ves: float, net_profit_ves: float, net_profit_usd: float):
    """Muestra tarjetas con las principales métricas operativas."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Órdenes Completadas", total_orders)
    with c2:
        st.metric("Volumen (VES)", f"{total_volume_ves:,.2f} Bs.")
    with c3:
        st.metric("Ganancia Neta (VES)", f"{net_profit_ves:,.2f} Bs.")
    with c4:
        st.metric("Ganancia Neta (USD)", f"${net_profit_usd:,.2f}")
