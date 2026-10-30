"""Modelos de datos Pydantic para órdenes, sincronización y exportación."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemResponse(BaseModel):
    """Representación de una orden individual de Binance P2P."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    trade_type: str
    asset: str
    fiat: str
    fiat_amount: float
    crypto_amount: float
    unit_price: float
    fee_fiat: float
    fee_crypto: float
    bcv_rate: float
    order_status: str
    counterparty_name: str | None = None
    created_at: datetime


class OrderListResponse(BaseModel):
    """Listado paginado de órdenes."""
    total: int
    page: int
    page_size: int
    items: list[OrderItemResponse]


class SyncOrdersRequest(BaseModel):
    """Parámetros para solicitar extracción directa de Binance P2P."""
    days: int = Field(default=30, ge=1, le=365)
    trade_type: str | None = Field(default=None, pattern="^(BUY|SELL)$")


class SyncOrdersResponse(BaseModel):
    """Resultado de la sincronización de órdenes."""
    success: bool
    total_fetched: int
    orders_inserted: int
    orders_existing: int
    buy_orders: int
    sell_orders: int
    total_volume_usdt: float
    total_volume_fiat: float
    message: str
