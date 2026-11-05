"""Tests unitarios (TDD) para la reconciliación automática de comprobantes desfasados/huérfanos (T18.4)."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher, Order
from src.integrations.receipt_ocr import BankReceiptOCR


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_reconcile_orphan_vouchers_delayed_upload():
    db = setup_in_memory_db()
    ocr = BankReceiptOCR()

    # Escenario:
    # A las 10:00 AM el usuario sube un comprobante por OCR antes de que la orden aparezca en Binance.
    orphan_voucher = BankVoucher(
        bank_name="Banco de Venezuela",
        reference_number="REF-998877",
        amount_ves=3500.0,
        bank_fee_ves=0.0,
        total_debited_ves=3500.0,
        payment_method="PAGO_MOVIL",
        movement_type="CREDIT",
        associated_order_number=None,
        verification_status="UNMATCHED",
        voucher_date=datetime(2026, 11, 4, 10, 0, 0, tzinfo=UTC),
    )
    db.add(orphan_voucher)
    db.commit()

    # Más tarde a las 2:00 PM, se sincronizan las órdenes de Binance del día
    matched_order = Order(
        order_number="ORD-MATCH-3500",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        unit_price=50.0,
        crypto_amount=70.0,
        fiat_amount=3500.0,
        order_status="COMPLETED",
        counterparty_name="Comprador Tardío",
        created_at=datetime(2026, 11, 4, 10, 2, 0, tzinfo=UTC),
    )
    db.add(matched_order)
    db.commit()

    # Ejecutar reconciliación de huérfanos
    reconciled_count = ocr.reconcile_orphan_vouchers(db=db, tolerance_hours=24)

    assert reconciled_count == 1
    db.refresh(orphan_voucher)
    assert orphan_voucher.verification_status == "MATCHED"
    assert orphan_voucher.associated_order_number == "ORD-MATCH-3500"


def test_api_reconcile_orphans_endpoint():
    from src.api.routes.accounting import reconcile_orphan_vouchers_endpoint
    from src.data.models import User

    db = setup_in_memory_db()
    trader = User(username="reconcile_trader", password_hash="pass", role="TRADER")
    db.add(trader)
    db.commit()

    res = reconcile_orphan_vouchers_endpoint(
        db=db,
        current_user=trader,
        tolerance_hours=48,
    )

    assert "reconciled_count" in res
    assert res["status"] == "SUCCESS"

