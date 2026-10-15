"""Esquemas de datos fuertemente tipados con Pydantic para la API oficial C2C/P2P de Binance.
Garantiza validación estricta en tiempo de ejecución de todas las respuestas de la red.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatusEnum(str, Enum):
    """Estados del ciclo de vida de una orden P2P en Binance."""
    PENDING = "PENDING"
    TRADING = "TRADING"
    BUYER_PAYED = "BUYER_PAYED"
    DISTRIBUTING = "DISTRIBUTING"
    COMPLETED = "COMPLETED"
    IN_APPEAL = "IN_APPEAL"
    CANCELLED = "CANCELLED"
    CANCELLED_BY_SYSTEM = "CANCELLED_BY_SYSTEM"


class TradeTypeEnum(str, Enum):
    """Sentido de la operación en el libro P2P."""
    BUY = "BUY"
    SELL = "SELL"


class AdvertisementRoleEnum(str, Enum):
    """Rol de ejecución respecto al anuncio."""
    MAKER = "MAKER"
    TAKER = "TAKER"


class BinanceOrderMatchItem(BaseModel):
    """Representación de una orden individual devuelta por GET /sapi/v1/c2c/orderMatch/listUserOrderHistory."""
    orderNumber: str = Field(..., description="Identificador único de la orden en Binance")
    advNo: str = Field(..., description="Número del anuncio de origen")
    tradeType: TradeTypeEnum = Field(..., description="Sentido de la orden (BUY/SELL)")
    asset: str = Field(..., description="Criptoactivo (USDT, BTC, etc.)")
    fiat: str = Field(..., description="Divisa fíat (VES, USD, etc.)")
    fiatSymbol: str | None = Field(default="", description="Símbolo de la divisa fíat (Bs, $, etc.)")
    amount: str = Field(..., description="Cantidad de cripto negociada")
    totalPrice: str = Field(..., description="Monto total en moneda fíat")
    unitPrice: str = Field(..., description="Precio unitario de ejecución")
    orderStatus: OrderStatusEnum = Field(..., description="Estado de la orden")
    createTime: int = Field(..., description="Timestamp de creación en milisegundos UTC")
    advertisementRole: AdvertisementRoleEnum | None = Field(default=None, description="Rol del comerciante (MAKER/TAKER)")
    takerCommission: str | None = Field(default="0", description="Comisión cobrada al taker")
    takerAmount: str | None = Field(default=None, description="Cantidad ejecutada del taker")
    commission: str | None = Field(default="0", description="Comisión cobrada al maker")
    counterPartNickName: str | None = Field(default="", description="Apodo de la contraparte")

    @property
    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    @property
    def total_price_decimal(self) -> Decimal:
        return Decimal(self.totalPrice)

    @property
    def unit_price_decimal(self) -> Decimal:
        return Decimal(self.unitPrice)

    @property
    def fee_decimal(self) -> Decimal:
        # Sumar comisiones reportadas (maker o taker)
        taker_fee = Decimal(self.takerCommission or "0")
        maker_fee = Decimal(self.commission or "0")
        return taker_fee + maker_fee


class BinanceOrderHistoryResponse(BaseModel):
    """Respuesta completa del endpoint de historial de órdenes."""
    code: str = Field(..., description="Código de respuesta ('000000' indica éxito)")
    message: str | None = Field(default="success")
    success: bool = Field(default=True)
    total: int | None = Field(default=0)
    data: list[BinanceOrderMatchItem] = Field(default_factory=list)


class BinanceAdvertiserInfo(BaseModel):
    """Métricas públicas de un comerciante en el order book."""
    nickName: str
    monthOrderCount: int = 0
    monthFinishRate: float = 0.0


class BinanceAdDetail(BaseModel):
    """Detalle de un anuncio en el order book."""
    advNo: str
    tradeType: TradeTypeEnum
    asset: str
    fiatUnit: str
    price: str
    surplusAmount: str
    minSingleTransAmount: str | None = "0"
    maxSingleTransAmount: str | None = "0"


class BinanceSearchOrderItem(BaseModel):
    """Elemento individual de búsqueda en POST /sapi/v1/c2c/orderMatch/search."""
    adv: BinanceAdDetail
    advertiser: BinanceAdvertiserInfo


class BinanceSearchResponse(BaseModel):
    """Respuesta de búsqueda de anuncios en el order book."""
    code: str
    message: str | None = None
    success: bool = True
    total: int = 0
    data: list[BinanceSearchOrderItem] = Field(default_factory=list)


class BinanceServerTime(BaseModel):
    """Respuesta de sincronización horaria GET /api/v3/time."""
    serverTime: int
