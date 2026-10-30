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
    timestamp: datetime
