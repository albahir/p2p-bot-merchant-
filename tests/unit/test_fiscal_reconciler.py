"""Pruebas unitarias para el motor de reconstrucción fiscal de 6 piezas y FIFOCostMethod con inventario inicial."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.models import Base, Order, WalletMovement
from src.data.repositories import OrderRepository, WalletMovementRepository
from src.reporting.fiscal_reconciler import FiscalReconciler, FiscalReconciliationResult
from src.reporting.tax_engine import FIFOCostMethod, TaxLot


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_fifo_cost_method_with_initial_inventory():
    """Verifica que FIFOCostMethod acepte lotes de inventario inicial y los liquide en orden."""
    initial_lots = [
        TaxLot(crypto_amount=100.0, total_cost_fiat=5000.0, unit_cost_fiat=50.0)
    ]
    fifo = FIFOCostMethod(initial_inventory=initial_lots)

    sell_order = Order(
        order_number="SELL-001",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        crypto_amount=50.0,
        unit_price=60.0,
        fiat_amount=3000.0,
        fee_fiat=0.0,
        order_status="COMPLETED",
        bcv_rate=50.0,
        created_at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
    )

    results = fifo.process_orders([sell_order])
    assert len(results) == 1
    res = results[0]
    # Costo de adquisición de 50 USDT a 50 VES/USDT = 2500 VES
    assert res.acquisition_cost_fiat == 2500.0
    # Ingreso = 3000 VES, Ganancia = 500 VES
    assert res.net_profit_fiat == 500.0
    assert res.net_profit_usd == 10.0


def test_fiscal_reconciler_balanced_period(db_session: Session):
    """Verifica la ecuación de 6 piezas en un período perfectamente balanceado."""
    order_repo = OrderRepository(db_session)
    wallet_repo = WalletMovementRepository(db_session)

    # 1. P2P Buy (Entrada de cripto)
    buy_order = Order(
        order_number="BUY-101",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        crypto_amount=300.0,
        unit_price=52.0,
        fiat_amount=15600.0,
        fee_fiat=0.0,
        order_status="COMPLETED",
        bcv_rate=50.0,
        created_at=datetime(2026, 10, 5, 10, 0, tzinfo=UTC),
    )
    order_repo.create(buy_order)

    # 2. P2P Sell (Salida de cripto)
    sell_order = Order(
        order_number="SELL-102",
        trade_type="SELL",
        asset="USDT",
        fiat="VES",
        crypto_amount=200.0,
        unit_price=55.0,
        fiat_amount=11000.0,
        fee_fiat=0.0,
        order_status="COMPLETED",
        bcv_rate=50.0,
        created_at=datetime(2026, 10, 10, 14, 0, tzinfo=UTC),
    )
    order_repo.create(sell_order)

    # 3. Wallet Deposit (Entrada on-chain)
    deposit = WalletMovement(
        txid="DEP-001",
        movement_type="DEPOSIT",
        asset="USDT",
        amount=100.0,
        fee=0.0,
        status="COMPLETED",
        timestamp=datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
    )
    wallet_repo.create(deposit)

    # 4. Wallet Withdrawal (Salida on-chain con comisión)
    withdrawal = WalletMovement(
        txid="WTH-001",
        movement_type="WITHDRAWAL",
        asset="USDT",
        amount=50.0,
        fee=1.0,
        status="COMPLETED",
        timestamp=datetime(2026, 10, 20, 16, 0, tzinfo=UTC),
    )
    wallet_repo.create(withdrawal)

    # Reconciliación:
    # Saldo inicial = 100 USDT
    # Entradas = Depósitos (100) + Compras P2P (300) = 400 USDT
    # Salidas = Retiros (50) + Ventas P2P (200) = 250 USDT
    # Comisiones cripto = Retiro fee (1.0)
    # Saldo final teórico = 100 + 400 - 250 - 1.0 = 249.0 USDT
    reconciler = FiscalReconciler(db_session=db_session)
    result = reconciler.reconcile_period(
        period="2026-10",
        initial_balance=100.0,
        initial_bcv_rate=50.0,
        actual_final_balance=249.0,
    )

    assert isinstance(result, FiscalReconciliationResult)
    assert result.period == "2026-10"
    assert result.initial_balance == 100.0
    assert result.inflows_deposits == 100.0
    assert result.inflows_p2p_buys == 300.0
    assert result.total_inflows == 400.0
    assert result.outflows_withdrawals == 50.0
    assert result.outflows_p2p_sells == 200.0
    assert result.total_outflows == 250.0
    assert result.total_fees == 1.0
    assert result.calculated_final_balance == 249.0
    assert result.actual_final_balance == 249.0
    assert result.discrepancy == 0.0
    assert result.status == "BALANCED"
    assert result.volume_operated == 500.0  # 300 buys + 200 sells


def test_fiscal_reconciler_discrepancy_detection(db_session: Session):
    """Detecta merma o saldo no justificado cuando el saldo real difiere del teórico."""
    reconciler = FiscalReconciler(db_session=db_session)
    result = reconciler.reconcile_period(
        period="2026-10",
        initial_balance=100.0,
        actual_final_balance=90.0,  # Faltan 10 USDT
    )

    assert result.calculated_final_balance == 100.0
    assert result.actual_final_balance == 90.0
    assert result.discrepancy == -10.0
    assert result.status == "DISCREPANCY"


def test_fiscal_reconciler_persist_snapshot(db_session: Session):
    """Verifica que el snapshot mensual se guarde e idempotentemente se actualice."""
    reconciler = FiscalReconciler(db_session=db_session)
    result = reconciler.reconcile_period(
        period="2026-10",
        initial_balance=50.0,
        actual_final_balance=50.0,
    )

    snapshot = reconciler.save_snapshot(result)
    assert snapshot.id is not None
    assert snapshot.period == "2026-10"
    assert snapshot.status == "BALANCED"

    # Segunda corrida actualiza snapshot existente sin duplicar ID
    updated_result = reconciler.reconcile_period(
        period="2026-10",
        initial_balance=50.0,
        actual_final_balance=45.0,
    )
    updated_snapshot = reconciler.save_snapshot(updated_result)
    assert updated_snapshot.id == snapshot.id
    assert updated_snapshot.status == "DISCREPANCY"
