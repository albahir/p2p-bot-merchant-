"""Tests unitarios (TDD) para el Motor Contable: Libro Diario y Libro Mayor (SPEC-017)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher, Order
from src.reporting.accounting_engine import (
    AccountingEngine,
    LedgerSummary,
)


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_journal_entry_for_buy_order_with_bank_fee():
    db = setup_in_memory_db()
    engine = AccountingEngine(db=db)
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    order = Order(
        order_number="ORD-BUY-500",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=3000.0,
        crypto_amount=60.0,
        unit_price=50.0,
        order_status="COMPLETED",
        created_at=now,
    )

    voucher = BankVoucher(
        id=1,
        bank_name="Banco de Venezuela",
        destination_bank="Banesco",
        reference_number="0102998877",
        amount_ves=3000.0,
        bank_fee_ves=9.0,  # 0.30% comisión interbancaria
        total_debited_ves=3009.0,
        sender_id="V-19456789",
        sender_name="CARLOS PEREZ",
        sender_phone="0414-1234567",
        concept="Compra USDT orden 500",
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        associated_order_number="ORD-BUY-500",
        verification_status="MATCHED",
        voucher_date=now,
    )

    entries = engine.record_p2p_trade(order=order, voucher=voucher)

    # Debe generar 3 líneas contables:
    # 1. DEBE 1.1.05 Activos Cripto USDT: 3000.00
    # 2. DEBE 5.2.01 Gastos Comisiones Bancarias: 9.00
    # 3. HABER 1.1.01 Banco Nacional VES: 3009.00
    assert len(entries) == 3

    total_debe = sum(e.debit for e in entries)
    total_haber = sum(e.credit for e in entries)

    assert round(total_debe, 2) == round(total_haber, 2)
    assert round(total_debe, 2) == 3009.0

    # Verificar que los hashes SHA-256 estén encadenados
    for e in entries:
        assert len(e.entry_hash) == 64
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[2].prev_hash == entries[1].entry_hash


def test_create_journal_entry_for_sell_order():
    db = setup_in_memory_db()
    engine = AccountingEngine(db=db)
    now = datetime(2026, 11, 3, 16, 0, 0, tzinfo=UTC)

    order = Order(
        order_number="ORD-SELL-600",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        fiat_amount=5000.0,
        crypto_amount=100.0,
        unit_price=50.0,
        order_status="COMPLETED",
        created_at=now,
    )

    voucher = BankVoucher(
        id=2,
        bank_name="Mercantil",
        reference_number="0105112233",
        amount_ves=5000.0,
        bank_fee_ves=0.0,  # En recepción la comisión bancaria es 0
        total_debited_ves=5000.0,
        sender_id="V-25667788",
        sender_name="ANA GOMEZ",
        payment_method="PAGO_MOVIL",
        movement_type="CREDIT",
        associated_order_number="ORD-SELL-600",
        verification_status="MATCHED",
        voucher_date=now,
    )

    entries = engine.record_p2p_trade(order=order, voucher=voucher)

    assert len(entries) == 2
    total_debe = sum(e.debit for e in entries)
    total_haber = sum(e.credit for e in entries)

    assert round(total_debe, 2) == round(total_haber, 2)
    assert round(total_debe, 2) == 5000.0

    # Línea 1: DEBE Banco VES: 5000.0
    assert entries[0].account_code == "1.1.01"
    assert entries[0].debit == 5000.0

    # Línea 2: HABER Activos USDT: 5000.0
    assert entries[1].account_code == "1.1.05"
    assert entries[1].credit == 5000.0


def test_ledger_monthly_calculation_and_chaining():
    db = setup_in_memory_db()
    engine = AccountingEngine(db=db)
    t0 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)

    # 1. Compra de 2,000 VES con fee de 6 VES (Total debited 2006)
    o1 = Order(
        order_number="ORD-B1",
        trade_type="BUY",
        fiat_amount=2000.0,
        crypto_amount=40.0,
        created_at=t0,
    )
    v1 = BankVoucher(
        bank_name="BDV",
        amount_ves=2000.0,
        bank_fee_ves=6.0,
        movement_type="DEBIT",
        payment_method="PAGO_MOVIL",
        voucher_date=t0,
    )
    engine.record_p2p_trade(order=o1, voucher=v1)

    # 2. Venta de 3,500 VES (0 fee)
    o2 = Order(
        order_number="ORD-S1",
        trade_type="SELL",
        fiat_amount=3500.0,
        crypto_amount=70.0,
        created_at=t0 + timedelta(days=1),
    )
    v2 = BankVoucher(
        bank_name="BDV",
        amount_ves=3500.0,
        bank_fee_ves=0.0,
        movement_type="CREDIT",
        payment_method="PAGO_MOVIL",
        voucher_date=t0 + timedelta(days=1),
    )
    engine.record_p2p_trade(order=o2, voucher=v2)

    # Calcular Libro Mayor para Noviembre 2026 con saldo inicial 10,000 VES
    ledger_ves: LedgerSummary = engine.calculate_ledger_for_account(
        account_code="1.1.01",
        year=2026,
        month=11,
        initial_balance=10000.0,
    )

    # Saldo Inicial: 10,000
    # Debe (ingresos por venta): +3,500
    # Haber (egresos compra + fee): -2,006
    # Saldo Final: 10,000 + 3,500 - 2,006 = 11,494.00
    assert ledger_ves.initial_balance == 10000.0
    assert ledger_ves.total_debit == 3500.0
    assert ledger_ves.total_credit == 2006.0
    assert round(ledger_ves.final_balance, 2) == 11494.0
