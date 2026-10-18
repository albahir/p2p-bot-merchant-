"""Componente visual de Matriz de Arbitraje Bancario y Calculadora de Rentabilidad Maker.
Diseñado para la Terminal P2P (SPEC-013 Fase 4) bajo estándares Streamlit 2026.
"""

from typing import Any

import pandas as pd

from src.core.spread_monitor import (
    BankRateQuote,
    SpreadMonitor,
)


def render_arbitrage_matrix(
    quotes: list[BankRateQuote],
    bcv_rate: float = 0.0,
    bcv_gap_pct: float = 0.0,
    st_module: Any = None,
) -> None:
    """Renderiza el monitor de spreads interbancarios y arbitraje en vivo."""
    import streamlit as default_st

    st = st_module or default_st

    st.subheader(":material/table_chart: Monitor de Spreads por Banco (USDT / VES)")

    monitor = SpreadMonitor()

    # 1. KPIs de Alto Nivel
    col1, col2, col3 = st.columns(3)

    with col1, st.container(border=True):
        st.metric(
            label="Tasa Oficial BCV",
            value=f"{bcv_rate:,.2f} Bs" if bcv_rate > 0 else "N/D",
            delta=f"{bcv_gap_pct:+.2f}% vs P2P" if bcv_gap_pct != 0 else None,
            delta_color="normal",
        )

    best_monobank = max(quotes, key=lambda q: q.spread_pct) if quotes else None
    with col2, st.container(border=True):
        if best_monobank:
            st.metric(
                label=f"Mejor Monobanco ({best_monobank.bank_name})",
                value=f"{best_monobank.spread_pct:+.2f}%",
                delta=f"{best_monobank.spread_ves:+.2f} Bs",
            )
        else:
            st.metric(label="Mejor Spread Monobanco", value="N/D")

    cross_opp = monitor.find_best_cross_arbitrage(quotes) if quotes else None
    with col3, st.container(border=True):
        if cross_opp:
            st.metric(
                label=f"Arbitraje ({cross_opp['buy_bank']} ➔ {cross_opp['sell_bank']})",
                value=f"{cross_opp['spread_pct']:+.2f}%",
                delta=f"+{cross_opp['net_profit_ves_100u']:,.2f} Bs / 100u",
            )
        else:
            st.metric(label="Arbitraje Cruzado", value="N/D")

    # 2. Tabla Interactiva de Bancos
    if quotes:
        table_data = []
        for q in quotes:
            calc = monitor.calculate_cycle_net_profit(
                crypto_amount=100.0,
                buy_price=q.buy_rate,
                sell_price=q.sell_rate,
            )
            status_icon = (
                "🟢 Saludable"
                if calc.warning_level == "OK"
                else ("🟡 Crítico" if calc.warning_level == "CRITICAL_MARGIN" else "🔴 Pérdida")
            )
            table_data.append(
                {
                    "Banco / Método": q.bank_name,
                    "Compra Maker (Bs)": f"{q.buy_rate:,.2f}",
                    "Venta Maker (Bs)": f"{q.sell_rate:,.2f}",
                    "Spread Bruto (Bs)": f"{q.spread_ves:+,.2f}",
                    "Spread (%)": f"{q.spread_pct:+.2f}%",
                    "Ganancia Neta (100 USDT)": f"{calc.net_profit_ves:+,.2f} Bs",
                    "Retorno USDT": f"{calc.net_profit_usdt:+,.4f} USDT",
                    "Estado": status_icon,
                }
            )

        df = pd.DataFrame(table_data)
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No hay cotizaciones de bancos cargadas en este momento.")

    # 3. Oportunidad de Arbitraje Cruzado Destacada
    if cross_opp and cross_opp["spread_pct"] > 0.80:
        with st.container(border=True):
            st.markdown(
                f"### :material/trending_up: Oportunidad de Arbitraje Interbancario Detectada\n\n"
                f"- **Paso 1 (Compra)**: Colocar anuncio Maker de compra en **{cross_opp['buy_bank']}** a **{cross_opp['buy_rate']:,.2f} VES/USDT**.\n"
                f"- **Paso 2 (Venta)**: Colocar anuncio Maker de venta en **{cross_opp['sell_bank']}** a **{cross_opp['sell_rate']:,.2f} VES/USDT**.\n"
                f"- **Spread Bruto**: **{cross_opp['spread_pct']:+.2f}%** | **Retorno Neto Proyectado**: **+{cross_opp['net_profit_ves_100u']:,.2f} VES** (por ciclo de 100 USDT)."
            )


