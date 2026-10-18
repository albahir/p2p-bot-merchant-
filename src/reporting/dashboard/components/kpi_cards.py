"""Componentes de tarjetas KPI con diseño fintech y soporte para Streamlit moderno."""

from typing import Any


def render_fintech_kpis(
    orders_count: int,
    volume_ves: float,
    net_profit_ves: float,
    net_profit_usd: float,
    vouchers_ratio: str = "N/A",
    bcv_spread: str = "0.0%",
    st_module: Any = None,
) -> None:
    """Muestra tarjetas KPI estilizadas de terminal fintech."""
    try:
        import streamlit as st
        ui = st_module or st
    except (ImportError, RuntimeError):
        ui = st_module

    if ui is None:
        return

    with ui.container(border=True):
        c1, c2, c3, c4, c5, c6 = ui.columns(6)
        with c1:
            ui.metric(
                label="Órdenes P2P",
                value=f"{orders_count:,}",
                help="Total de órdenes completadas en el período activo",
            )
        with c2:
            ui.metric(
                label="Volumen Operado",
                value=f"{volume_ves:,.2f} VES",
                help="Volumen total transado en bolívares",
            )
        with c3:
            ui.metric(
                label="Ganancia Neta (VES)",
                value=f"{net_profit_ves:,.2f} VES",
                delta=f"{net_profit_ves:,.2f} Bs." if net_profit_ves != 0 else None,
                help="Utilidad neta gravable calculada bajo método FIFO",
            )
        with c4:
            ui.metric(
                label="Ganancia Neta (USD)",
                value=f"${net_profit_usd:,.2f}",
                delta=f"${net_profit_usd:,.2f}" if net_profit_usd != 0 else None,
                help="Margen equivalente en dólares estadounidenses",
            )
        with c5:
            ui.metric(
                label="Conciliación OCR",
                value=vouchers_ratio,
                help="Ratio de comprobantes bancarios vinculados a órdenes",
            )
        with c6:
            ui.metric(
                label="Brecha P2P vs BCV",
                value=bcv_spread,
                help="Spread promedio de cotización entre P2P y tasa oficial",
            )


def render_kpis(total_orders: int, total_volume_ves: float, net_profit_ves: float, net_profit_usd: float) -> None:
    """Función de compatibilidad histórica para dashboards existentes."""
    render_fintech_kpis(
        orders_count=total_orders,
        volume_ves=total_volume_ves,
        net_profit_ves=net_profit_ves,
        net_profit_usd=net_profit_usd,
    )
