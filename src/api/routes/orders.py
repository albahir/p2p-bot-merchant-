"""Rutas de gestión, sincronización y descarga de órdenes de Binance P2P."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_authenticated, require_trader
from src.api.schemas.orders import (
    OrderItemResponse,
    OrderListResponse,
    SyncOrdersRequest,
    SyncOrdersResponse,
)
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.models import User
from src.data.repositories import OrderRepository

router = APIRouter(prefix="/api/orders", tags=["Órdenes P2P"])


@router.get("", response_model=OrderListResponse)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_authenticated)],
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=50, ge=1, le=200, description="Cantidad de registros por página"),
    trade_type: str | None = Query(default=None, pattern="^(BUY|SELL)$"),
    order_status: str | None = Query(default=None),
    search: str | None = Query(default=None, description="Búsqueda por número de orden o contraparte"),
) -> OrderListResponse:
    """Retorna el listado paginado de órdenes registradas en el sistema."""
    repo = OrderRepository(db)
    skip = (page - 1) * page_size
    total, items = repo.list_paginated(
        skip=skip,
        limit=page_size,
        trade_type=trade_type,
        order_status=order_status,
        search=search,
    )

    return OrderListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[OrderItemResponse.model_validate(o) for o in items],
    )


@router.post("/sync", response_model=SyncOrdersResponse)
def sync_binance_orders(
    req: SyncOrdersRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> SyncOrdersResponse:
    """Extrae el historial oficial de órdenes de Binance P2P vía API oficial."""
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
        pass

    client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
    syncer = BinanceHistorySyncer()
    result = syncer.sync_orders(
        client=client,
        db=db,
        days=req.days,
        trade_type=req.trade_type or "ALL",
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error_message or "Error sincronizando con Binance API.",
        )

    return SyncOrdersResponse(
        success=True,
        total_fetched=result.total_fetched,
        orders_inserted=result.orders_inserted,
        orders_existing=result.orders_existing,
        buy_orders=result.buy_orders,
        sell_orders=result.sell_orders,
        total_volume_usdt=result.total_volume_usdt,
        total_volume_fiat=result.total_volume_fiat,
        message=f"Sincronización completada: {result.orders_inserted} nuevas órdenes guardadas.",
    )


@router.get("/export")
def export_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_authenticated)],
    format: str = Query(default="xlsx", pattern="^(xlsx|csv_semicolon|csv_comma)$"),
) -> Response:
    """Genera y descarga el archivo con el historial de órdenes en Excel o CSV."""
    repo = OrderRepository(db)
    orders = repo.list_completed()

    if format == "xlsx":
        file_bytes = BinanceHistorySyncer.generate_orders_excel(orders)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "ordenes_binance_p2p.xlsx"
    elif format == "csv_semicolon":
        file_bytes = BinanceHistorySyncer.generate_orders_csv(orders, sep=";")
        media_type = "text/csv; charset=utf-8"
        filename = "ordenes_binance_p2p_excel.csv"
    else:
        file_bytes = BinanceHistorySyncer.generate_orders_csv(orders, sep=",")
        media_type = "text/csv; charset=utf-8"
        filename = "ordenes_binance_p2p_comma.csv"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": media_type,
    }
    return Response(content=file_bytes, media_type=media_type, headers=headers)
