"""Tests unitarios (TDD) para los componentes modulares de la Terminal P2P (SPEC-013)."""

from unittest.mock import MagicMock

from src.reporting.dashboard.components.ai_telemetry import render_ai_telemetry
from src.reporting.dashboard.components.kpi_cards import render_fintech_kpis
from src.reporting.dashboard.components.terminal_header import render_terminal_header


def test_render_terminal_header_mock():
    mock_st = MagicMock()
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    render_terminal_header(
        bot_mode="PRODUCTION",
        ip_address="198.51.100.25",
        api_weight=240,
        fail_closed=True,
        st_module=mock_st,
    )
    assert mock_st.columns.called


def test_render_fintech_kpis_mock():
    mock_st = MagicMock()
    mock_st.columns.return_value = [MagicMock() for _ in range(6)]
    render_fintech_kpis(
        orders_count=45,
        volume_ves=1250000.50,
        net_profit_ves=38500.00,
        net_profit_usd=820.50,
        vouchers_ratio="12/12 (100%)",
        bcv_spread="+4.2%",
        st_module=mock_st,
    )
    assert mock_st.columns.called



def test_render_ai_telemetry_mock():
    mock_st = MagicMock()
    sample_pool = {
        "total_keys": 3,
        "active_index": 0,
        "keys": [
            {"slot": 1, "masked": "AIzaSy...7GBE", "status": "ACTIVE", "calls": 15},
            {"slot": 2, "masked": "AIzaSy...4QWE", "status": "ACTIVE", "calls": 14},
            {"slot": 3, "masked": "AIzaSy...9XYZ", "status": "ACTIVE", "calls": 12},
        ],
    }
    render_ai_telemetry(pool_state=sample_pool, st_module=mock_st)
    assert mock_st.markdown.called or mock_st.columns.called


def test_render_receipt_center_mock():
    from src.reporting.dashboard.components.receipt_center import render_receipt_center

    mock_st = MagicMock()
    mock_st.file_uploader.return_value = None
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

    render_receipt_center(db=mock_db, st_module=mock_st)
    assert mock_st.subheader.called or mock_st.markdown.called


def test_render_binance_p2p_book_mock():
    """Valida la ejecución de render_binance_p2p_book con cliente simulado y filtros."""
    from src.core.binance_mock import MockBinanceP2PClient
    from src.reporting.dashboard.components.binance_p2p_book import render_binance_p2p_book

    mock_st = MagicMock()
    mock_st.segmented_control.return_value = "Comprar USDT"
    mock_st.selectbox.side_effect = ["VES", "USDT", "Banco de Venezuela"]
    mock_st.number_input.return_value = 1000.0
    mock_st.toggle.return_value = False
    mock_st.button.return_value = False
    mock_st.columns.side_effect = lambda spec, **kwargs: [MagicMock() for _ in (spec if isinstance(spec, list) else range(spec))]

    mock_client = MockBinanceP2PClient()
    render_binance_p2p_book(st_module=mock_st, client=mock_client, use_sandbox=True)

    assert mock_st.subheader.called
    assert mock_st.segmented_control.called
    assert mock_st.selectbox.called



