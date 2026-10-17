"""Servicio de cierre fiscal mensual automatizado y despacho de informes contables a Telegram."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from src.data.repositories import OrderRepository
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.tax_engine import CostMethod, FIFOCostMethod

logger = logging.getLogger("monthly_closer")

MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


class MonthlyFiscalCloser:
    """Generador de cierres contables mensuales con exportación en Excel y entrega por Telegram."""

    def __init__(
        self,
        session_factory: Any,
        notifier: Any | None = None,
        cost_method: CostMethod | None = None,
        output_dir: str = ".",
    ):
        self.session_factory = session_factory
        self.notifier = notifier
        self.cost_method = cost_method or FIFOCostMethod()
        self.output_dir = output_dir

    def execute_close(
        self,
        year: int,
        month: int,
        send_telegram: bool = True,
    ) -> tuple[str | None, dict[str, Any]]:
        """Calcula las métricas de un mes calendario, genera el .xlsx y lo envía opcionalmente a Telegram."""
        if month < 1 or month > 12:
            return None, {"error": "Mes inválido (debe ser entre 1 y 12)"}

        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=UTC)
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        else:
            next_month_start = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=UTC)
        end_dt = next_month_start - timedelta(microseconds=1)

        db = self.session_factory()
        try:
            repo = OrderRepository(db)
            orders = repo.list_completed(start_date=start_dt, end_date=end_dt)
            if not orders:
                logger.info(f"No hay órdenes completadas para el período {year}-{month:02d}.")
                return None, {
                    "total_orders": 0,
                    "message": f"No hay órdenes completadas para {year}-{month:02d}.",
                }

            results = self.cost_method.process_orders(orders)
            if not results:
                logger.info(f"No se generaron resultados gravables para {year}-{month:02d}.")
                return None, {
                    "total_orders": 0,
                    "message": f"No hay operaciones de venta gravables en {year}-{month:02d}.",
                }

            orders_count = len(results)
            crypto_sold = sum(r.crypto_amount for r in results)
            gross_revenue_ves = sum(r.total_revenue_fiat for r in results)
            acquisition_cost_ves = sum(r.acquisition_cost_fiat for r in results)
            fees_ves = sum(r.fee_fiat for r in results)
            net_profit_ves = sum(r.net_profit_fiat for r in results)
            net_profit_usd = sum(r.net_profit_usd for r in results)
            margin_pct = (net_profit_ves / gross_revenue_ves * 100.0) if gross_revenue_ves > 0 else 0.0

            metrics: dict[str, Any] = {
                "year": year,
                "month": month,
                "total_orders": orders_count,
                "crypto_sold": round(crypto_sold, 2),
                "gross_revenue_ves": round(gross_revenue_ves, 2),
                "acquisition_cost_ves": round(acquisition_cost_ves, 2),
                "fees_ves": round(fees_ves, 2),
                "net_profit_fiat": round(net_profit_ves, 2),
                "net_profit_usd": round(net_profit_usd, 2),
                "margin_pct": round(margin_pct, 2),
            }

            os.makedirs(self.output_dir, exist_ok=True)
            output_file = os.path.join(self.output_dir, f"reporte_fiscal_{year}_{month:02d}.xlsx")
            ExcelReporter.generate_tax_report(results, output_file)
            metrics["file_path"] = output_file

            if send_telegram and self.notifier:
                month_name = MONTH_NAMES_ES[month - 1]
                caption = (
                    f"📊 *Cierre Fiscal Mensual — {month_name} {year}*\n\n"
                    f"• Total Órdenes: `{orders_count}`\n"
                    f"• Volumen USDT Vendido: `{crypto_sold:,.2f} USDT`\n"
                    f"• Ingreso Bruto: `{gross_revenue_ves:,.2f} VES`\n"
                    f"• Costo Adquisición: `{acquisition_cost_ves:,.2f} VES`\n"
                    f"• Comisiones: `{fees_ves:,.2f} VES`\n"
                    f"• Ganancia Neta: `{net_profit_ves:,.2f} VES` (`${net_profit_usd:,.2f} USD`)\n"
                    f"• Margen Operativo: `{margin_pct:.2f}%`\n\n"
                    f"📎 *Informe contable auditado en Excel adjunto.*"
                )
                self.notifier.send_document(file_path=output_file, caption=caption)

            logger.info(f"Cierre fiscal de {year}-{month:02d} completado exitosamente: {output_file}")
            return output_file, metrics
        finally:
            db.close()
