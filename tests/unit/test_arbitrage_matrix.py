"""Tests unitarios para el componente visual Arbitrage Matrix y Monitor de Spreads (SPEC-013 Fase 4)."""

from unittest.mock import MagicMock

from src.core.spread_monitor import BankRateQuote
from src.reporting.dashboard.components.arbitrage_matrix import (
    render_arbitrage_matrix,
    render_maker_calculator,
)


def _mock_columns(n_or_spec):
    count = n_or_spec if isinstance(n_or_spec, int) else len(n_or_spec)
    return [MagicMock() for _ in range(count)]


def test_render_arbitrage_matrix_mock():
    mock_st = MagicMock()
    mock_st.columns.side_effect = _mock_columns
    quotes = [
        BankRateQuote(
            bank_name="Banco de Venezuela",
            buy_rate=845.00,
            sell_rate=855.00,
        ),
        BankRateQuote(
            bank_name="Bancamiga",
            buy_rate=848.00,
            sell_rate=850.00,
        ),
    ]

    render_arbitrage_matrix(
        quotes=quotes,
        bcv_rate=820.00,
        bcv_gap_pct=3.05,
        st_module=mock_st,
    )

    assert mock_st.container.called or mock_st.dataframe.called or mock_st.columns.called


def test_render_maker_calculator_mock():
    mock_st = MagicMock()
    mock_st.columns.side_effect = _mock_columns
    # Mock return values for inputs
    mock_st.number_input.side_effect = [500.0, 844.0, 854.0]
    mock_st.selectbox.return_value = "Usuario Normal (0.35%)"
    mock_st.checkbox.return_value = True

    render_maker_calculator(st_module=mock_st)

    assert mock_st.number_input.called
    assert mock_st.container.called or mock_st.markdown.called
