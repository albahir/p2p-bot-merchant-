"""Script de generación de datos de prueba para desarrollo local.
"""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path para ejecuciones directas
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.exc import SQLAlchemyError

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
                fee_crypto=0.0,
                order_status="COMPLETED",
                created_at=datetime.now(UTC)
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
                fee_crypto=0.0,
                order_status="COMPLETED",
                created_at=datetime.now(UTC)
            )
        ]
        db.add_all(sample_orders)
        db.commit()
        logger.info(f"Insertadas {len(sample_orders)} órdenes de prueba con éxito.")
    except SQLAlchemyError as e:
        logger.error(f"Error al sembrar datos: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
