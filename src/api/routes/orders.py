"""Rutas de gestión, sincronización y descarga de órdenes de Binance P2P."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_db, get_settings, require_authenticated, require_trader
from src.api.schemas.orders import (
    OrderItemResponse,
    OrderListResponse,
    SyncOrdersRequest,
    SyncOrdersResponse,
)
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.models import User
from src.data.repositories import OrderRepository
from src.security.file_guards import MAX_ORDERS_UPLOAD_BYTES, read_upload_bounded

router = APIRouter(prefix="/api/orders", tags=["Órdenes P2P"])



@router.get("", response_model=OrderListResponse)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_authenticated)],
    page: Annotated[int, Query(ge=1, description="Número de página")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Cantidad de registros por página")] = 50,
    trade_type: Annotated[str | None, Query(pattern="^(BUY|SELL)$")] = None,
    order_status: Annotated[str | None, Query()] = None,
    payment_method: Annotated[str | None, Query(max_length=64, description="Filtro por banco o método de pago")] = None,
    date_from: Annotated[str | None, Query(description="Fecha inicio YYYY-MM-DD (Hora VET UTC-4)")] = None,
    date_to: Annotated[str | None, Query(description="Fecha fin YYYY-MM-DD (Hora VET UTC-4)")] = None,
    min_amount: Annotated[float | None, Query(ge=0.0, description="Cantidad mínima en USDT")] = None,
    max_amount: Annotated[float | None, Query(ge=0.0, description="Cantidad máxima en USDT")] = None,
    sort_by: Annotated[
        str,
        Query(pattern="^(date_desc|date_asc|amount_desc|amount_asc|price_desc|price_asc)$"),
    ] = "date_desc",
    search: Annotated[str | None, Query(description="Búsqueda por número de orden, contraparte o banco")] = None,
) -> OrderListResponse:
    """Retorna el listado paginado y filtrado de órdenes registradas por el operador autenticado."""
    from datetime import UTC, datetime, timedelta, timezone
    from datetime import date as date_cls

    vet_tz = timezone(timedelta(hours=-4))
    start_dt: datetime | None = None
    end_dt: datetime | None = None

    if date_from and date_from.strip():
        try:
            d_from = date_cls.fromisoformat(date_from.strip())
            start_dt = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato inválido para date_from (use YYYY-MM-DD).",
            ) from err

    if date_to and date_to.strip():
        try:
            d_to = date_cls.fromisoformat(date_to.strip())
            end_dt = datetime(d_to.year, d_to.month, d_to.day, 23, 59, 59, 999999, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato inválido para date_to (use YYYY-MM-DD).",
            ) from err

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    repo = OrderRepository(db, user_id=uid)
    skip = (page - 1) * page_size
    total, items = repo.list_paginated(
        skip=skip,
        limit=page_size,
        trade_type=trade_type,
        order_status=order_status,
        start_date=start_dt,
        end_date=end_dt,
        search=search,
        user_id=uid,
        payment_method=payment_method,
        min_amount=min_amount,
        max_amount=max_amount,
        sort_by=sort_by,
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
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyncOrdersResponse:
    """Extrae el historial oficial de órdenes de Binance P2P vía API oficial."""
    from datetime import date as date_cls

    from sqlalchemy.orm import sessionmaker

    from src.api.routes.settings import _user_binance_key_names
    from src.core.binance_client import BinanceP2PClient
    from src.data.models import AccountingPeriodBalance
    from src.security.api_key_manager import ApiKeyManager

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    k_api, k_priv, _ = _user_binance_key_names(uid)
    api_key = ""
    private_key = ""
    try:
        factory = sessionmaker(bind=db.get_bind())
        km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
        api_key = (km.get_secret(k_api) or "").strip()
        private_key = (km.get_secret(k_priv) or "").strip()
    except (ValueError, KeyError, OSError, RuntimeError, TypeError):
        pass

    if not api_key or not private_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No tienes configuradas tus credenciales de Binance API. "
                "Ve a Configuración → API de Binance, guarda tu API Key y clave secreta/privada, y vuelve a intentar."
            ),
        )

    eff_start_date: date_cls | None = None
    if req.start_date:
        try:
            eff_start_date = date_cls.fromisoformat(req.start_date.strip())
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato inválido para start_date (use YYYY-MM-DD).",
            ) from err
    elif req.year is not None and req.month is not None:
        period_str = f"{req.year}-{req.month:02d}"
        cfg_q = db.query(AccountingPeriodBalance).filter(AccountingPeriodBalance.period == period_str)
        if uid is not None:
            cfg_q = cfg_q.filter(AccountingPeriodBalance.user_id == uid)
        cfg_row = cfg_q.first()
        if cfg_row is not None and cfg_row.cutoff_start_date is not None:
            eff_start_date = cfg_row.cutoff_start_date  # type: ignore[assignment]

    syncer = BinanceHistorySyncer()
    with BinanceP2PClient(api_key=api_key, private_key_pem=private_key) as client:
        result = syncer.sync_orders(
            client=client,
            db=db,
            days=req.days,
            trade_type=req.trade_type or "ALL",
            page_size=100,
            user_id=uid,
            year=req.year,
            month=req.month,
            start_date=eff_start_date,
            only_completed=req.only_completed,
            include_exports=False,
            auto_reconcile=True,
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error_message or "Error sincronizando con Binance API.",
        )

    parts = [f"Sincronización completada ({result.effective_days}d): {result.orders_inserted} nuevas órdenes"]
    if result.orders_updated > 0:
        parts.append(f"{result.orders_updated} actualizadas")
    if result.cancelled_skipped > 0:
        parts.append(f"{result.cancelled_skipped} canceladas omitidas")
    if result.reconciled_vouchers > 0:
        parts.append(f"{result.reconciled_vouchers} comprobante(s) auto-conciliado(s)")
    summary_msg = ", ".join(parts) + "."
    if result.warnings:
        summary_msg = f"{summary_msg} {result.warnings[0]}"

    return SyncOrdersResponse(
        success=True,
        total_fetched=result.total_fetched,
        orders_inserted=result.orders_inserted,
        orders_existing=result.orders_existing,
        orders_updated=result.orders_updated,
        cancelled_skipped=result.cancelled_skipped,
        reconciled_vouchers=result.reconciled_vouchers,
        buy_orders=result.buy_orders,
        sell_orders=result.sell_orders,
        total_volume_usdt=result.total_volume_usdt,
        total_volume_fiat=result.total_volume_fiat,
        effective_days=result.effective_days,
        days_clamped=result.days_clamped,
        warnings=result.warnings,
        message=summary_msg,
    )


@router.post("/upload", response_model=SyncOrdersResponse)
def upload_orders_file(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    only_completed: bool = Query(default=True, description="Omitir órdenes canceladas al importar el archivo"),
) -> SyncOrdersResponse:
    """Importa órdenes de Binance P2P directamente desde un archivo Excel (.xlsx) o CSV descargado."""
    content = read_upload_bounded(file, MAX_ORDERS_UPLOAD_BYTES)

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    syncer = BinanceHistorySyncer()
    result = syncer.import_orders_file(
        file_bytes=content,
        filename=file.filename or "orders.xlsx",
        db=db,
        user_id=uid,
        only_completed=only_completed,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message or "Error procesando archivo de órdenes.",
        )

    parts = [f"Archivo importado: {result.orders_inserted} órdenes completadas nuevas"]
    if result.orders_updated > 0:
        parts.append(f"{result.orders_updated} actualizadas")
    if result.orders_existing > 0:
        parts.append(f"{result.orders_existing} ya existentes")
    if result.cancelled_skipped > 0:
        parts.append(f"{result.cancelled_skipped} canceladas omitidas automáticamente")
    if result.reconciled_vouchers > 0:
        parts.append(f"{result.reconciled_vouchers} comprobante(s) auto-conciliado(s)")

    return SyncOrdersResponse(
        success=True,
        total_fetched=result.total_fetched,
        orders_inserted=result.orders_inserted,
        orders_existing=result.orders_existing,
        orders_updated=result.orders_updated,
        cancelled_skipped=result.cancelled_skipped,
        reconciled_vouchers=result.reconciled_vouchers,
        buy_orders=result.buy_orders,
        sell_orders=result.sell_orders,
        total_volume_usdt=result.total_volume_usdt,
        total_volume_fiat=result.total_volume_fiat,
        message=", ".join(parts) + ".",
    )



@router.get("/export")
def export_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_authenticated)],
    format: str = Query(default="xlsx", pattern="^(xlsx|csv_semicolon|csv_comma)$"),
) -> Response:
    """Genera y descarga el archivo con el historial de órdenes del operador autenticado en Excel o CSV."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    repo = OrderRepository(db, user_id=uid)
    orders = repo.list_completed(user_id=uid)

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
