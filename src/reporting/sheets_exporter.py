"""Exportador de métricas y datos de órdenes hacia Google Sheets."""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from src.reporting.tax_engine import TradeResult

try:
    import gspread
    from gspread.exceptions import GSpreadException
except ImportError:
    gspread = None  # type: ignore[assignment]
    GSpreadException = Exception  # type: ignore[misc, assignment]

logger = logging.getLogger("sheets_exporter")


class SheetsExporter:
    """Exportador para sincronización remota con Google Sheets (Multi-Pestaña)."""

    def __init__(
        self,
        credentials_path: str = "config/google_credentials.json",
        credentials_json: str | dict[str, Any] | None = None,
    ):
        self.credentials_path = credentials_path
        self.credentials_json = credentials_json
        self.last_error: str | None = None
        self.client_email: str | None = None
        self._extract_client_email()

    def _extract_client_email(self) -> None:
        """Extrae el email de la cuenta de servicio si está disponible."""
        try:
            if self.credentials_json:
                if isinstance(self.credentials_json, str):
                    data = json.loads(self.credentials_json)
                else:
                    data = self.credentials_json
                self.client_email = data.get("client_email")
            elif os.path.exists(self.credentials_path):
                with open(self.credentials_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.client_email = data.get("client_email")
        except (json.JSONDecodeError, OSError, TypeError):
            pass

    def _get_client(self) -> Any:
        """Obtiene una instancia autenticada de gspread de manera segura."""
        if gspread is None:
            self.last_error = "El paquete 'gspread' no está instalado en el entorno."
            logger.warning(self.last_error)
            return None

        try:
            if self.credentials_json:
                if isinstance(self.credentials_json, str):
                    creds_dict = json.loads(self.credentials_json)
                else:
                    creds_dict = self.credentials_json
                return gspread.service_account_from_dict(creds_dict)

            if os.path.exists(self.credentials_path):
                return gspread.service_account(filename=self.credentials_path)

            self.last_error = (
                "Credenciales no encontradas: Define la variable 'GOOGLE_SERVICE_ACCOUNT_JSON' "
                "o coloca el archivo en 'config/google_credentials.json'."
            )
            logger.warning(self.last_error)
            return None
        except (GSpreadException, OSError, ValueError, TypeError, KeyError) as e:
            self.last_error = f"Error en credenciales de Google: {e}"
            logger.error(f"Error inicializando cliente de Google Sheets: {e}")
            return None

    def _get_or_create_worksheet(self, sh: Any, title: str, rows: int = 100, cols: int = 20) -> Any:
        """Busca una pestaña por título o la crea si no existe."""
        for ws in sh.worksheets():
            if ws.title == title:
                return ws
        return sh.add_worksheet(title=title, rows=rows, cols=cols)

    def export(self, sheet_id: str, results: list[TradeResult]) -> bool:
        """Exporta los resultados a una hoja remota de cálculo con formato multi-pestaña."""
        if not sheet_id:
            self.last_error = "No se configuró 'GOOGLE_SHEET_ID' para la exportación."
            logger.warning(self.last_error)
            return False

        client = self._get_client()
        if client is None:
            return False

        try:
            sh = client.open_by_key(sheet_id)

            # 1. Pestaña: Detalle Fiscal
            ws_detalle = self._get_or_create_worksheet(sh, "Detalle Fiscal", rows=max(100, len(results) + 10), cols=15)
            headers_detalle: list[Any] = [
                "Fecha y Hora (UTC)",
                "Orden",
                "Tipo",
                "Cripto (USDT)",
                "Precio Venta (VES)",
                "Ingreso Total (VES)",
                "Costo Adquisición (VES)",
                "Comisión (VES)",
                "Tasa BCV",
                "Ganancia Neta (VES)",
                "Ganancia Neta (USD)",
            ]
            data_detalle: list[list[Any]] = [headers_detalle]
            for r in results:
                date_str = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "-"
                data_detalle.append([
                    date_str,
                    r.order_number,
                    r.trade_type,
                    round(r.crypto_amount, 4),
                    round(r.sell_price_fiat, 2),
                    round(r.total_revenue_fiat, 2),
                    round(r.acquisition_cost_fiat, 2),
                    round(r.fee_fiat, 2),
                    round(r.bcv_rate, 4),
                    round(r.net_profit_fiat, 2),
                    round(r.net_profit_usd, 2),
                ])

            ws_detalle.clear()
            ws_detalle.append_rows(data_detalle)

            # 2. Pestaña: Resumen Ejecutivo
            ws_resumen = self._get_or_create_worksheet(sh, "Resumen Ejecutivo", rows=30, cols=5)
            total_crypto = sum(r.crypto_amount for r in results)
            total_revenue = sum(r.total_revenue_fiat for r in results)
            total_cost = sum(r.acquisition_cost_fiat for r in results)
            total_fees = sum(r.fee_fiat for r in results)
            total_profit_ves = sum(r.net_profit_fiat for r in results)
            total_profit_usd = sum(r.net_profit_usd for r in results)
            margin_pct = (total_profit_ves / total_revenue * 100.0) if total_revenue > 0 else 0.0

            sync_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

            headers_resumen: list[Any] = ["Métrica", "Valor"]
            data_resumen: list[list[Any]] = [
                headers_resumen,
                ["Órdenes Procesadas", len(results)],
                ["Volumen USDT Vendido", round(total_crypto, 2)],
                ["Ingreso Total (VES)", round(total_revenue, 2)],
                ["Costo Total Adquisición (VES)", round(total_cost, 2)],
                ["Comisiones Totales (VES)", round(total_fees, 2)],
                ["Ganancia Neta Consolidada (VES)", round(total_profit_ves, 2)],
                ["Ganancia Neta Consolidada (USD)", round(total_profit_usd, 2)],
                ["Margen Operativo Neto (%)", f"{margin_pct:.2f}%"],
                ["Última Sincronización", sync_timestamp],
            ]

            ws_resumen.clear()
            ws_resumen.append_rows(data_resumen)

            logger.info(f"Google Sheets '{sheet_id}' sincronizado exitosamente con 2 pestañas.")
            self.last_error = None
            return True
        except (GSpreadException, OSError, ValueError, TypeError, KeyError) as e:
            err_str = str(e)
            if "403" in err_str or "PERMISSION_DENIED" in err_str or "caller does not have permission" in err_str:
                email_hint = f" ({self.client_email})" if self.client_email else ""
                self.last_error = (
                    f"Permiso denegado (HTTP 403). Abre tu Google Sheet, presiona 'Compartir' "
                    f"y agrega a la cuenta de servicio{email_hint} con rol de 'Editor'."
                )
            elif "404" in err_str or "SpreadsheetNotFound" in err_str:
                self.last_error = f"Hoja no encontrada (HTTP 404). Verifica que el GOOGLE_SHEET_ID '{sheet_id}' sea correcto."
            elif "API has not been used" in err_str or "SERVICE_DISABLED" in err_str:
                self.last_error = "Google Sheets API o Google Drive API no están habilitadas en tu Google Cloud Console."
            else:
                self.last_error = f"Error exportando a Google Sheets: {e}"

            logger.error(self.last_error)
            return False

    @staticmethod
    def get_sheet_url(sheet_id: str) -> str:
        """Devuelve el enlace directo al documento en Google Sheets."""
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
