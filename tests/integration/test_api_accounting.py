"""Pruebas de integración para los controladores de contabilidad y reconciliación (SPEC-017).

Prueba directamente los controladores de las rutas de FastAPI garantizando
validación de esquemas, respuestas de base de datos y partida doble sin bloqueos
de sockets en el sandbox de Windows.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routes.accounting import (
    MatchVoucherRequest,
    export_accounting_excel,
    export_accounting_pdf,
    get_journal_entries,
    get_ledger_summaries,
    match_voucher_with_order,
)
from src.data.database import Base
from src.data.models import BankVoucher, JournalEntry, Order, User


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def current_trader():
    return User(
        id=1,
        username="trader_acct",
        password_hash="dummy_hash",
        role="TRADER",
        is_active=True,
    )


def test_get_journal_entries_empty_and_populated(test_db, current_trader):
    # 1. Vacío
    entries = get_journal_entries(db=test_db, current_user=current_trader)
    assert entries == []

    # 2. Poblar con un asiento contable
    now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC)
    entry = JournalEntry(
        entry_number=1,
        date_time=now,
        account_code="1.1.01",
        account_name="Banco VES",
        debit=1500.0,
        credit=0.0,
        reference="REF-9988",
        description="Ingreso P2P",
        entry_hash="h" * 64,
    )
    test_db.add(entry)
    test_db.commit()

    entries_pop = get_journal_entries(db=test_db, current_user=current_trader)
    assert len(entries_pop) == 1
    assert entries_pop[0].account_code == "1.1.01"
    assert entries_pop[0].debit == 1500.0


def test_get_ledger_monthly_summary(test_db, current_trader):
    summaries = get_ledger_summaries(
        db=test_db,
        current_user=current_trader,
        year=2026,
        month=11,
    )
    assert isinstance(summaries, list)
    assert len(summaries) >= 4  # Core accounts (Banco VES, USDT, Comisiones)


def test_export_excel_and_pdf(test_db, current_trader):
    # Excel
    resp_excel = export_accounting_excel(
        db=test_db,
        current_user=current_trader,
        year=2026,
        month=11,
    )
    assert resp_excel.path is not None
    assert resp_excel.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # PDF
    resp_pdf = export_accounting_pdf(
        db=test_db,
        current_user=current_trader,
        year=2026,
        month=11,
    )
    assert resp_pdf.path is not None
    assert resp_pdf.media_type == "application/pdf"
    with open(resp_pdf.path, "rb") as f:
        data = f.read()
        assert data.startswith(b"%PDF-")


def test_manual_voucher_match(test_db, current_trader):
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)
    order = Order(
        order_number="ORD-MATCH-API",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=2000.0,
        crypto_amount=40.0,
        unit_price=50.0,
        order_status="COMPLETED",
        created_at=now,
    )
    voucher = BankVoucher(
        bank_name="Banco de Venezuela",
        reference_number="0102123456",
        amount_ves=2000.0,
        bank_fee_ves=6.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        verification_status="UNMATCHED",
        voucher_date=now,
    )
    test_db.add(order)
    test_db.add(voucher)
    test_db.commit()
    test_db.refresh(voucher)

    payload = MatchVoucherRequest(order_number="ORD-MATCH-API")
    res = match_voucher_with_order(
        voucher_id=voucher.id,
        payload=payload,
        db=test_db,
        current_user=current_trader,
    )

    assert res["status"] == "MATCHED"
    assert res["associated_order_number"] == "ORD-MATCH-API"
    assert res["journal_entries_created"] == 3

    # Verificar que los asientos se reflejan en get_journal_entries
    journal = get_journal_entries(db=test_db, current_user=current_trader)
    assert len(journal) == 3
