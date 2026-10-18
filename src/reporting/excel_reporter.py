"""Generador de informes fiscales en formato Excel (.xlsx).
Incluye soporte para informes de 2 pestañas (Detalle y Resumen) e informes
completos de Reconstrucción Fiscal de 4 pestañas:
1. 'Resumen Fiscal': Reconstrucción de 6 piezas, patrimonio y liquidación ISLR.
2. 'Detalle P2P': Órdenes C2C ejecutadas con precios, costos y márgenes.
3. 'Depósitos y Retiros': Movimientos on-chain de criptoactivos.
4. 'Conciliación Bancaria': Comprobantes en bolívares conciliados con órdenes.
"""

from typing import TYPE_CHECKING

import pandas as pd

from src.data.models import BankVoucher, Order, WalletMovement
from src.reporting.tax_engine import TradeResult

if TYPE_CHECKING:
    from src.reporting.fiscal_reconciler import FiscalReconciliationResult


class ExcelReporter:
    """Generador de hojas de cálculo de auditoría fiscal."""

    @staticmethod
    def generate_tax_report(results: list[TradeResult], output_path: str) -> str:
        """Crea el archivo Excel con las dos pestañas especificadas en Spec 005."""
        if not results:
            detail_data = []
        else:
            detail_data = [
                {
                    "Fecha y Hora (UTC)": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "-",
                    "Número de Orden": r.order_number,
                    "Tipo": r.trade_type,
                    "Cripto (USDT)": r.crypto_amount,
                    "Precio Venta (VES)": r.sell_price_fiat,
                    "Ingreso Bruto (VES)": r.total_revenue_fiat,
                    "Costo Adquisición (VES)": r.acquisition_cost_fiat,
                    "Comisión (VES)": r.fee_fiat,
                    "Ganancia Neta (VES)": r.net_profit_fiat,
                    "Tasa BCV": r.bcv_rate,
                    "Ganancia Neta (USD)": r.net_profit_usd,
                }
                for r in results
            ]

        df_detail = pd.DataFrame(detail_data)

        total_revenue_ves = sum(r.total_revenue_fiat for r in results)
        total_cost_ves = sum(r.acquisition_cost_fiat for r in results)
        total_fees_ves = sum(r.fee_fiat for r in results)
        total_profit_ves = sum(r.net_profit_fiat for r in results)
        total_profit_usd = sum(r.net_profit_usd for r in results)

        summary_data = [
            {"Métrica": "Total Operaciones de Venta", "Valor": len(results)},
            {"Métrica": "Ingresos Brutos Totales (VES)", "Valor": total_revenue_ves},
            {"Métrica": "Costo de Adquisición Total (VES)", "Valor": total_cost_ves},
            {"Métrica": "Comisiones Pagadas (VES)", "Valor": total_fees_ves},
            {"Métrica": "Ganancia Neta Gravable (VES)", "Valor": total_profit_ves},
            {"Métrica": "Ganancia Neta Estimada (USD)", "Valor": total_profit_usd},
        ]
        df_summary = pd.DataFrame(summary_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_detail.to_excel(writer, sheet_name="Detalle", index=False)
            df_summary.to_excel(writer, sheet_name="Resumen", index=False)

        return output_path

    @staticmethod
    def generate_fiscal_reconstruction_report(
        reconciliation: "FiscalReconciliationResult",
        p2p_orders: list[Order],
        wallet_movements: list[WalletMovement],
        vouchers: list[BankVoucher],
        output_path: str,
    ) -> str:
        """Crea el informe fiscal integral de 4 pestañas para auditorías tributarias."""
        summary_rows = [
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Período Fiscal", "Valor": reconciliation.period},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "1. Saldo Inicial (USDT)", "Valor": reconciliation.initial_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "2. Entradas - Depósitos On-chain (USDT)", "Valor": reconciliation.inflows_deposits},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "2. Entradas - Compras P2P (USDT)", "Valor": reconciliation.inflows_p2p_buys},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Total Entradas Cripto (USDT)", "Valor": reconciliation.total_inflows},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "3. Salidas - Retiros On-chain (USDT)", "Valor": reconciliation.outflows_withdrawals},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "3. Salidas - Ventas P2P (USDT)", "Valor": reconciliation.outflows_p2p_sells},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Total Salidas Cripto (USDT)", "Valor": reconciliation.total_outflows},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "4. Volumen Operado Total (USDT)", "Valor": reconciliation.volume_operated},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "5. Comisiones de Red / Costos (USDT)", "Valor": reconciliation.total_fees},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "6. Saldo Final Calculado Teórico (USDT)", "Valor": reconciliation.calculated_final_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "6. Saldo Final Real / Snapshot (USDT)", "Valor": reconciliation.actual_final_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Discrepancia / Merma (USDT)", "Valor": reconciliation.discrepancy},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Estatus Consistencia Patrimonial", "Valor": reconciliation.status},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ingresos Brutos por Ventas (VES)", "Valor": reconciliation.gross_revenue_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Costos de Adquisición FIFO (VES)", "Valor": reconciliation.acquisition_cost_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ganancia Neta Gravable (VES)", "Valor": reconciliation.net_profit_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ganancia Neta Estimada (USD)", "Valor": reconciliation.net_profit_usd},
            {"Sección": "3. Auditoría Bancaria", "Concepto / Métrica": "Comprobantes Bancarios Procesados", "Valor": reconciliation.vouchers_count},
            {"Sección": "3. Auditoría Bancaria", "Concepto / Métrica": "Comprobantes Auto-Conciliados", "Valor": reconciliation.matched_vouchers_count},
        ]
        df_summary = pd.DataFrame(summary_rows)

        p2p_data = [
            {
                "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "-",
                "Número de Pedido": o.order_number,
                "Tipo": o.trade_type,
                "Activo": o.asset,
                "Cripto": o.crypto_amount,
                "Precio Unitario": o.unit_price,
                "Moneda Fiat": o.fiat,
                "Monto Fiat": o.fiat_amount,
                "Comisión": o.fee_fiat,
                "Tasa BCV": o.bcv_rate,
                "Estado": o.order_status,
            }
            for o in p2p_orders
        ]
        df_p2p = pd.DataFrame(p2p_data)

        movs_data = [
            {
                "Fecha (UTC)": m.timestamp.strftime("%Y-%m-%d %H:%M:%S") if m.timestamp else "-",
                "Tipo Movimiento": m.movement_type,
                "Activo": m.asset,
                "Monto": m.amount,
                "Comisión Red": m.fee,
                "Red": m.network or "-",
                "TXID": m.txid or "-",
                "Dirección": m.address or "-",
                "Estado": m.status,
            }
            for m in wallet_movements
        ]
        df_movs = pd.DataFrame(movs_data)

        vouchers_data = [
            {
                "Fecha": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "-",
                "Banco": v.bank_name,
                "Referencia": v.reference_number,
                "Monto (VES)": v.amount_ves,
                "Cédula/RIF Emisor": v.sender_id or "-",
                "Nombre Titular": v.sender_name or "-",
                "Método Pago": v.payment_method,
                "Orden P2P Vinculada": v.associated_order_number or "-",
                "Estado Verificación": v.verification_status,
            }
            for v in vouchers
        ]
        df_vouchers = pd.DataFrame(vouchers_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="Resumen Fiscal", index=False)
            df_p2p.to_excel(writer, sheet_name="Detalle P2P", index=False)
            df_movs.to_excel(writer, sheet_name="Depósitos y Retiros", index=False)
            df_vouchers.to_excel(writer, sheet_name="Conciliación Bancaria", index=False)

        return output_path
