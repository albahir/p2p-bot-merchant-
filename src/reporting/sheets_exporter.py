"""Exportador de métricas y datos de órdenes hacia Google Sheets."""

import logging
from typing import Any

from src.reporting.tax_engine import TradeResult

logger = logging.getLogger("sheets_exporter")


class SheetsExporter:
    """Exportador para sincronización remota con Google Sheets."""

    def __init__(self, credentials_path: str = "config/google_credentials.json"):
        self.credentials_path = credentials_path

    def export(self, sheet_id: str, results: list[TradeResult]) -> bool:
        """Exporta los resultados a una hoja remota de cálculo."""
        try:
            import gspread
        except ImportError:
            logger.warning("gspread no está instalado. Sincronización omitida.")
            return False
        else:
            try:
                gc = gspread.service_account(filename=self.credentials_path)
                sh = gc.open_by_key(sheet_id)
                worksheet = sh.sheet1
                # Cabeceras
                headers: list[Any] = ["Order", "Crypto", "Revenue VES", "Cost VES", "Profit VES", "Profit USD"]
                data_to_write: list[list[Any]] = [headers]
                for r in results:
                    data_to_write.append([
                        r.order_number,
                        r.crypto_amount,
                        r.total_revenue_fiat,
                        r.acquisition_cost_fiat,
                        r.net_profit_fiat,
                        r.net_profit_usd,
                    ])
                worksheet.clear()
                worksheet.append_rows(data_to_write)
                logger.info("Datos sincronizados a Google Sheets exitosamente.")
                return True
            except (gspread.exceptions.APIError, OSError) as e:
                logger.error(f"Error exportando a Google Sheets: {e}")
                return False
