"""Rutas de consulta de Spreads P2P, Matriz de Arbitraje Interbancario y tasas BCV."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas.spreads import (
    ArbitrageMatrixResponse,
    BCVRateResponse,
    BestArbitrageItem,
    RateQuoteItem,
)
from src.core.spread_monitor import SpreadMonitor
from src.reporting.bcv_service import BCVService

router = APIRouter(prefix="/api/spreads", tags=["Spreads & Arbitraje"])


@router.get("/bcv", response_model=BCVRateResponse)
def get_bcv_rates() -> BCVRateResponse:
    """Retorna las tasas oficiales vigentes del Banco Central de Venezuela (BCV)."""
    bcv_service = BCVService()
    full_rates = bcv_service.fetch_full_rates()
    usd_rate = float(full_rates.get("usd") or bcv_service.get_official_rate())
    if usd_rate <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tasa oficial del BCV no disponible temporalmente (Fail-closed). Sin valores por defecto.",
        )

    eur_rate = float(full_rates["eur"]) if "eur" in full_rates else None
    cny_rate = float(full_rates["cny"]) if "cny" in full_rates else None
    fecha_valor = full_rates.get("fecha_valor")

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
        timestamp=datetime.now(UTC),
    )


@router.get("/matrix", response_model=ArbitrageMatrixResponse)
def get_arbitrage_matrix(
    amount_usdt: float = Query(default=100.0, ge=1.0, description="Monto en USDT para proyectar retorno"),
) -> ArbitrageMatrixResponse:
    """Calcula la matriz comparativa de cotizaciones bancarias y el mejor arbitraje cruzado."""
    spread_mon = SpreadMonitor()
    bcv_service = BCVService()

    quotes = spread_mon.fetch_live_quotes()
    bcv_usd = bcv_service.get_official_rate()

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
        best_item = BestArbitrageItem(
            buy_bank=best_cross["buy_bank"],
            buy_rate=best_cross["buy_rate"],
            sell_bank=best_cross["sell_bank"],
            sell_rate=best_cross["sell_rate"],
            spread_ves=best_cross["spread_ves"],
            spread_pct=best_cross["spread_pct"],
            net_profit_ves=best_cross["net_profit_ves_100u"],
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


@router.get("/banks", response_model=list[str])
def get_supported_banks() -> list[str]:
    """Retorna la lista de bancos y métodos de pago monitoreados en Binance P2P."""
    return list(SpreadMonitor.BINANCE_METHODS_MAP.keys())
