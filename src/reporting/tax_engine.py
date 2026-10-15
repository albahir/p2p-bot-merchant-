"""Motor de cálculo fiscal (ISLR) con métodos FIFO y Costo Promedio Ponderado.
Módulo puro sin dependencias del motor de trading de Binance.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
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


class CostMethod(ABC):
    @abstractmethod
    def process_orders(self, orders: List[Order]) -> List[TradeResult]:
        pass


class FIFOCostMethod(CostMethod):
    """Método FIFO (First-In, First-Out): Las compras más antiguas se liquidan primero."""

    def process_orders(self, orders: List[Order]) -> List[TradeResult]:
        inventory: List[TaxLot] = []
        results: List[TradeResult] = []

        for order in orders:
            if order.trade_type == "BUY":
                # Compras entran al inventario acumulando costo total + comisiones
                total_cost = order.fiat_amount + order.fee_fiat
                unit_cost = total_cost / order.crypto_amount if order.crypto_amount > 0 else 0
                inventory.append(TaxLot(
                    crypto_amount=order.crypto_amount,
                    total_cost_fiat=total_cost,
                    unit_cost_fiat=unit_cost
                ))
            elif order.trade_type == "SELL":
                sell_amount = order.crypto_amount
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

                revenue = order.fiat_amount
                net_profit = revenue - matched_cost_fiat - order.fee_fiat
                rate = order.bcv_rate if order.bcv_rate > 0 else 1.0
                profit_usd = net_profit / rate

                results.append(TradeResult(
                    order_number=order.order_number,
                    trade_type="SELL",
                    crypto_amount=sell_amount,
                    sell_price_fiat=order.unit_price,
                    total_revenue_fiat=revenue,
                    acquisition_cost_fiat=matched_cost_fiat,
                    fee_fiat=order.fee_fiat,
                    net_profit_fiat=net_profit,
                    bcv_rate=rate,
                    net_profit_usd=profit_usd
                ))

        return results


class WeightedAverageCostMethod(CostMethod):
    """Método de Costo Promedio Ponderado."""

    def process_orders(self, orders: List[Order]) -> List[TradeResult]:
        total_crypto = 0.0
        total_cost_fiat = 0.0
        results: List[TradeResult] = []

        for order in orders:
            if order.trade_type == "BUY":
                total_crypto += order.crypto_amount
                total_cost_fiat += (order.fiat_amount + order.fee_fiat)
            elif order.trade_type == "SELL":
                avg_unit_cost = (total_cost_fiat / total_crypto) if total_crypto > 0 else 0.0
                matched_cost_fiat = avg_unit_cost * order.crypto_amount

                total_crypto = max(0.0, total_crypto - order.crypto_amount)
                total_cost_fiat = max(0.0, total_cost_fiat - matched_cost_fiat)

                revenue = order.fiat_amount
                net_profit = revenue - matched_cost_fiat - order.fee_fiat
                rate = order.bcv_rate if order.bcv_rate > 0 else 1.0
                profit_usd = net_profit / rate

                results.append(TradeResult(
                    order_number=order.order_number,
                    trade_type="SELL",
                    crypto_amount=order.crypto_amount,
                    sell_price_fiat=order.unit_price,
                    total_revenue_fiat=revenue,
                    acquisition_cost_fiat=matched_cost_fiat,
                    fee_fiat=order.fee_fiat,
                    net_profit_fiat=net_profit,
                    bcv_rate=rate,
                    net_profit_usd=profit_usd
                ))

        return results
