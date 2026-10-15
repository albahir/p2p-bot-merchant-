"""Ingesta y sincronización periódica del histórico de órdenes de Binance P2P.
Persiste las transacciones en PostgreSQL/SQLite local para conservar el histórico fiscal
más allá de la ventana de 6 meses de Binance.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
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

    def ingest_recent_orders(self, trade_type: str = "BUY", days_back: int = 7) -> int:
        """Descarga órdenes de los últimos N días y las inserta de forma idempotente."""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)

        response = self.client.get_order_history(
            trade_type=trade_type,
            start_timestamp=start_ms,
            end_timestamp=now_ms
        )

        data = response.get("data", [])
        if not isinstance(data, list):
            logger.info("No se encontraron órdenes nuevas en el período consultado.")
            return 0

        inserted_count = 0
        db = self.session_factory()
        try:
            repo = OrderRepository(db)
            for item in data:
                order_number = str(item.get("orderNumber"))
                existing = repo.get_by_order_number(order_number)
                if not existing:
                    created_time_ms = item.get("createTime", now_ms)
                    created_dt = datetime.fromtimestamp(created_time_ms / 1000, tz=timezone.utc)
                    order = Order(
                        order_number=order_number,
                        trade_type=item.get("tradeType", trade_type),
                        asset=item.get("asset", "USDT"),
                        fiat=item.get("fiat", "VES"),
                        fiat_amount=float(item.get("totalPrice", 0.0)),
                        crypto_amount=float(item.get("amount", 0.0)),
                        unit_price=float(item.get("unitPrice", 0.0)),
                        fee_fiat=float(item.get("commission", 0.0)),
                        bcv_rate=0.0,
                        order_status=item.get("orderStatus", "COMPLETED"),
                        created_at=created_dt
                    )
                    repo.create(order)
                    inserted_count += 1
            logger.info(f"Ingesta completada: {inserted_count} órdenes nuevas registradas.")
            return inserted_count
        finally:
            db.close()
