"""Motor de cálculo fiscal (ISLR) con métodos FIFO y Costo Promedio Ponderado.
Módulo puro sin dependencias del motor de trading de Binance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from src.data.models import Order


@dataclass
class TaxLot:
    crypto_amount: float
    total_cost_fiat: float
    unit_cost_fiat: float


@dataclass
class TradeResult:
    order_number: str
    trade_type: str
    crypto_amount: float
    sell_price_fiat: float
    total_revenue_fiat: float
    acquisition_cost_fiat: float
    fee_fiat: float
    net_profit_fiat: float
    bcv_rate: float
    net_profit_usd: float
    created_at: datetime | None = None
    inventory_shortfall_crypto: float = 0.0


class CostMethod(ABC):
    @abstractmethod
    def process_orders(self, orders: list[Order]) -> list[TradeResult]:
        pass


class FIFOCostMethod(CostMethod):
    """Método FIFO (First-In, First-Out): Las compras más antiguas se liquidan primero."""

    def __init__(
        self,
        initial_inventory: list[TaxLot] | None = None,
        fallback_bcv_rate: float | None = None,
    ):
        self.initial_inventory: list[TaxLot] = [
            TaxLot(
                crypto_amount=lot.crypto_amount,
                total_cost_fiat=lot.total_cost_fiat,
                unit_cost_fiat=lot.unit_cost_fiat,
            )
            for lot in (initial_inventory or [])
        ]
        self.fallback_bcv_rate: float | None = (
            float(fallback_bcv_rate) if fallback_bcv_rate and float(fallback_bcv_rate) > 0 else None
        )
        self.inventory_warnings: list[str] = []
        self.bcv_warnings: list[str] = []

    def process_orders(
        self,
        orders: list[Order],
        initial_inventory: list[TaxLot] | None = None,
    ) -> list[TradeResult]:
        self.inventory_warnings = []
        self.bcv_warnings = []
        starting_lots = initial_inventory if initial_inventory is not None else self.initial_inventory
        inventory: list[TaxLot] = [
            TaxLot(
                crypto_amount=lot.crypto_amount,
                total_cost_fiat=lot.total_cost_fiat,
                unit_cost_fiat=lot.unit_cost_fiat,
            )
            for lot in starting_lots
        ]
        results: list[TradeResult] = []
        last_valid_bcv = self.fallback_bcv_rate or 0.0

        for order in orders:
            status_val = str(getattr(order, "order_status", "COMPLETED") or "COMPLETED").upper()
            if status_val != "COMPLETED":
                continue
            raw_bcv = float(order.bcv_rate) if getattr(order, "bcv_rate", None) else 0.0
            if raw_bcv > 0.0:
                last_valid_bcv = raw_bcv

            if order.trade_type == "BUY":
                # Compras entran al inventario acumulando costo total + comisiones
                crypto_amount = float(order.crypto_amount)
                fiat_amount = float(order.fiat_amount)
                fee_fiat = float(order.fee_fiat)
                total_cost = fiat_amount + fee_fiat
                unit_cost = total_cost / crypto_amount if crypto_amount > 0 else 0.0
                inventory.append(TaxLot(
                    crypto_amount=crypto_amount,
                    total_cost_fiat=total_cost,
                    unit_cost_fiat=unit_cost,
                ))
            elif order.trade_type == "SELL":
                sell_amount = float(order.crypto_amount)
                remaining_sell = sell_amount
                matched_cost_fiat = 0.0

                while remaining_sell > 0 and inventory:
                    lot = inventory[0]
                    if lot.crypto_amount <= remaining_sell:
                        matched_cost_fiat += lot.total_cost_fiat
                        remaining_sell -= lot.crypto_amount
                        inventory.pop(0)
                    else:
                        proportion = remaining_sell / lot.crypto_amount
                        cost_used = lot.total_cost_fiat * proportion
                        matched_cost_fiat += cost_used
                        lot.crypto_amount -= remaining_sell
                        lot.total_cost_fiat -= cost_used
                        remaining_sell = 0.0

                shortfall = round(max(0.0, remaining_sell), 6) if remaining_sell > 1e-6 else 0.0
                if shortfall > 0.0:
                    self.inventory_warnings.append(
                        f"Orden {order.order_number}: inventario insuficiente en PEPS "
                        f"(faltante de {shortfall:.4f} USDT sin lote previo). Registra el saldo inicial."
                    )

                revenue = float(order.fiat_amount)
                fee_fiat = float(order.fee_fiat)
                net_profit = revenue - matched_cost_fiat - fee_fiat
                rate = raw_bcv if raw_bcv > 0.0 else last_valid_bcv
                if rate <= 0.0:
                    rate = 0.0
                    profit_usd = 0.0
                    self.bcv_warnings.append(
                        f"Orden {order.order_number}: sin tasa oficial BCV (>0); contravalor USD omitido."
                    )
                else:
                    profit_usd = net_profit / rate

                results.append(TradeResult(
                    order_number=str(order.order_number),
                    trade_type="SELL",
                    crypto_amount=sell_amount,
                    sell_price_fiat=float(order.unit_price),
                    total_revenue_fiat=revenue,
                    acquisition_cost_fiat=matched_cost_fiat,
                    fee_fiat=fee_fiat,
                    net_profit_fiat=net_profit,
                    bcv_rate=rate,
                    net_profit_usd=profit_usd,
                    created_at=cast(datetime | None, order.created_at),
                    inventory_shortfall_crypto=shortfall,
                ))

        return results


class WeightedAverageCostMethod(CostMethod):
    """Método de Costo Promedio Ponderado."""

    def __init__(
        self,
        initial_inventory: list[TaxLot] | None = None,
        fallback_bcv_rate: float | None = None,
    ):
        self._initial_lots = list(initial_inventory) if initial_inventory else []
        self.fallback_bcv_rate: float | None = (
            float(fallback_bcv_rate) if fallback_bcv_rate and float(fallback_bcv_rate) > 0 else None
        )
        self.inventory_warnings: list[str] = []
        self.bcv_warnings: list[str] = []

    def process_orders(
        self,
        orders: list[Order],
        initial_inventory: list[TaxLot] | None = None,
    ) -> list[TradeResult]:
        self.inventory_warnings = []
        self.bcv_warnings = []
        starting_lots = initial_inventory if initial_inventory is not None else self._initial_lots
        total_crypto = sum(float(lot.crypto_amount) for lot in starting_lots)
        total_cost_fiat = sum(float(lot.total_cost_fiat) for lot in starting_lots)
        results: list[TradeResult] = []
        last_valid_bcv = self.fallback_bcv_rate or 0.0

        for order in orders:
            status_val = str(getattr(order, "order_status", "COMPLETED") or "COMPLETED").upper()
            if status_val != "COMPLETED":
                continue
            crypto_amount = float(order.crypto_amount)
            fiat_amount = float(order.fiat_amount)
            fee_fiat = float(order.fee_fiat)
            raw_bcv = float(order.bcv_rate) if getattr(order, "bcv_rate", None) else 0.0
            if raw_bcv > 0.0:
                last_valid_bcv = raw_bcv

            if order.trade_type == "BUY":
                total_crypto += crypto_amount
                total_cost_fiat += (fiat_amount + fee_fiat)
            elif order.trade_type == "SELL":
                shortfall = round(max(0.0, crypto_amount - total_crypto), 6) if crypto_amount > total_crypto + 1e-6 else 0.0
                if shortfall > 0.0:
                    self.inventory_warnings.append(
                        f"Orden {order.order_number}: inventario insuficiente en Costo Promedio "
                        f"(faltante de {shortfall:.4f} USDT sin lote previo)."
                    )
                avg_unit_cost = (total_cost_fiat / total_crypto) if total_crypto > 0 else 0.0
                covered_qty = min(crypto_amount, total_crypto) if total_crypto > 0 else 0.0
                matched_cost_fiat = avg_unit_cost * covered_qty

                total_crypto = max(0.0, total_crypto - crypto_amount)
                total_cost_fiat = max(0.0, total_cost_fiat - matched_cost_fiat)

                revenue = fiat_amount
                net_profit = revenue - matched_cost_fiat - fee_fiat
                rate = raw_bcv if raw_bcv > 0.0 else last_valid_bcv
                if rate <= 0.0:
                    rate = 0.0
                    profit_usd = 0.0
                    self.bcv_warnings.append(
                        f"Orden {order.order_number}: sin tasa oficial BCV (>0); contravalor USD omitido."
                    )
                else:
                    profit_usd = net_profit / rate

                results.append(TradeResult(
                    order_number=str(order.order_number),
                    trade_type="SELL",
                    crypto_amount=crypto_amount,
                    sell_price_fiat=float(order.unit_price),
                    total_revenue_fiat=revenue,
                    acquisition_cost_fiat=matched_cost_fiat,
                    fee_fiat=fee_fiat,
                    net_profit_fiat=net_profit,
                    bcv_rate=rate,
                    net_profit_usd=profit_usd,
                    created_at=cast(datetime | None, order.created_at),
                    inventory_shortfall_crypto=shortfall,
                ))

        return results
