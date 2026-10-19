"""Componente visual interactivo del Libro de Órdenes y Mercado Binance P2P con Filtros.
Replica la experiencia de la interfaz oficial de Binance P2P:
- Selector Comprar / Vender con estilo nativo.
- Filtros por Criptomoneda, Divisa Fíat, Monto, Método de Pago / Banco y Comerciante Verificado.
- Presentación de anunciantes con tasas de finalización, precios destacados, límites y badges de bancos.
- Simulador de orden y cálculo de comisiones integrado por cada anuncio.
"""

from typing import Any

import httpx

from src.core.binance_schemas import BinanceSearchOrderItem
from src.core.spread_monitor import SpreadMonitor


def render_binance_p2p_book(
    st_module: Any = None,
    client: Any | None = None,
    use_sandbox: bool = False,
) -> None:
    """Renderiza el libro de órdenes y los filtros interactivos idénticos a Binance P2P."""
    import streamlit as default_st

    st = st_module or default_st

    st.subheader(":material/currency_exchange: Mercado y Libro de Órdenes Binance P2P")
    st.caption("Consulta precios en vivo, filtra por entidad bancaria o monto y simula operaciones con comisiones desglosadas.")

    # 1. Selector de Operación (Comprar / Vender estilo Binance)
    trade_action = st.segmented_control(
        "Sentido de la Operación",
        options=["Comprar USDT", "Vender USDT"],
        default="Comprar USDT",
        label_visibility="collapsed",
    )
    is_buy = trade_action == "Comprar USDT"
    trade_type = "BUY" if is_buy else "SELL"

    # 2. Barra de Filtros estilo Binance
    with st.container(border=True):
        col_fiat, col_crypto, col_amount, col_bank = st.columns([1, 1, 1.2, 1.8])

        with col_fiat:
            fiat = st.selectbox(
                "Moneda Fíat",
                options=["VES", "USD", "EUR", "COP"],
                index=0,
                help="Divisa local para la transacción",
            )

        with col_crypto:
            crypto = st.selectbox(
                "Criptomoneda",
                options=["USDT", "BTC", "ETH", "BNB"],
                index=0,
                help="Activo digital a comerciar",
            )

        with col_amount:
            trans_amount_input = st.number_input(
                f"Monto ({fiat})",
                min_value=0.0,
                value=0.0,
                step=500.0,
                help="Filtra anuncios cuyos límites acepten este monto",
            )
            trans_amount = float(trans_amount_input) if trans_amount_input > 0 else None

        with col_bank:
            all_bank_names = list(SpreadMonitor.BINANCE_METHODS_MAP.keys())
            bank_options = ["Todos los pagos"] + all_bank_names
            selected_bank = st.selectbox(
                "Método de Pago / Banco",
                options=bank_options,
                index=0,
                help="Filtra anuncios que acepten este banco o método (21 métodos oficiales Binance)",
            )

        col_opts, col_mode, col_refresh = st.columns([1.6, 1.6, 0.8], vertical_alignment="bottom")
        with col_opts:
            verified_only = st.toggle("⭐ Solo comerciantes verificados", value=False)
        with col_mode:
            live_feed = st.toggle(
                "🟢 Mercado Real (Binance P2P)",
                value=not use_sandbox,
                help="Consulta anuncios y precios en vivo directamente de Binance P2P",
            )
        with col_refresh:
            st.button("🔄 Actualizar", width="stretch")

    # Mapeo del método bancario hacia el código Binance
    pay_types: list[str] | None = None
    if selected_bank != "Todos los pagos":
        code = (
            SpreadMonitor.BINANCE_METHODS_MAP.get(selected_bank)
            or SpreadMonitor.BANK_PAY_TYPE_MAP.get(selected_bank)
        )
        pay_types = [code] if code else [selected_bank]


    # 3. Obtención de Anuncios (Cliente Binance / BAPI / Mock Fallback)
    p2p_client = client
    is_live_request = live_feed and (client is None or not use_sandbox)

    if p2p_client is None:
        if not is_live_request:
            from src.core.binance_mock import MockBinanceP2PClient
            p2p_client = MockBinanceP2PClient()
        else:
            try:
                from config.settings import Settings
                from src.core.binance_client import BinanceP2PClient
                from src.security.api_key_manager import ApiKeyManager

                settings = Settings()
                api_key = ""
                private_key = ""
                try:
                    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY)
                    api_key = km.get_secret("binance_api_key") or ""
                    private_key = km.get_secret("binance_private_key") or ""
                except (ValueError, KeyError, OSError, RuntimeError, TypeError):
                    api_key = ""
                    private_key = ""

                p2p_client = BinanceP2PClient(
                    api_key=api_key,
                    private_key_pem=private_key,
                )
            except (ImportError, ValueError, KeyError, OSError, RuntimeError):
                from src.core.binance_mock import MockBinanceP2PClient
                p2p_client = MockBinanceP2PClient()

    ads: list[BinanceSearchOrderItem] = []
    mode_label = "🟢 Binance P2P Oficial (En Vivo)" if is_live_request else "🧪 Simulación (Sandbox)"
    with st.spinner("Consultando cotizaciones de Binance P2P..."):
        try:
            # Primero intentar búsqueda en vivo (BAPI pública o SAPI según el cliente)
            resp = p2p_client.search_p2p_ads(
                asset=crypto,
                fiat=fiat,
                trade_type=trade_type,
                pay_types=pay_types,
                trans_amount=trans_amount,
                merchant_check=verified_only,
                rows=15,
                use_public_bapi=is_live_request,
            )
            ads = resp.data
        except (httpx.HTTPError, OSError, RuntimeError, ValueError, KeyError, TypeError) as fetch_err:
            st.warning(f"Aviso de Red: No se pudo conectar a la API en vivo de Binance ({fetch_err}). Mostrando datos de simulación calibrados.")
            from src.core.binance_mock import MockBinanceP2PClient
            fallback_mock = MockBinanceP2PClient()
            resp = fallback_mock.search_p2p_ads(
                asset=crypto,
                fiat=fiat,
                trade_type=trade_type,
                pay_types=pay_types,
                trans_amount=trans_amount,
                merchant_check=verified_only,
                rows=15,
            )
            ads = resp.data
            mode_label = "🧪 Simulación Calibrada (Fallback sin red)"

    # 4. Renderizado del Libro de Órdenes
    st.markdown(
        f"<div style='display: flex; justify-content: space-between; align-items: center; margin: 0.75rem 0;'>"
        f"<span style='font-weight: 600; color: #F0F6FC;'>Anuncios Activos ({len(ads)}) — {crypto}/{fiat}</span>"
        f"<span class='badge-pill badge-matched'>{mode_label}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not ads:
        st.info("No se encontraron anuncios con los filtros seleccionados. Intenta ampliar los métodos de pago o el rango de monto.")
        return

    # Renderizar cada anuncio con diseño inspirado en Binance P2P
    for idx, ad_item in enumerate(ads):
        adv = ad_item.adv
        advertiser = ad_item.advertiser
        price_val = float(adv.price)
        min_limit = float(adv.minSingleTransAmount or "0")
        max_limit = float(adv.maxSingleTransAmount or "0")
        surplus = float(adv.surplusAmount)

        with st.container(border=True):
            col_adv, col_price, col_limits, col_action = st.columns([1.5, 1.2, 1.8, 1], vertical_alignment="center")

            with col_adv:
                st.markdown(f"**👤 {advertiser.nickName}**")
                finish_pct = advertiser.monthFinishRate * 100
                st.caption(f"{advertiser.monthOrderCount} órdenes | {finish_pct:.1f}% finalización")

            with col_price:
                price_color = "#10B981" if is_buy else "#F43F5E"
                st.markdown(
                    f"<div style='font-size: 1.35rem; font-weight: 700; color: {price_color};'>"
                    f"{price_val:,.2f} <span style='font-size: 0.85rem; color: #8B949E;'>{fiat}</span></div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Precio por 1 {crypto}")

            with col_limits:
                st.markdown(f"**Disponible**: `{surplus:,.2f} {crypto}`")
                st.markdown(f"**Límites**: `{min_limit:,.2f} {fiat}` - `{max_limit:,.2f} {fiat}`")

                # Badges de métodos de pago bancarios
                banks_html = "".join(
                    [f"<span class='badge-pill badge-matched' style='font-size: 0.68rem; margin-right: 0.3rem;'>{b}</span>" for b in ad_item.bank_names]
                )
                if banks_html:
                    st.markdown(banks_html, unsafe_allow_html=True)

            with col_action:
                btn_label = f"Comprar {crypto}" if is_buy else f"Vender {crypto}"
                btn_type = "primary" if is_buy else "secondary"
                expand_key = f"expand_sim_{trade_type}_{adv.advNo}_{idx}"
                if st.button(btn_label, key=f"btn_{expand_key}", width="stretch", type=btn_type):
                    st.session_state[f"show_sim_{expand_key}"] = not st.session_state.get(f"show_sim_{expand_key}", False)

            # Simulador desplegable de ciclo y comisiones con este anuncio
            if st.session_state.get(f"show_sim_{expand_key}", False):
                with st.expander(f"🧮 Simular Operación con {advertiser.nickName}", expanded=True):
                    sim_c1, sim_c2 = st.columns(2)
                    with sim_c1:
                        sim_crypto = st.number_input(
                            f"Cantidad a operar ({crypto})",
                            min_value=10.0,
                            max_value=max(surplus, 100.0),
                            value=min(100.0, surplus),
                            step=10.0,
                            key=f"input_crypto_{expand_key}",
                        )
                    with sim_c2:
                        gross_fiat = sim_crypto * price_val
                        st.metric(f"Total Bruto ({fiat})", f"{gross_fiat:,.2f} {fiat}")

                    # Cálculo financiero con SpreadMonitor
                    monitor = SpreadMonitor()
                    # Estimar venta de ciclo con 1% de margen si es compra
                    sim_buy_p = price_val if is_buy else price_val * 0.99
                    sim_sell_p = price_val * 1.01 if is_buy else price_val
                    calc = monitor.calculate_cycle_net_profit(
                        crypto_amount=sim_crypto,
                        buy_price=sim_buy_p,
                        sell_price=sim_sell_p,
                    )

                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.caption("Comisión Binance Maker (0.35%)")
                        st.write(f"`{calc.binance_fee_ves:,.2f} {fiat}`")
                    with m2:
                        st.caption("Comisión Bancaria Oculta (0.30% PM)")
                        st.write(f"`{calc.bank_fee_buy_ves + calc.bank_fee_sell_ves:,.2f} {fiat}`")
                    with m3:
                        st.caption("Retorno Neto Proyectado de Ciclo")
                        ret_color = "#10B981" if calc.net_profit_ves > 0 else "#F43F5E"
                        st.markdown(f"<span style='font-weight: 700; color: {ret_color};'>{calc.net_profit_ves:+,.2f} {fiat}</span>", unsafe_allow_html=True)
