"""Motor de Reconstrucción Fiscal P2P de 6 Piezas y Snapshots Mensuales.
Aplica la ecuación contable de consistencia patrimonial:
Saldo Inicial + Entradas (Depósitos + Compras) - Salidas (Retiros + Ventas) - Comisiones = Saldo Final Teórico.
Calcula ISLR mediante FIFOCostMethod con inventario inicial valorado a tasa BCV.
"""

import calendar
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.data.models import BankVoucher, FiscalPeriodSnapshot
from src.data.repositories import (
    BankVoucherRepository,
    FiscalSnapshotRepository,
    OrderRepository,
    WalletMovementRepository,
)
from src.reporting.bcv_service import BCVService
from src.reporting.tax_engine import FIFOCostMethod, TaxLot

logger = logging.getLogger("fiscal_reconciler")


@dataclass
class FiscalReconciliationResult:
    period: str
    initial_balance: float
    inflows_deposits: float
    inflows_p2p_buys: float
    total_inflows: float
    outflows_withdrawals: float
    outflows_p2p_sells: float
    total_outflows: float
    volume_operated: float
    total_fees: float
    calculated_final_balance: float
    actual_final_balance: float
    discrepancy: float
    gross_revenue_ves: float
    acquisition_cost_ves: float
    net_profit_ves: float
    net_profit_usd: float
    status: str
    orders_count: int = 0
    movements_count: int = 0
    vouchers_count: int = 0
    matched_vouchers_count: int = 0
    message: str = ""


