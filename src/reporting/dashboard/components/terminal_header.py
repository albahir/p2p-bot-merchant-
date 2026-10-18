"""Componente modular de la barra superior de telemetría de la Terminal P2P."""

from datetime import UTC, datetime
from typing import Any

from src.reporting.dashboard.theme import render_status_badge


def render_terminal_header(
    bot_mode: str = "PRODUCTION",
    ip_address: str = "Desconocida",
    api_weight: int = 0,
    fail_closed: bool = True,
    st_module: Any = None,
) -> None:
    """Renderiza la barra de estado superior de la Terminal."""
    try:
        import streamlit as st
        ui = st_module or st
    except (ImportError, RuntimeError):
        ui = st_module

    if ui is None:
        return

    now_utc = datetime.now(UTC)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    mode_variant = "success" if bot_mode == "PRODUCTION" else "warning"
    fc_variant = "success" if fail_closed else "danger"

    weight_color = "emerald" if api_weight < 3000 else ("amber" if api_weight < 4500 else "ruby")

    with ui.container(border=True):
        c1, c2, c3, c4 = ui.columns([2, 2, 2, 2])
        with c1:
            ui.markdown(
                f"**Terminal P2P**: {render_status_badge(bot_mode, mode_variant)} "
                f"{render_status_badge('FAIL-CLOSED' if fail_closed else 'DEGRADED', fc_variant)}",
                unsafe_allow_html=True,
            )
        with c2:
            ui.markdown(
                f":material/public: **IP Saliente**: `{ip_address}`",
            )
        with c3:
            ui.markdown(
                f":material/speed: **API Weight**: `{api_weight}/5000` "
                f"<span style='color: var(--{weight_color}, #10B981); font-weight: 600;'>●</span>",
                unsafe_allow_html=True,
            )
        with c4:
            ui.markdown(
                f":material/schedule: **Reloj**: `{now_str}`",
            )
