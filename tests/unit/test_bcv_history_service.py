"""Tests unitarios (TDD) para el servicio histórico de tasas BCV con Fecha Valor (SPEC-017)."""

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BCVRateHistory, Order
from src.data.repositories import BCVHistoryRepository
from src.reporting.bcv_history_service import BCVHistoryService


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_fecha_valor_resolution_regular_and_weekend():
    db = setup_in_memory_db()
    repo = BCVHistoryRepository(db)

    # Sembrar tasas
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 10, 30), usd_rate=40.50))  # Viernes
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 11, 2), usd_rate=41.20))   # Lunes
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 11, 3), usd_rate=41.80))   # Martes
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 11, 4), usd_rate=42.50))   # Miércoles

    service = BCVHistoryService(db_session=db)

    # 1. Operación en Martes a las 10:00 AM hora VE (14:00 UTC)
    t1 = datetime(2026, 11, 3, 14, 0, tzinfo=UTC)
    assert service.get_rate_for_timestamp(t1) == 41.80

    # 2. Operación en Martes a las 6:30 PM hora VE (22:30 UTC) - después de publicación del BCV
    t2 = datetime(2026, 11, 3, 22, 30, tzinfo=UTC)
    # Debe ser la tasa de hoy (41.80), no la de mañana (42.50)
    assert service.get_rate_for_timestamp(t2) == 41.80

    # 3. Operación en Sábado 31-Oct a las 8:00 PM hora VE (00:00 UTC del Domingo)
    t_sabado = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)  # 20:00 VE del 31-Oct
    assert service.get_rate_for_timestamp(t_sabado) == 40.50  # Tasa del viernes

    # 4. Operación en Domingo 01-Nov a las 11:00 AM hora VE
    t_domingo = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
    assert service.get_rate_for_timestamp(t_domingo) == 40.50  # Tasa del viernes

    # 5. Operación en Miércoles 04-Nov a las 00:05 AM hora VE (04:05 UTC)
    t_miercoles = datetime(2026, 11, 4, 4, 5, tzinfo=UTC)
    assert service.get_rate_for_timestamp(t_miercoles) == 42.50


def test_backfill_historical_orders():
    db = setup_in_memory_db()
    repo = BCVHistoryRepository(db)

    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 10, 30), usd_rate=40.50))
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 11, 2), usd_rate=41.20))
    repo.upsert_rate(BCVRateHistory(fecha_valor=date(2026, 11, 3), usd_rate=41.80))

    orders = [
        Order(
            order_number="ORD-1",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=1000.0,
            crypto_amount=24.5,
            unit_price=40.8,
            order_status="COMPLETED",
            created_at=datetime(2026, 10, 31, 18, 0, tzinfo=UTC),  # Sábado -> BCV 40.50
            bcv_rate=0.0,
        ),
        Order(
            order_number="ORD-2",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=2000.0,
            crypto_amount=48.0,
            unit_price=41.6,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 3, 16, 0, tzinfo=UTC),   # Martes -> BCV 41.80
            bcv_rate=0.0,
        ),
    ]

    service = BCVHistoryService(db_session=db)
    updated_count = service.backfill_orders(orders)

    assert updated_count == 2
    assert orders[0].bcv_rate == 40.50
    assert orders[1].bcv_rate == 41.80
