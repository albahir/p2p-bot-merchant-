"""Prueba de extremo a extremo (E2E) simulando ciclo de ingesta, cálculo fiscal y auditoría."""

from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.database import Base
from src.data.models import Order
from src.data.repositories import OrderRepository
from src.reporting.tax_engine import FIFOCostMethod
from src.security.audit_logger import AuditLogger

def test_full_p2p_tax_and_audit_cycle():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # 1. Auditoría de inicio
    audit = AuditLogger(db_session_factory=session_factory)
    audit.log("STARTUP", "SYSTEM", "127.0.0.1", "SUCCESS")

    # 2. Registrar órdenes simuladas de Binance
    db = session_factory()
    repo = OrderRepository(db)
    repo.create(Order(
        order_number="E2E_01",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=3600.0,
        crypto_amount=100.0,
        unit_price=36.0,
        fee_fiat=0.0,
        bcv_rate=36.0,
        order_status="COMPLETED",
        created_at=datetime.now(timezone.utc)
    ))
    repo.create(Order(
        order_number="E2E_02",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=3800.0,
        crypto_amount=100.0,
        unit_price=38.0,
        fee_fiat=0.0,
        bcv_rate=36.0,
        order_status="COMPLETED",
        created_at=datetime.now(timezone.utc)
    ))

    completed_orders = repo.list_completed()
    db.close()

    # 3. Procesamiento fiscal FIFO
    fifo = FIFOCostMethod()
    results = fifo.process_orders(completed_orders)

    assert len(results) == 1
    assert results[0].net_profit_fiat == 200.0
