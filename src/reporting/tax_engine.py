"""Motor de cálculo fiscal (ISLR) con métodos FIFO y Costo Promedio Ponderado.
Módulo puro sin dependencias del motor de trading de Binance.
"""

from abc import ABC, abstractmethod
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
    def process_orders(self, orders: list[Order]) -> list[TradeResult]:
        pass


class FIFOCostMethod(CostMethod):
    """Método FIFO (First-In, First-Out): Las compras más antiguas se liquidan primero."""

    def process_orders(self, orders: list[Order]) -> list[TradeResult]:
        inventory: list[TaxLot] = []
        results: list[TradeResult] = []

        for order in orders:
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

                revenue = float(order.fiat_amount)
                fee_fiat = float(order.fee_fiat)
                net_profit = revenue - matched_cost_fiat - fee_fiat
                bcv_rate = float(order.bcv_rate) if order.bcv_rate else 1.0
                rate = bcv_rate if bcv_rate > 0 else 1.0
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
                ))

        return results


class WeightedAverageCostMethod(CostMethod):
    """Método de Costo Promedio Ponderado."""

    def process_orders(self, orders: list[Order]) -> list[TradeResult]:
        total_crypto = 0.0
        total_cost_fiat = 0.0
        results: list[TradeResult] = []

        for order in orders:
            crypto_amount = float(order.crypto_amount)
            fiat_amount = float(order.fiat_amount)
            fee_fiat = float(order.fee_fiat)

            if order.trade_type == "BUY":
                total_crypto += crypto_amount
                total_cost_fiat += (fiat_amount + fee_fiat)
            elif order.trade_type == "SELL":
                avg_unit_cost = (total_cost_fiat / total_crypto) if total_crypto > 0 else 0.0
                matched_cost_fiat = avg_unit_cost * crypto_amount

                total_crypto = max(0.0, total_crypto - crypto_amount)
                total_cost_fiat = max(0.0, total_cost_fiat - matched_cost_fiat)

                revenue = fiat_amount
                net_profit = revenue - matched_cost_fiat - fee_fiat
                bcv_rate = float(order.bcv_rate) if order.bcv_rate else 1.0
                rate = bcv_rate if bcv_rate > 0 else 1.0
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
                ))

        return results
