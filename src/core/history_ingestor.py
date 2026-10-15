"""Ingesta y sincronización periódica del histórico de órdenes de Binance P2P.
Persiste las transacciones en PostgreSQL/SQLite local para conservar el histórico fiscal
más allá de la ventana de 6 meses de Binance.
"""

import logging
from datetime import UTC, datetime

from src.core.binance_client import BinanceP2PClient
from src.data.database import SessionLocal
from src.data.models import Order
from src.data.repositories import OrderRepository

logger = logging.getLogger("history_ingestor")


class HistoryIngestor:
    """Sincronizador de historial P2P hacia la base de datos local."""

    def __init__(self, client: BinanceP2PClient, db_session_factory=SessionLocal):
        self.client = client
        self.session_factory = db_session_factory

    def ingest_recent_orders(self, trade_type: str = "ALL", days_back: int = 7) -> int:
        """Descarga órdenes de los últimos N días y las inserta de forma idempotente.
        Soporta trade_type='BUY', 'SELL' o 'ALL' (descarga ambos sentidos).
        """
        if trade_type.upper() == "ALL":
            count_buy = self._ingest_by_type("BUY", days_back)
            count_sell = self._ingest_by_type("SELL", days_back)
            return count_buy + count_sell
        return self._ingest_by_type(trade_type, days_back)

    def _ingest_by_type(self, trade_type: str, days_back: int) -> int:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        start_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)

        response = self.client.get_order_history(
            trade_type=trade_type,
            start_timestamp=start_ms,
            end_timestamp=now_ms
        )

        # Soportar tanto modelo Pydantic como diccionario crudo
        if hasattr(response, "data"):
            order_items = response.data
        elif isinstance(response, dict):
            order_items = response.get("data", [])
        else:
            order_items = []

        if not order_items:
            logger.info(f"No se encontraron órdenes {trade_type} en el período consultado.")
            return 0

        inserted_count = 0
        db = self.session_factory()
        try:
            repo = OrderRepository(db)
            for item in order_items:
                if isinstance(item, dict):
                    order_num = str(item.get("orderNumber"))
                    existing = repo.get_by_order_number(order_num)
                    if not existing:
                        c_time_ms = item.get("createTime", now_ms)
                        created_dt = datetime.fromtimestamp(c_time_ms / 1000, tz=UTC)
                        raw_type = item.get("tradeType", trade_type)
                        t_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
                        asset_str = str(item.get("asset", "USDT"))
                        fiat_str = str(item.get("fiat", "VES"))
                        fiat_amt = float(item.get("totalPrice", 0.0))
                        crypto_amt = float(item.get("amount", 0.0))
                        u_price = float(item.get("unitPrice", 0.0))
                        raw_status = item.get("orderStatus", "COMPLETED")
                        status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                        fee_val = float(item.get("commission") or item.get("takerCommission") or 0.0)
                        from src.reporting.bcv_service import BCVService
                        bcv_val = BCVService().fetch_current_rate()
                        order = Order(
                            order_number=order_num,
                            trade_type=t_type,
                            asset=asset_str,
                            fiat=fiat_str,
                            fiat_amount=fiat_amt,
                            crypto_amount=crypto_amt,
                            unit_price=u_price,
                            fee_fiat=fee_val,
                            fee_crypto=0.0,
                            bcv_rate=bcv_val,
                            order_status=status_str,
                            created_at=created_dt,
                        )
                        repo.create(order)
                        inserted_count += 1
                else:
                    order_num = str(item.orderNumber)
                    existing = repo.get_by_order_number(order_num)
                    if not existing:
                        c_time_ms = item.createTime
                        created_dt = datetime.fromtimestamp(c_time_ms / 1000, tz=UTC)
                        raw_type = item.tradeType
                        t_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
                        asset_str = str(item.asset)
                        fiat_str = str(item.fiat)
                        fiat_amt = float(item.totalPrice)
                        crypto_amt = float(item.amount)
                        u_price = float(item.unitPrice)
                        raw_status = item.orderStatus
                        status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                        fee_val = float(item.fee_decimal if hasattr(item, "fee_decimal") else 0.0)
                        from src.reporting.bcv_service import BCVService
                        bcv_val = BCVService().fetch_current_rate()
                        order = Order(
                            order_number=order_num,
                            trade_type=t_type,
                            asset=asset_str,
                            fiat=fiat_str,
                            fiat_amount=fiat_amt,
                            crypto_amount=crypto_amt,
                            unit_price=u_price,
                            fee_fiat=fee_val,
                            fee_crypto=0.0,
                            bcv_rate=bcv_val,
                            order_status=status_str,
                            created_at=created_dt,
                        )
                        repo.create(order)
                        inserted_count += 1
            logger.info(f"Ingesta {trade_type} completada: {inserted_count} órdenes nuevas registradas.")
            return inserted_count
        finally:
            db.close()
