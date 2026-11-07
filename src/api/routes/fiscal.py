"""Rutas de Reconciliación Fiscal P2P de 6 Piezas y Cumplimiento Tributario SENIAT."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_trader
from src.data.models import User
from src.reporting.bcv_service import BCVService
from src.reporting.fiscal_reconciler import FiscalReconciler

logger = logging.getLogger("api_fiscal")

router = APIRouter(prefix="/api/fiscal", tags=["Gestión Fiscal P2P"])


class FiscalReconciliationRequest(BaseModel):
    period: str = Field(..., description="Período contable en formato YYYY-MM", examples=["2026-10"])
    initial_balance: float = Field(default=0.0, ge=0.0, description="Saldo inicial real en USDT")
    actual_final_balance: float | None = Field(default=None, ge=0.0, description="Saldo final real en USDT (Snapshot)")
    asset: str = Field(default="USDT", description="Activo cripto principal")
    cost_method: str = Field(default="FIFO", description="Método de costeo: FIFO o AVG")


class FiscalReconciliationResponse(BaseModel):
    period: str
    initial_balance: float
    inflows_p2p_buys: float
    total_inflows: float
    outflows_p2p_sells: float
    total_outflows: float
    volume_operated: float
    volume_operated_ves: float = 0.0
    total_fees: float
    total_fees_ves: float = 0.0
    calculated_final_balance: float
    actual_final_balance: float
    discrepancy: float
    gross_revenue_ves: float
    acquisition_cost_ves: float
    net_profit_ves: float
    net_profit_usd: float
    status: str
    orders_count: int
    message: str
    bcv_rate: float
    cost_method: str = "FIFO"


@router.get("/summary", response_model=FiscalReconciliationResponse)
def get_fiscal_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    period: str = Query(default=datetime.now(UTC).strftime("%Y-%m"), description="Período en formato YYYY-MM"),
    initial_balance: float = Query(default=0.0, ge=0.0),
    actual_final_balance: float | None = Query(default=None, ge=0.0),
    cost_method: str = Query(default="FIFO", description="Método de costeo fiscal: FIFO o AVG"),
) -> FiscalReconciliationResponse:
    """Calcula y retorna la ecuación contable de 6 piezas para auditoría fiscal P2P."""
    try:
        bcv_svc = BCVService()
        reconciler = FiscalReconciler(db_session=db, bcv_service=bcv_svc)
        res = reconciler.reconcile_period(
            period=period,
            initial_balance=initial_balance,
            actual_final_balance=actual_final_balance,
            cost_method=cost_method,
        )
        bcv_val = bcv_svc.fetch_current_rate() or 0.0

        return FiscalReconciliationResponse(
            period=res.period,
            initial_balance=res.initial_balance,
            inflows_p2p_buys=res.inflows_p2p_buys,
            total_inflows=res.total_inflows,
            outflows_p2p_sells=res.outflows_p2p_sells,
            total_outflows=res.total_outflows,
            volume_operated=res.volume_operated,
            volume_operated_ves=res.volume_operated_ves,
            total_fees=res.total_fees,
            total_fees_ves=res.total_fees_ves,
            calculated_final_balance=res.calculated_final_balance,
            actual_final_balance=res.actual_final_balance,
            discrepancy=res.discrepancy,
            gross_revenue_ves=res.gross_revenue_ves,
            acquisition_cost_ves=res.acquisition_cost_ves,
            net_profit_ves=res.net_profit_ves,
            net_profit_usd=res.net_profit_usd,
            status=res.status,
            orders_count=res.orders_count,
            message=res.message,
            bcv_rate=bcv_val,
            cost_method=res.cost_method,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except (SQLAlchemyError, TypeError, KeyError, OSError) as err:
        logger.error("Fallo durante el cálculo fiscal de 6 piezas: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno procesando la conciliación contable de 6 piezas.",
        )


@router.post("/reconcile", response_model=FiscalReconciliationResponse)
def execute_fiscal_reconciliation(
    req: FiscalReconciliationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> FiscalReconciliationResponse:
    """Ejecuta y persiste la reconciliación patrimonial del período especificado."""
    try:
        bcv_svc = BCVService()
        reconciler = FiscalReconciler(db_session=db, bcv_service=bcv_svc)
        res = reconciler.reconcile_period(
            period=req.period,
            initial_balance=req.initial_balance,
            actual_final_balance=req.actual_final_balance,
            asset=req.asset,
            cost_method=req.cost_method,
        )
        reconciler.save_snapshot(res)
        bcv_val = bcv_svc.fetch_current_rate() or 0.0

        return FiscalReconciliationResponse(
            period=res.period,
            initial_balance=res.initial_balance,
            inflows_p2p_buys=res.inflows_p2p_buys,
            total_inflows=res.total_inflows,
            outflows_p2p_sells=res.outflows_p2p_sells,
            total_outflows=res.total_outflows,
            volume_operated=res.volume_operated,
            volume_operated_ves=res.volume_operated_ves,
            total_fees=res.total_fees,
            total_fees_ves=res.total_fees_ves,
            calculated_final_balance=res.calculated_final_balance,
            actual_final_balance=res.actual_final_balance,
            discrepancy=res.discrepancy,
            gross_revenue_ves=res.gross_revenue_ves,
            acquisition_cost_ves=res.acquisition_cost_ves,
            net_profit_ves=res.net_profit_ves,
            net_profit_usd=res.net_profit_usd,
            status=res.status,
            orders_count=res.orders_count,
            message=res.message,
            bcv_rate=bcv_val,
            cost_method=res.cost_method,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except (SQLAlchemyError, TypeError, KeyError, OSError) as err:
        logger.error("Error persistiendo reconciliación fiscal: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la persistencia del cierre contable.",
        )


@router.get("/snapshot")
def get_fiscal_snapshot(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    period: str = Query(default=datetime.now(UTC).strftime("%Y-%m"), description="Período en formato YYYY-MM"),
) -> dict[str, Any]:
    """Consulta si un período mensual ya fue cerrado y sellado en la base de datos."""
    _ = current_user
    from src.data.repositories import FiscalSnapshotRepository

    snap_repo = FiscalSnapshotRepository(db)
    snap = snap_repo.get_by_period(period)
    if not snap:
        return {"period": period, "is_closed": False, "snapshot": None}

    return {
        "period": period,
        "is_closed": True,
        "snapshot": {
            "period": snap.period,
            "initial_balance": float(snap.initial_balance),
            "calculated_final_balance": float(snap.calculated_final_balance),
            "actual_final_balance": float(snap.actual_final_balance),
            "discrepancy": float(snap.discrepancy),
            "total_fees": float(snap.total_fees),
            "net_profit_ves": float(snap.net_profit_ves),
            "net_profit_usd": float(snap.net_profit_usd),
            "status": snap.status,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
        },
    }
