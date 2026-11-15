"""Rutas de consulta de Spreads P2P, Matriz de Arbitraje Interbancario y tasas BCV."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas.spreads import (
    ArbitrageMatrixResponse,
    BCVHistoryItemResponse,
    BCVRateResponse,
    BestArbitrageItem,
    FilteredOrderbookResponse,
    OrderbookAdItem,
    RateQuoteItem,
)
from src.core.spread_monitor import SpreadMonitor
from src.reporting.bcv_history_service import VET_TIMEZONE, BCVHistoryService
from src.reporting.bcv_service import BCVService

router = APIRouter(prefix="/api/spreads", tags=["Spreads & Arbitraje"])


def _resolve_bcv_with_db_history(db: Session | None) -> dict[str, object]:
    """Obtiene la tasa BCV desde la tabla histórica `bcv_rate_history` en BD;
    si aún no existe para la Fecha Valor hábil actual, consulta el BCV en vivo y la guarda en BD.
    """
    bcv_service = BCVService()
    if db is not None and isinstance(db, Session):
        history_svc = BCVHistoryService(db_session=db, bcv_live_service=bcv_service)
        return history_svc.get_or_fetch_current_rates()

    full_rates = bcv_service.fetch_full_rates()
    usd_val = float(full_rates.get("usd") or bcv_service.get_official_rate() or 0.0)
    return {
        "usd": usd_val,
        "eur": full_rates.get("eur"),
        "cny": full_rates.get("cny"),
        "fecha_valor": full_rates.get("fecha_valor"),
        "source": "bcv_live",
    }


@router.get("/bcv", response_model=BCVRateResponse)
def get_bcv_rates(
    db: Annotated[Session | None, Depends(get_db)] = None,
) -> BCVRateResponse:
    """Retorna las tasas oficiales vigentes del BCV (cargadas desde `bcv_rate_history` o persistidas al consultar)."""
    full_rates = _resolve_bcv_with_db_history(db)
    usd_raw = full_rates.get("usd")
    usd_rate = float(str(usd_raw)) if usd_raw is not None else 0.0
    if usd_rate <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tasa oficial del BCV no disponible temporalmente (Fail-closed). Sin valores por defecto.",
        )

    eur_raw = full_rates.get("eur")
    cny_raw = full_rates.get("cny")
    eur_rate = float(str(eur_raw)) if eur_raw is not None else None
    cny_rate = float(str(cny_raw)) if cny_raw is not None else None
    fecha_valor = str(full_rates["fecha_valor"]) if full_rates.get("fecha_valor") else None
    source_str = str(full_rates.get("source") or "bcv_db_history")

    # Referencia P2P para brecha (sin multiplicar por valores artificiales)
    spread_mon = SpreadMonitor()
    quotes = spread_mon.fetch_live_quotes()
    p2p_ref = quotes[0].sell_rate if quotes else 0.0
    brecha = spread_mon.calculate_bcv_gap(p2p_ref, usd_rate) if p2p_ref > 0 else 0.0

    return BCVRateResponse(
        usd=usd_rate,
        eur=eur_rate,
        cny=cny_rate,
        fecha_valor=fecha_valor,
        p2p_usdt_ref=p2p_ref,
        brecha_pct=brecha,
        source=source_str,
        timestamp=datetime.now(UTC),
    )


@router.get("/bcv/history", response_model=list[BCVHistoryItemResponse])
def get_bcv_rate_history(
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Cantidad de días hacia atrás a consultar"),
) -> list[BCVHistoryItemResponse]:
    """Retorna el historial de tasas oficiales del BCV almacenadas en `bcv_rate_history`."""
    history_svc = BCVHistoryService(db_session=db)
    # Asegurar que la tasa vigente del día esté registrada en BD
    history_svc.get_or_fetch_current_rates()

    end_date = datetime.now(VET_TIMEZONE).date()
    start_date = end_date - timedelta(days=days)
    records = history_svc.repo.list_rates(start_date=start_date, end_date=end_date)
    return [
        BCVHistoryItemResponse(
            fecha_valor=str(r.fecha_valor),
            usd_rate=float(r.usd_rate),
            eur_rate=float(r.eur_rate) if r.eur_rate is not None else None,
            source=str(r.source or "bcv_official"),
        )
        for r in reversed(records)
    ]


@router.get("/matrix", response_model=ArbitrageMatrixResponse)
def get_arbitrage_matrix(
    db: Annotated[Session | None, Depends(get_db)] = None,
    amount_usdt: float = Query(
        default=100.0,
        ge=1.0,
        le=100000.0,
        description="Monto en USDT para filtrar volumen y proyectar retorno",
    ),
    merchant_only: bool = Query(
        default=False,
        description="Filtrar únicamente anuncios de comerciantes verificados en Binance P2P",
    ),
) -> ArbitrageMatrixResponse:
    """Calcula la matriz comparativa de cotizaciones bancarias y el mejor arbitraje cruzado."""
    spread_mon = SpreadMonitor()

    # Si se solicita un volumen distinto al base (100 USDT) o solo verificados,
    # convertir a monto aproximado en VES (transAmount) para filtrar límites reales en Binance
    trans_amount_ves: float | None = None
    if abs(amount_usdt - 100.0) > 0.01 or merchant_only:
        base_quotes = spread_mon.fetch_live_quotes()
        ref_rate = base_quotes[0].buy_rate if base_quotes and base_quotes[0].buy_rate > 0 else 1005.0
        trans_amount_ves = round(amount_usdt * ref_rate, 2)
        quotes = spread_mon.fetch_live_quotes(
            trans_amount_ves=trans_amount_ves,
            merchant_only=merchant_only,
        )
    else:
        quotes = spread_mon.fetch_live_quotes()

    # Cargar tasa oficial BCV desde la tabla histórica `bcv_rate_history` (0ms si ya fue guardada hoy)
    bcv_data = _resolve_bcv_with_db_history(db)
    bcv_usd_raw = bcv_data.get("usd")
    bcv_usd = float(str(bcv_usd_raw)) if bcv_usd_raw is not None else 0.0

    if not quotes:
        return ArbitrageMatrixResponse(
            quotes=[],
            best_arbitrage=None,
            bcv_official_usd=bcv_usd,
            bcv_brecha_pct=0.0,
            timestamp=datetime.now(UTC),
        )

    quote_items = [
        RateQuoteItem(
            bank_name=q.bank_name,
            buy_rate=q.buy_rate,
            sell_rate=q.sell_rate,
            spread_ves=q.spread_ves,
            spread_pct=q.spread_pct,
            total_ads=q.total_ads,
            liquidity_pct=q.liquidity_pct,
            updated_at=q.updated_at,
        )
        for q in quotes
    ]

    best_cross = spread_mon.find_best_cross_arbitrage(quotes)
    best_item: BestArbitrageItem | None = None
    if best_cross:
        scaled_profit_ves = round(float(best_cross["net_profit_ves_100u"]) * (float(amount_usdt) / 100.0), 2)
        best_item = BestArbitrageItem(
            buy_bank=best_cross["buy_bank"],
            buy_rate=best_cross["buy_rate"],
            sell_bank=best_cross["sell_bank"],
            sell_rate=best_cross["sell_rate"],
            spread_ves=best_cross["spread_ves"],
            spread_pct=best_cross["spread_pct"],
            net_profit_ves=scaled_profit_ves,
            is_viable=best_cross["is_viable"],
            warning_message="Arbitraje interbancario disponible" if best_cross["is_viable"] else "Margen ajustado",
        )

    p2p_ref = quotes[0].sell_rate if quotes else bcv_usd
    brecha = spread_mon.calculate_bcv_gap(p2p_ref, bcv_usd)

    return ArbitrageMatrixResponse(
        quotes=quote_items,
        best_arbitrage=best_item,
        bcv_official_usd=bcv_usd,
        bcv_brecha_pct=brecha,
        timestamp=datetime.now(UTC),
    )


@router.get("/orderbook", response_model=FilteredOrderbookResponse)
def get_filtered_orderbook(
    amount_usdt: float = Query(
        default=100.0,
        ge=1.0,
        le=100000.0,
        description="Monto en USDT para filtrar anuncios compatibles",
    ),
    amount_ves: float | None = Query(
        default=None,
        ge=0.0,
        le=500000000.0,
        description="Monto exacto en Bolívares (VES / transAmount) tal cual el filtro de Binance P2P",
    ),
    bank: str = Query(
        default="Todos",
        max_length=64,
        description="Banco o método de pago (ej. Todos, Pago Móvil, Banesco, Mercantil, Venezuela)",
    ),
    merchant_only: bool = Query(
        default=False,
        description="Filtrar solo comerciantes verificados (escudo amarillo en Binance P2P)",
    ),
    rows: int = Query(
        default=10,
        ge=1,
        le=20,
        description="Cantidad de anuncios por columna (Compra / Venta)",
    ),
) -> FilteredOrderbookResponse:
    """Retorna el Spread por Precio y el Libro de Anuncios en vivo con los filtros exactos de Binance P2P."""
    spread_mon = SpreadMonitor()
    data = spread_mon.fetch_filtered_orderbook(
        amount_usdt=amount_usdt,
        amount_ves=amount_ves,
        bank=bank,
        merchant_only=merchant_only,
        rows=rows,
    )
    return FilteredOrderbookResponse(
        amount_usdt=data["amount_usdt"],
        trans_amount_ves=data["trans_amount_ves"],
        bank_filter=data["bank_filter"],
        pay_types=data["pay_types"],
        merchant_only=data["merchant_only"],
        best_buy_price=data["best_buy_price"],
        best_sell_price=data["best_sell_price"],
        price_spread_ves=data["price_spread_ves"],
        price_spread_pct=data["price_spread_pct"],
        taker_spread_ves=data["taker_spread_ves"],
        taker_spread_pct=data["taker_spread_pct"],
        maker_spread_ves=data["maker_spread_ves"],
        maker_spread_pct=data["maker_spread_pct"],
        recommended_mode=data["recommended_mode"],
        net_profit_ves=data["net_profit_ves"],
        net_profit_usdt=data["net_profit_usdt"],
        buy_ads=[OrderbookAdItem(**ad) for ad in data["buy_ads"]],
        sell_ads=[OrderbookAdItem(**ad) for ad in data["sell_ads"]],
        source=data["source"],
        timestamp=data["timestamp"],
    )


@router.get("/banks", response_model=list[str])
def get_supported_banks() -> list[str]:
    """Retorna la lista de bancos y métodos de pago monitoreados en Binance P2P."""
    return list(SpreadMonitor.BINANCE_METHODS_MAP.keys())
