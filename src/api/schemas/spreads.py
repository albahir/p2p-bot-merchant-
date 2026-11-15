"""Modelos de datos Pydantic para spreads, arbitraje y tasas BCV."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RateQuoteItem(BaseModel):
    """Cotización de un banco o método de pago P2P."""
    model_config = ConfigDict(from_attributes=True)

    bank_name: str
    buy_rate: float
    sell_rate: float
    spread_ves: float
    spread_pct: float
    total_ads: int = 0
    liquidity_pct: float = 0.0
    updated_at: datetime


class BestArbitrageItem(BaseModel):
    """Mejor oportunidad de arbitraje interbancario cruzado."""
    model_config = ConfigDict(from_attributes=True)

    buy_bank: str
    buy_rate: float
    sell_bank: str
    sell_rate: float
    spread_ves: float
    spread_pct: float
    net_profit_ves: float
    is_viable: bool
    warning_message: str = ""


class ArbitrageMatrixResponse(BaseModel):
    """Matriz completa de arbitraje P2P interbancario."""
    quotes: list[RateQuoteItem]
    best_arbitrage: BestArbitrageItem | None = None
    bcv_official_usd: float
    bcv_brecha_pct: float
    timestamp: datetime


class BCVRateResponse(BaseModel):
    """Respuesta con las tasas oficiales publicadas por el BCV."""
    usd: float
    eur: float | None = None
    cny: float | None = None
    fecha_valor: str | None = None
    p2p_usdt_ref: float = 0.0
    brecha_pct: float = 0.0
    source: str = "bcv_db_history"
    timestamp: datetime


class BCVHistoryItemResponse(BaseModel):
    """Registro diario de tasa oficial del BCV almacenado en base de datos."""
    fecha_valor: str
    usd_rate: float
    eur_rate: float | None = None
    source: str = "bcv_official"



class OrderbookAdItem(BaseModel):
    """Anuncio individual del libro de órdenes en vivo de Binance P2P."""
    adv_no: str
    trade_type: str
    price: float
    surplus_usdt: float
    min_ves: float
    max_ves: float
    min_usdt: float
    max_usdt: float
    nick_name: str
    month_orders: int
    finish_rate_pct: float
    is_merchant: bool
    banks: list[str]


class FilteredOrderbookResponse(BaseModel):
    """Respuesta del libro de órdenes filtrado por precio, monto, banco y comerciantes (estilo Binance P2P)."""
    amount_usdt: float
    trans_amount_ves: float
    bank_filter: str
    pay_types: list[str]
    merchant_only: bool
    best_buy_price: float
    best_sell_price: float
    price_spread_ves: float
    price_spread_pct: float
    taker_spread_ves: float
    taker_spread_pct: float
    maker_spread_ves: float
    maker_spread_pct: float
    recommended_mode: str
    net_profit_ves: float
    net_profit_usdt: float
    buy_ads: list[OrderbookAdItem]
    sell_ads: list[OrderbookAdItem]
    source: str
    timestamp: datetime

