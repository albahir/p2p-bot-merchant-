"""Script de generación de datos de prueba para desarrollo local.
"""

import logging
from datetime import datetime, timezone
from src.data.database import SessionLocal
from src.data.models import Order

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_data")

def main():
    logger.info("Insertando órdenes de prueba para validación fiscal y dashboard...")
    db = SessionLocal()
    try:
        sample_orders = [
            Order(
                order_number="ORDER_TEST_001",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=3650.0,
                crypto_amount=100.0,
                unit_price=36.5,
                bcv_rate=36.5,
                fee_fiat=0.0,
                order_status="COMPLETED",
                created_at=datetime.now(timezone.utc)
            ),
            Order(
                order_number="ORDER_TEST_002",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                fiat_amount=1875.0,
                crypto_amount=50.0,
                unit_price=37.5,
                bcv_rate=36.5,
                fee_fiat=5.0,
                order_status="COMPLETED",
                created_at=datetime.now(timezone.utc)
            )
        ]
        db.add_all(sample_orders)
        db.commit()
        logger.info(f"Insertadas {len(sample_orders)} órdenes de prueba con éxito.")
    except Exception as e:
        logger.error(f"Error al sembrar datos: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
