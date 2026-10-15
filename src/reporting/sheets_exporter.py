"""Exportador de métricas y datos de órdenes hacia Google Sheets."""

import logging

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
            gc = gspread.service_account(filename=self.credentials_path)
            sh = gc.open_by_key(sheet_id)
            worksheet = sh.sheet1
            # Cabeceras
            headers = ["Order", "Crypto", "Revenue VES", "Cost VES", "Profit VES", "Profit USD"]
            rows = [
                [r.order_number, r.crypto_amount, r.total_revenue_fiat, r.acquisition_cost_fiat, r.net_profit_fiat, r.net_profit_usd]
                for r in results
            ]
            worksheet.clear()
            worksheet.append_rows([headers] + rows)
            logger.info("Datos sincronizados a Google Sheets exitosamente.")
            return True
        except ImportError:
            logger.warning("gspread no está instalado. Sincronización omitida.")
            return False
        except Exception as e:
            logger.error(f"Error exportando a Google Sheets: {e}")
            return False
