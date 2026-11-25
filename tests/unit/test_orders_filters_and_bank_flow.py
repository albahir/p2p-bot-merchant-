"""Pruebas TDD para:
1. Filtros avanzados y ordenamiento en /api/orders (banco, fechas VET, rango USDT, sort_by).
2. Conteo real de órdenes/anuncios Compra vs Venta por banco en SpreadMonitor y /api/market/analytics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routes.market import get_market_analytics
from src.api.routes.orders import list_orders
from src.core.binance_schemas import (
    BinanceAdDetail,
    BinanceAdvertiserInfo,
    BinanceSearchOrderItem,
    BinanceSearchResponse,
    BinanceTradeMethod,
    TradeTypeEnum,
)
from src.core.spread_monitor import SpreadMonitor
from src.data.database import Base
from src.data.models import MarketSnapshot, Order
from src.security.auth_service import AuthService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _make_search_item(
    adv_no: str,
    trade_type: str,
    price: float,
    surplus: float,
    bank_name: str,
    month_orders: int = 200,
    is_merchant: bool = True,
) -> BinanceSearchOrderItem:
    return BinanceSearchOrderItem(
        adv=BinanceAdDetail(
            advNo=adv_no,
            tradeType=TradeTypeEnum(trade_type),
            asset="USDT",
            fiatUnit="VES",
            price=f"{price:.2f}",
            surplusAmount=f"{surplus:.2f}",
            minSingleTransAmount="500.00",
            maxSingleTransAmount="5000000.00",
            tradeMethods=[
                BinanceTradeMethod(
                    tradeMethodName=bank_name,
                    payType=bank_name.replace(" ", ""),
                    tradeMethodShortName=bank_name,
                )
            ],
        ),
        advertiser=BinanceAdvertiserInfo(
            nickName=f"Trader_{adv_no}",
            monthOrderCount=month_orders,
            monthFinishRate=0.99,
            userType="merchant" if is_merchant else "user",
        ),
    )


def test_orders_endpoint_advanced_filters_bank_date_vet_amount_and_sort(db_session):
    """GET /api/orders debe filtrar por banco, rango de fechas VET (UTC-4), monto USDT y ordenamiento."""
    user = AuthService(db_session=db_session).ensure_default_admin(default_username="filter_trader")

    # 2026-11-24 22:30 VET == 2026-11-25 02:30 UTC (clave VET!)
    dt_nov24_vet_night = datetime(2026, 11, 25, 2, 30, 0, tzinfo=UTC)
    # 2026-11-25 10:00 VET == 2026-11-25 14:00 UTC
    dt_nov25_vet_morning = datetime(2026, 11, 25, 14, 0, 0, tzinfo=UTC)

    orders = [
        Order(
            user_id=int(user.id),
            order_number="ORD-BANESCO-SMALL",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=25000.0,
            crypto_amount=50.0,
            unit_price=500.0,
            fee_fiat=0.0,
            fee_crypto=0.0,
            bcv_rate=400.0,
            order_status="COMPLETED",
            payment_method="Banesco",
            counterparty_name="Carlos",
            created_at=dt_nov24_vet_night,
        ),
        Order(
            user_id=int(user.id),
            order_number="ORD-BANESCO-BIG",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=153000.0,
            crypto_amount=300.0,
            unit_price=510.0,
            fee_fiat=0.0,
            fee_crypto=0.0,
            bcv_rate=400.0,
            order_status="COMPLETED",
            payment_method="Banesco",
            counterparty_name="Maria",
            created_at=dt_nov25_vet_morning,
        ),
        Order(
            user_id=int(user.id),
            order_number="ORD-MERCANTIL-MID",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=60000.0,
            crypto_amount=120.0,
            unit_price=500.0,
            fee_fiat=0.0,
            fee_crypto=0.0,
            bcv_rate=400.0,
            order_status="COMPLETED",
            payment_method="Mercantil",
            counterparty_name="Luis",
            created_at=dt_nov25_vet_morning,
        ),
    ]
    db_session.add_all(orders)
    db_session.commit()

    # 1. Filtrar por banco Banesco
    res_bank = list_orders(
        db=db_session,
        current_user=user,
        page=1,
        page_size=20,
        payment_method="Banesco",
    )
    assert res_bank.total == 2
    assert all(item.payment_method == "Banesco" for item in res_bank.items)

    # 2. Filtrar por fecha VET 2026-11-24 (debe incluir 2026-11-25 02:30 UTC porque en VET es 24/11 22:30!)
    res_nov24 = list_orders(
        db=db_session,
        current_user=user,
        page=1,
        page_size=20,
        date_from="2026-11-24",
        date_to="2026-11-24",
    )
    assert [i.order_number for i in res_nov24.items] == ["ORD-BANESCO-SMALL"]

    # 3. Filtrar por rango de monto USDT (100 a 350) + ordenar por mayor monto
    res_amt = list_orders(
        db=db_session,
        current_user=user,
        page=1,
        page_size=20,
        min_amount=100.0,
        max_amount=350.0,
        sort_by="amount_desc",
    )
    assert [i.order_number for i in res_amt.items] == ["ORD-BANESCO-BIG", "ORD-MERCANTIL-MID"]


def test_spread_monitor_orderbook_exposes_real_buy_vs_sell_counts_for_selected_bank():
    """fetch_filtered_orderbook debe exponer el total real de anuncios Compra vs Venta del banco seleccionado."""

    class SpyBinanceClient:
        def search_p2p_ads(self, *, trade_type: str, **kwargs):
            if trade_type == "BUY":
                return BinanceSearchResponse(
                    code="000000",
                    message="success",
                    success=True,
                    total=84,
                    data=[
                        _make_search_item("B1", "BUY", 1010.0, 500.0, "Banesco", month_orders=450, is_merchant=True),
                        _make_search_item("B2", "BUY", 1011.0, 300.0, "Banesco", month_orders=150, is_merchant=False),
                    ],
                )
            return BinanceSearchResponse(
                code="000000",
                message="success",
                success=True,
                total=36,
                data=[
                    _make_search_item("S1", "SELL", 1005.0, 400.0, "Banesco", month_orders=300, is_merchant=True),
                ],
            )

    book = SpreadMonitor().fetch_filtered_orderbook(
        amount_usdt=100.0,
        bank="Banesco",
        rows=20,
        client=SpyBinanceClient(),
    )

    assert book["total_buy_ads"] == 84
    assert book["total_sell_ads"] == 36
    assert book["buy_ads_share_pct"] == pytest.approx(70.0, abs=0.1)
    assert book["sell_ads_share_pct"] == pytest.approx(30.0, abs=0.1)
    assert book["buy_month_orders_sum"] == 600
    assert book["sell_month_orders_sum"] == 300
    assert isinstance(book["market_pressure_label"], str) and len(book["market_pressure_label"]) > 0


def test_market_analytics_returns_bank_order_flow_and_per_bank_ad_counts(db_session):
    """GET /api/market/analytics debe devolver el conteo Compra vs Venta para el banco elegido y por cada banco en tabla."""
    base_dt = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    db_session.add(
        MarketSnapshot(
            timestamp=base_dt - timedelta(minutes=5),
            bcv_rate=918.76,
            p2p_buy_best=1062.0,
            p2p_buy_avg20=1063.0,
            p2p_sell_best=1068.0,
            p2p_sell_avg20=1066.5,
            p2p_mid=1064.75,
            brecha_pct=15.9,
            spread_ves=-6.0,
            vol_buy_usdt=12000.0,
            vol_sell_usdt=15000.0,
        )
    )
    db_session.commit()

    mock_book = {
        "bank_filter": "Banesco",
        "best_buy_price": 1063.0,
        "best_sell_price": 1069.0,
        "total_buy_ads": 92,
        "total_sell_ads": 48,
        "buy_ads_share_pct": 65.7,
        "sell_ads_share_pct": 34.3,
        "buy_merchants_count": 15,
        "sell_merchants_count": 10,
        "buy_month_orders_sum": 14500,
        "sell_month_orders_sum": 8900,
        "market_pressure_label": "Mayor oferta de venta USDT (más anuncios en Compra)",
        "buy_ads": [
            {"price": 1063.0, "surplus_usdt": 1000.0, "banks": ["Banesco"], "month_orders": 500, "is_merchant": True},
            {"price": 1064.0, "surplus_usdt": 800.0, "banks": ["Banesco"], "month_orders": 400, "is_merchant": True},
        ],
        "sell_ads": [
            {"price": 1069.0, "surplus_usdt": 1500.0, "banks": ["Banesco"], "month_orders": 300, "is_merchant": True},
        ],
    }

    with (
        patch("src.core.spread_monitor.SpreadMonitor.fetch_filtered_orderbook", return_value=mock_book),
        patch("src.reporting.bcv_history_service.BCVHistoryService.get_or_fetch_current_rates", return_value={"usd": 918.76}),
    ):
        res = get_market_analytics(bank="Banesco", ticket_ves=500_000.0, db=db_session)

    assert res.order_flow.bank_filter == "Banesco"
    assert res.order_flow.total_buy_ads == 92
    assert res.order_flow.total_sell_ads == 48
    assert res.order_flow.buy_ads_share_pct == pytest.approx(65.7, abs=0.2)
    assert res.order_flow.sell_ads_share_pct == pytest.approx(34.3, abs=0.2)
    assert res.order_flow.buy_month_orders_sum == 14500
    assert res.order_flow.sell_month_orders_sum == 8900
    assert len(res.banks_snapshot) == 1
    assert res.banks_snapshot[0].buy_ads_count == 2
    assert res.banks_snapshot[0].sell_ads_count == 1
