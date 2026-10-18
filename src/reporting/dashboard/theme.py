"""Motor de temas y tokens de diseño Stitch (Obsidian Fintech) para el Dashboard.
Implementa estética Glassmorphism, paleta oscura de alta precisión y badges semánticos.
"""

import html
from typing import Any

STITCH_TOKENS: dict[str, str] = {
    "bg_dark": "#0B0E14",
    "surface": "#161B22",
    "surface_glass": "rgba(22, 27, 34, 0.75)",
    "border_subtle": "rgba(255, 255, 255, 0.08)",
    "border_highlight": "rgba(255, 255, 255, 0.18)",
    "emerald": "#10B981",
    "emerald_glow": "rgba(16, 185, 129, 0.15)",
    "ruby": "#F43F5E",
    "ruby_glow": "rgba(244, 63, 94, 0.15)",
    "cyan": "#06B6D4",
    "cyan_glow": "rgba(6, 182, 212, 0.15)",
    "amber": "#F59E0B",
    "amber_glow": "rgba(245, 158, 11, 0.15)",
    "text_primary": "#F0F6FC",
    "text_secondary": "#8B949E",
    "text_muted": "#6E7681",
}


def get_stitch_css() -> str:
    """Retorna el bloque CSS de diseño Glassmorphism y tokens de Stitch."""
    return f"""
    <style>
    /* Estructura base y fondo Obsidian */
    .stApp {{
        background-color: {STITCH_TOKENS["bg_dark"]};
        color: {STITCH_TOKENS["text_primary"]};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    /* Tarjetas Glassmorphism Fintech */
    .fintech-card {{
        background: {STITCH_TOKENS["surface_glass"]};
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid {STITCH_TOKENS["border_subtle"]};
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s ease-in-out, transform 0.2s ease-in-out;
    }}
    .fintech-card:hover {{
        border-color: {STITCH_TOKENS["border_highlight"]};
    }}

    /* Barra Superior de Terminal */
    .terminal-header {{
        background: {STITCH_TOKENS["surface_glass"]};
        backdrop-filter: blur(16px);
        border: 1px solid {STITCH_TOKENS["border_subtle"]};
        border-radius: 12px;
        padding: 0.85rem 1.25rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    /* Números de alta precisión / Tabular Nums */
    .stat-num {{
        font-variant-numeric: tabular-nums;
        font-family: "JetBrains Mono", "SF Mono", Consolas, Menlo, monospace;
        letter-spacing: -0.02em;
        font-weight: 600;
    }}

    /* Badges Semánticos */
    .badge-pill {{
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .badge-success, .badge-matched {{
        background: {STITCH_TOKENS["emerald_glow"]};
        color: {STITCH_TOKENS["emerald"]};
        border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    .badge-danger, .badge-discrepancy {{
        background: {STITCH_TOKENS["ruby_glow"]};
        color: {STITCH_TOKENS["ruby"]};
        border: 1px solid rgba(244, 63, 94, 0.3);
    }}
    .badge-warning, .badge-unmatched {{
        background: {STITCH_TOKENS["amber_glow"]};
        color: {STITCH_TOKENS["amber"]};
        border: 1px solid rgba(245, 158, 11, 0.3);
    }}
    .badge-info {{
        background: {STITCH_TOKENS["cyan_glow"]};
        color: {STITCH_TOKENS["cyan"]};
        border: 1px solid rgba(6, 182, 212, 0.3);
    }}

    /* Ajuste de métricas nativas de Streamlit */
    [data-testid="stMetricValue"] {{
        font-family: "JetBrains Mono", Consolas, monospace !important;
        font-size: 1.6rem !important;
        color: {STITCH_TOKENS["text_primary"]} !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {STITCH_TOKENS["text_secondary"]} !important;
        font-weight: 500 !important;
    }}

    /* Tablas estilizadas */
    [data-testid="stDataFrame"] {{
        border: 1px solid {STITCH_TOKENS["border_subtle"]};
        border-radius: 8px;
        overflow: hidden;
    }}
    </style>
    """


def render_status_badge(label: str, variant: str = "info") -> str:
    """Genera HTML sanitizado para un badge con estilo Stitch."""
    clean_label = html.escape(str(label).strip())
    clean_variant = html.escape(str(variant).strip().lower())
    return f'<span class="badge-pill badge-{clean_variant}">{clean_label}</span>'


def apply_stitch_theme(st_module: Any = None) -> None:
    """Inyecta los estilos de Stitch en la aplicación Streamlit."""
    try:
        import streamlit as st
        target = st_module or st
        target.markdown(get_stitch_css(), unsafe_allow_html=True)
    except (ImportError, RuntimeError, AttributeError):
        pass
