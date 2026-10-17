"""Generador de informes fiscales en formato Excel (.xlsx).
Incluye dos hojas:
1. 'Detalle': Operaciones de venta con desglose de costo, ingreso, comisiones y ganancia.
2. 'Resumen': Totales consolidados en VES y USD para declaración de ISLR.
"""


import pandas as pd

from src.reporting.tax_engine import TradeResult


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
            {"Métrica": "Ganancia Neta Estimada (USD)", "Valor": total_profit_usd}
        ]
        df_summary = pd.DataFrame(summary_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_detail.to_excel(writer, sheet_name="Detalle", index=False)
            df_summary.to_excel(writer, sheet_name="Resumen", index=False)

        return output_path
