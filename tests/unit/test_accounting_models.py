"""Tests unitarios (TDD) para modelos de datos contables y repositorios (SPEC-017)."""

import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher, BCVRateHistory, JournalEntry, Order
from src.data.repositories import (
    BankVoucherRepository,
    BCVHistoryRepository,
    JournalEntryRepository,
)


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_bank_voucher_enhanced_fields():
    db = setup_in_memory_db()
    repo = BankVoucherRepository(db)

    voucher = BankVoucher(
        bank_name="BANCO DE VENEZUELA",
        destination_bank="BANESCO",
        reference_number="0102948271",
        amount_ves=2500.00,
        bank_fee_ves=7.50,
        total_debited_ves=2507.50,
        sender_id="V-19456789",
        sender_name="CARLOS PEREZ",
        sender_phone="0414-1234567",
        concept="PAGO ORDEN 20489",
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        reconciliation_score=95.0,
        voucher_date=datetime(2026, 11, 3, 14, 30, tzinfo=UTC),
    )

    saved = repo.create(voucher)
    assert saved.id is not None
    assert saved.destination_bank == "BANESCO"
    assert saved.concept == "PAGO ORDEN 20489"
    assert saved.sender_phone == "0414-1234567"
    assert saved.bank_fee_ves == 7.50
    assert saved.total_debited_ves == 2507.50
    assert saved.payment_method == "PAGO_MOVIL"
    assert saved.movement_type == "DEBIT"
    assert saved.reconciliation_score == 95.0


def test_order_enhanced_fields():
    db = setup_in_memory_db()
    order = Order(
        order_number="204891823901",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=2500.00,
        crypto_amount=59.80,
        unit_price=41.80,
        order_status="COMPLETED",
        counterparty_name="carlos_cripto",
        created_at=datetime(2026, 11, 3, 14, 25, tzinfo=UTC),
        completed_at=datetime(2026, 11, 3, 14, 35, tzinfo=UTC),
        payment_method="Banesco",
    )
    db.add(order)
    db.commit()

    saved = db.query(Order).filter(Order.order_number == "204891823901").first()
    assert saved is not None
    assert saved.completed_at is not None
    assert saved.completed_at.strftime("%Y-%m-%d %H:%M") == "2026-11-03 14:35"
    assert saved.payment_method == "Banesco"


def test_bcv_rate_history_repository():
    db = setup_in_memory_db()
    repo = BCVHistoryRepository(db)

    # Insertar tasa
    rate_item = BCVRateHistory(
        fecha_valor=date(2026, 11, 3),
        usd_rate=41.80,
        eur_rate=45.20,
        source="BCV_OFFICIAL",
    )
    repo.upsert_rate(rate_item)

    # Consultar
    fetched = repo.get_rate_by_date(date(2026, 11, 3))
    assert fetched is not None
    assert fetched.usd_rate == 41.80
    assert fetched.eur_rate == 45.20

    # Upsert actualizar
    updated_item = BCVRateHistory(
        fecha_valor=date(2026, 11, 3),
        usd_rate=41.85,
        eur_rate=45.30,
        source="BCV_OFFICIAL_REVISED",
    )
    repo.upsert_rate(updated_item)
    refetched = repo.get_rate_by_date(date(2026, 11, 3))
    assert refetched is not None
    assert refetched.usd_rate == 41.85


def test_journal_entry_repository_and_hash():
    db = setup_in_memory_db()
    repo = JournalEntryRepository(db)

    prev_hash = "0" * 64
    payload = f"1|2026-11-03 14:30:00|1.1.01|BANCO VES|2500.0|0.0|0102948271|{prev_hash}"
    entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    entry = JournalEntry(
        entry_number=1,
        date_time=datetime(2026, 11, 3, 14, 30, tzinfo=UTC),
        account_code="1.1.01",
        account_name="BANCO CUENTA CORRIENTE",
        debit=2500.0,
        credit=0.0,
        reference="0102948271",
        description="Cobro Venta P2P",
        voucher_id=1,
        order_number="204891823901",
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )

    saved = repo.create_entry(entry)
    assert saved.id is not None
    assert saved.entry_number == 1
    assert saved.debit == 2500.0
    assert saved.credit == 0.0
    assert saved.entry_hash == entry_hash

    entries = repo.list_entries(start_date=datetime(2026, 11, 1), end_date=datetime(2026, 11, 30))
    assert len(entries) == 1