def render_maker_calculator(st_module: Any = None) -> None:
    """Renderiza la calculadora interactiva de ganancia neta para ciclos Maker en P2P."""
    import streamlit as default_st

    st = st_module or default_st

    st.subheader(":material/calculate: Calculadora de Rentabilidad Real P2P (Ciclo Maker)")
    st.caption(
        "Deduce automáticamente comisiones Binance según tu nivel de comerciante y tarifas interbancarias (0.30% Pago Móvil). "
        "Aplica la regla de oro: **Spread mínimo viable en VES ≥ 0.80%**."
    )

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            capital_usdt = float(
                st.number_input(
                    "Capital Operativo (USDT)",
                    min_value=10.0,
                    max_value=100000.0,
                    value=500.0,
                    step=50.0,
                    help="Monto de USDT con el que inicias el ciclo de compra.",
                )
            )

        with col2:
            buy_rate = float(
                st.number_input(
                    "Tasa de Compra Maker (VES)",
                    min_value=1.0,
                    value=844.00,
                    step=0.50,
                    help="Precio al que compraste los USDT en tu anuncio.",
                )
            )

        with col3:
            sell_rate = float(
                st.number_input(
                    "Tasa de Venta Maker (VES)",
                    min_value=1.0,
                    value=854.00,
                    step=0.50,
                    help="Precio al que vendes los USDT en tu anuncio.",
                )
            )

        col_tier, col_bank = st.columns(2)

        tier_map = {
            "Usuario Normal (0.35%)": 0.0035,
            "Nivel Bronce (0.25%)": 0.0025,
            "Nivel Plata (0.20%)": 0.0020,
            "Nivel Oro / PRO (0.15%)": 0.0015,
        }

        with col_tier:
            selected_tier = st.selectbox(
                "Nivel de Comerciante Binance (Comisión Maker)",
                list(tier_map.keys()),
                index=0,
            )
            maker_fee_pct = tier_map.get(selected_tier, 0.0035)

        with col_bank:
            include_pago_movil = st.checkbox(
                "Incluir Comisión Bancaria (0.30% Pago Móvil en ambas patas)",
                value=True,
                help="Los bancos en Venezuela cobran 0.30% por Pago Móvil interbancario tanto al fondear como al transferir.",
            )
            bank_fee_pct = 0.003 if include_pago_movil else 0.0

        # Cálculo matemático
        calc = SpreadMonitor.calculate_cycle_net_profit(
            crypto_amount=capital_usdt,
            buy_price=buy_rate,
            sell_price=sell_rate,
            binance_maker_fee_pct=maker_fee_pct,
            bank_fee_pct=bank_fee_pct,
        )

        st.divider()

        # Visualización de Resultados
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric(
                label="Monto Invertido (VES)",
                value=f"{calc.gross_buy_ves:,.2f} Bs",
            )
        with m2:
            st.metric(
                label="Comisiones Totales",
                value=f"{calc.binance_fee_ves:,.2f} Bs Binance",
                delta=f"-{(calc.bank_fee_buy_ves + calc.bank_fee_sell_ves):,.2f} Bs Banco",
                delta_color="inverse",
            )
        with m3:
            delta_color = "normal" if calc.net_profit_usdt > 0 else "inverse"
            st.metric(
                label="Ganancia Neta (USDT)",
                value=f"{calc.net_profit_usdt:+,.4f} USDT",
                delta=f"{calc.net_spread_pct:+.2f}% ROI",
                delta_color=delta_color,
            )
        with m4:
            st.metric(
                label="Ganancia Neta (VES)",
                value=f"{calc.net_profit_ves:+,.2f} Bs",
                delta=f"Spread Bruto: {calc.gross_spread_pct:+.2f}%",
                delta_color="normal" if calc.net_profit_ves > 0 else "inverse",
            )

        # Diagnóstico y Alertas Semánticas
        if calc.warning_level == "LOSS":
            st.error(
                f":material/dangerous: **Pérdida Neta Confirmada**: Este ciclo genera una pérdida real de **{calc.net_profit_ves:,.2f} VES** "
                f"({calc.net_profit_usdt:,.4f} USDT). El spread bruto del {calc.gross_spread_pct:.2f}% es completamente consumido por "
                f"la comisión de Binance y comisiones bancarias."
            )
        elif calc.warning_level == "CRITICAL_MARGIN":
            st.warning(
                f":material/warning: **Margen Crítico ({calc.gross_spread_pct:.2f}% < 0.80%)**: Aunque la calculadora arroja una ganancia nominal "
                f"de +{calc.net_profit_usdt:,.4f} USDT, el spread está por debajo del umbral de seguridad de 0.80% en VES. Cualquier micro-deslizamiento "
                f"de tasa cambiaria o redondeo bancario transformará la operación en pérdida."
            )
        else:
            st.success(
                f":material/check_circle: **Margen Saludable ({calc.gross_spread_pct:.2f}% ≥ 0.80%)**: Operación rentable. "
                f"Retorno neto estimado de **+{calc.net_profit_ves:,.2f} VES** (+{calc.net_profit_usdt:,.4f} USDT, {calc.net_spread_pct:+.2f}% ROI) "
                f"tras absorber todas las tarifas de plataforma y bancarias."
            )