class FiscalReconciler:
    """Motor de cálculo y auditoría de consistencia de 6 piezas para comerciantes P2P."""

    def __init__(self, db_session: Session, bcv_service: BCVService | None = None):
        self.db = db_session
        self.bcv_service = bcv_service or BCVService()
        self.order_repo = OrderRepository(self.db)
        self.wallet_repo = WalletMovementRepository(self.db)
        self.snapshot_repo = FiscalSnapshotRepository(self.db)
        self.voucher_repo = BankVoucherRepository(self.db)

    @staticmethod
    def _parse_period_dates(period: str) -> tuple[datetime, datetime]:
        """Convierte una cadena YYYY-MM en tupla (start_datetime, end_datetime) UTC."""
        parts = period.split("-")
        if len(parts) != 2:
            raise ValueError(f"Formato de período inválido '{period}'. Debe ser 'YYYY-MM'.")
        year = int(parts[0])
        month = int(parts[1])
        _, last_day = calendar.monthrange(year, month)

        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=UTC)
        end_dt = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=UTC)
        return start_dt, end_dt

    def reconcile_period(
        self,
        period: str,
        initial_balance: float | None = None,
        initial_bcv_rate: float | None = None,
        actual_final_balance: float | None = None,
        asset: str = "USDT",
    ) -> FiscalReconciliationResult:
        """Calcula las 6 piezas fiscales para el período mensual especificado."""
        start_dt, end_dt = self._parse_period_dates(period)

        # 1. Pieza 1: Saldo Inicial
        if initial_balance is None:
            # Buscar snapshot del mes anterior
            prev_month = 12 if start_dt.month == 1 else start_dt.month - 1
            prev_year = start_dt.year - 1 if start_dt.month == 1 else start_dt.year
            prev_period = f"{prev_year:04d}-{prev_month:02d}"
            prev_snap = self.snapshot_repo.get_by_period(prev_period)
            if prev_snap is not None:
                initial_balance = float(prev_snap.actual_final_balance)
            else:
                initial_balance = 0.0

        if initial_bcv_rate is None or initial_bcv_rate <= 0:
            try:
                rate_val = self.bcv_service.fetch_current_rate()
                initial_bcv_rate = float(rate_val) if rate_val else 1.0
            except (RuntimeError, ValueError, OSError, KeyError, AttributeError):
                initial_bcv_rate = 1.0

        # Obtener órdenes del período
        all_orders = self.order_repo.list_completed(start_date=start_dt, end_date=end_dt)
        asset_orders = [o for o in all_orders if (o.asset or "").upper() == asset.upper()]

        p2p_buys = [o for o in asset_orders if o.trade_type == "BUY"]
        p2p_sells = [o for o in asset_orders if o.trade_type == "SELL"]

        inflows_p2p_buys = sum(float(o.crypto_amount) for o in p2p_buys)
        outflows_p2p_sells = sum(float(o.crypto_amount) for o in p2p_sells)
        volume_operated = sum(float(o.crypto_amount) for o in asset_orders)

        # Obtener movimientos de billetera (Depósitos y Retiros)
        all_movements = self.wallet_repo.list_completed(start_date=start_dt, end_date=end_dt)
        asset_movements = [m for m in all_movements if (m.asset or "").upper() == asset.upper()]

        deposits = [m for m in asset_movements if m.movement_type == "DEPOSIT"]
        withdrawals = [m for m in asset_movements if m.movement_type == "WITHDRAWAL"]

        inflows_deposits = sum(float(m.amount) for m in deposits)
        outflows_withdrawals = sum(float(m.amount) for m in withdrawals)
        withdrawal_fees = sum(float(m.fee) for m in withdrawals)

        total_inflows = inflows_deposits + inflows_p2p_buys
        total_outflows = outflows_withdrawals + outflows_p2p_sells
        total_fees = withdrawal_fees

        # Ecuación de consistencia: Saldo Final Teórico
        calculated_final = round(initial_balance + total_inflows - total_outflows - total_fees, 6)

        if actual_final_balance is None:
            actual_final_balance = calculated_final

        discrepancy = round(actual_final_balance - calculated_final, 6)
        status = "BALANCED" if abs(discrepancy) < 0.001 else "DISCREPANCY"

        if status == "BALANCED":
            message = "Período fiscal balanceado y consistente con los movimientos bancarios y cripto."
        else:
            diff_label = "Faltante (merma no justificada)" if discrepancy < 0 else "Sobrante no registrado"
            message = f"Discrepancia detectada: {diff_label} de {abs(discrepancy):.4f} {asset}."

        # Cálculo ISLR mediante FIFOCostMethod con inventario inicial
        initial_lots: list[TaxLot] = []
        if initial_balance > 0:
            initial_lots.append(
                TaxLot(
                    crypto_amount=initial_balance,
                    total_cost_fiat=initial_balance * initial_bcv_rate,
                    unit_cost_fiat=initial_bcv_rate,
                )
            )

        fifo = FIFOCostMethod(initial_inventory=initial_lots)
        trade_results = fifo.process_orders(asset_orders)

        gross_revenue_ves = sum(r.total_revenue_fiat for r in trade_results)
        acquisition_cost_ves = sum(r.acquisition_cost_fiat for r in trade_results)
        net_profit_ves = sum(r.net_profit_fiat for r in trade_results)
        net_profit_usd = sum(r.net_profit_usd for r in trade_results)

        # Comprobantes bancarios (estadísticas de conciliación)
        vouchers = (
            self.db.query(BankVoucher)
            .filter(cast(Any, BankVoucher.created_at >= start_dt), cast(Any, BankVoucher.created_at <= end_dt))
            .all()
        )
        vouchers_count = len(vouchers)
        matched_vouchers_count = sum(1 for v in vouchers if v.verification_status == "MATCHED")

        return FiscalReconciliationResult(
            period=period,
            initial_balance=round(initial_balance, 6),
            inflows_deposits=round(inflows_deposits, 6),
            inflows_p2p_buys=round(inflows_p2p_buys, 6),
            total_inflows=round(total_inflows, 6),
            outflows_withdrawals=round(outflows_withdrawals, 6),
            outflows_p2p_sells=round(outflows_p2p_sells, 6),
            total_outflows=round(total_outflows, 6),
            volume_operated=round(volume_operated, 6),
            total_fees=round(total_fees, 6),
            calculated_final_balance=round(calculated_final, 6),
            actual_final_balance=round(actual_final_balance, 6),
            discrepancy=round(discrepancy, 6),
            gross_revenue_ves=round(gross_revenue_ves, 2),
            acquisition_cost_ves=round(acquisition_cost_ves, 2),
            net_profit_ves=round(net_profit_ves, 2),
            net_profit_usd=round(net_profit_usd, 2),
            status=status,
            orders_count=len(asset_orders),
            movements_count=len(asset_movements),
            vouchers_count=vouchers_count,
            matched_vouchers_count=matched_vouchers_count,
            message=message,
        )

    def save_snapshot(self, result: FiscalReconciliationResult) -> FiscalPeriodSnapshot:
        """Persiste o actualiza el snapshot mensual de reconciliación en la base de datos."""
        snapshot = FiscalPeriodSnapshot(
            period=result.period,
            initial_balance=result.initial_balance,
            inflows_deposits=result.inflows_deposits,
            inflows_p2p_buys=result.inflows_p2p_buys,
            outflows_withdrawals=result.outflows_withdrawals,
            outflows_p2p_sells=result.outflows_p2p_sells,
            volume_operated=result.volume_operated,
            total_fees=result.total_fees,
            calculated_final_balance=result.calculated_final_balance,
            actual_final_balance=result.actual_final_balance,
            discrepancy=result.discrepancy,
            gross_revenue_ves=result.gross_revenue_ves,
            acquisition_cost_ves=result.acquisition_cost_ves,
            net_profit_ves=result.net_profit_ves,
            net_profit_usd=result.net_profit_usd,
            status=result.status,
        )
        return cast(FiscalPeriodSnapshot, self.snapshot_repo.upsert_snapshot(snapshot))
