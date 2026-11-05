"""Tests unitarios (TDD) para el cálculo de Saldo Teórico Dinámico y Balances Multi-Banco (T18.1)."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher, Order
from src.reporting.accounting_engine import AccountingEngine, LiveBalanceSummary


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_calculate_live_theoretical_balance_single_and_multi_bank():
    db = setup_in_memory_db()
    engine = AccountingEngine(db=db)

    # Simular órdenes completadas
    # 1. Compra P2P: Pagué 5,000 VES de Banco de Venezuela, recibí 100 USDT
    order_buy = Order(
        order_number="ORD-BUY-001",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        unit_price=50.0,
        crypto_amount=100.0,
        fiat_amount=5000.0,
        order_status="COMPLETED",
        counterparty_name="Vendedor A",
        created_at=datetime(2026, 11, 4, 10, 0, 0, tzinfo=UTC),
    )
    # 2. Venta P2P: Recibí 2,750 VES en Banesco, entregué 50 USDT
    order_sell = Order(
        order_number="ORD-SELL-001",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        unit_price=55.0,
        crypto_amount=50.0,
        fiat_amount=2750.0,
        order_status="COMPLETED",
        counterparty_name="Comprador B",
        created_at=datetime(2026, 11, 4, 14, 0, 0, tzinfo=UTC),
    )

    db.add_all([order_buy, order_sell])
    db.commit()

    # Crear comprobantes bancarios conciliados para alimentar el Libro Diario
    voucher_bdv = BankVoucher(
        bank_name="Banco de Venezuela",
        reference_number="REF-001-BDV",
        amount_ves=5000.0,
        bank_fee_ves=0.0,
        total_debited_ves=5000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        associated_order_number=order_buy.order_number,
        verification_status="MATCHED",
        voucher_date=datetime(2026, 11, 4, 10, 5, 0, tzinfo=UTC),
    )
    voucher_banesco = BankVoucher(
        bank_name="Banesco",
        reference_number="REF-002-BANESCO",
        amount_ves=2750.0,
        bank_fee_ves=0.0,
        total_debited_ves=2750.0,
        payment_method="TRANSFERENCIA",
        movement_type="CREDIT",
        associated_order_number=order_sell.order_number,
        verification_status="MATCHED",
        voucher_date=datetime(2026, 11, 4, 14, 5, 0, tzinfo=UTC),
    )
    db.add_all([voucher_bdv, voucher_banesco])
    db.commit()

    # Asentar en el Libro Diario
    engine.record_p2p_trade(order=order_buy, voucher=voucher_bdv)
    engine.record_p2p_trade(order=order_sell, voucher=voucher_banesco)


    # Supongamos que el comerciante configuró su saldo inicial:
    # USDT: 1,000 USDT
    # Banco de Venezuela: 20,000 VES
    # Banesco: 10,000 VES
    initial_balances = {
        "crypto_usdt": 1000.0,
        "banks": {
            "Banco de Venezuela": 20000.0,
            "Banesco": 10000.0,
        },
    }

    live_summary: LiveBalanceSummary = engine.get_live_theoretical_balance(
        year=2026,
        month=11,
        initial_balances=initial_balances,
    )

    # Verificaciones matemáticas:
    # USDT: 1,000 + 100 (compra) - 50 (venta) = 1,050 USDT
    assert live_summary.initial_usdt == 1000.0
    assert live_summary.inflow_usdt == 100.0
    assert live_summary.outflow_usdt == 50.0
    assert live_summary.theoretical_usdt == 1050.0

    # Banco de Venezuela: 20,000 - 5,000 = 15,000 VES
    bdv = next((b for b in live_summary.bank_breakdown if "Venezuela" in b.bank_name), None)
    assert bdv is not None
    assert bdv.initial_ves == 20000.0
    assert bdv.outflows_ves == 5000.0
    assert bdv.theoretical_ves == 15000.0

    # Banesco: 10,000 + 2,750 = 12,750 VES
    banesco = next((b for b in live_summary.bank_breakdown if "Banesco" in b.bank_name), None)
    assert banesco is not None
    assert banesco.initial_ves == 10000.0
    assert banesco.inflows_ves == 2750.0
    assert banesco.theoretical_ves == 12750.0

    # Total VES teórico consolidado: 15,000 + 12,750 = 27,750 VES
    assert live_summary.total_initial_ves == 30000.0
    assert live_summary.total_theoretical_ves == 27750.0


def test_api_live_balance_endpoint():
    from src.api.routes.accounting import get_live_balance
    from src.data.models import User

    db = setup_in_memory_db()
    trader = User(username="live_trader", password_hash="pass", role="TRADER")
    db.add(trader)
    db.commit()

    res = get_live_balance(
        year=2026,
        month=11,
        initial_usdt=500.0,
        initial_ves=10000.0,
        db=db,
        current_user=trader,
    )

    assert res.year == 2026
    assert res.month == 11
    assert res.initial_usdt == 500.0
    assert res.theoretical_usdt == 500.0
    assert res.total_initial_ves == 10000.0
    assert res.total_theoretical_ves == 10000.0

