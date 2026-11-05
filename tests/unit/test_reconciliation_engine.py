"""Tests unitarios (TDD) para el Motor de Conciliación Multi-Factorial P2P (SPEC-017)."""

from datetime import UTC, datetime, timedelta

from src.data.models import BankVoucher, Order
from src.reporting.reconciliation_engine import (
    P2PReconciliationEngine,
    ReconciliationDecision,
)


def test_exact_pago_movil_auto_match():
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    order = Order(
        order_number="ORD-20261103-987654",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=2450.75,
        crypto_amount=50.0,
        unit_price=49.015,
        payment_method="Banco de Venezuela",
        counterparty_name="CARLOS PEREZ",
        order_status="COMPLETED",
        created_at=now,
        completed_at=now + timedelta(minutes=5),
    )

    voucher = BankVoucher(
        id=1,
        bank_name="Banco de Venezuela",
        destination_bank="Banesco",
        reference_number="987654",
        amount_ves=2450.75,
        sender_id="V-19456789",
        sender_name="CARLOS PEREZ",
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        voucher_date=now + timedelta(minutes=3),
    )

    score = engine.calculate_score(voucher, order)
    # Monto exacto con céntimos (30+5) + Banco (30) + Ref en orden (40) + Nombre (15) = 100 max
    assert score >= 90.0

    match_result = engine.find_best_match(voucher, [order])
    assert match_result.decision == ReconciliationDecision.AUTO_MATCHED
    assert match_result.matched_order is not None
    assert match_result.matched_order.order_number == "ORD-20261103-987654"


def test_flow_direction_mismatch_fails_closed():
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    # Orden BUY (nosotros pagamos VES -> voucher DEBIT)
    order = Order(
        order_number="ORD-BUY-101",
        trade_type="BUY",
        fiat_amount=1500.0,
        crypto_amount=30.0,
        unit_price=50.0,
        payment_method="Banesco",
        created_at=now,
    )

    # Voucher CREDIT (ingreso de dinero, típico de SELL, no BUY)
    voucher = BankVoucher(
        id=2,
        bank_name="Banesco",
        reference_number="123456",
        amount_ves=1500.0,
        payment_method="PAGO_MOVIL",
        movement_type="CREDIT",
        voucher_date=now + timedelta(minutes=2),
    )

    score = engine.calculate_score(voucher, order)
    assert score == 0.0

    match_result = engine.find_best_match(voucher, [order])
    assert match_result.decision == ReconciliationDecision.UNMATCHED
    assert match_result.matched_order is None


def test_time_window_pago_movil_exceeded():
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    order = Order(
        order_number="ORD-PM-102",
        trade_type="BUY",
        fiat_amount=1000.0,
        crypto_amount=20.0,
        unit_price=50.0,
        payment_method="Banesco",
        created_at=now,
    )

    # Voucher emitido 45 minutos después (> 30 min para pago móvil)
    voucher = BankVoucher(
        id=3,
        bank_name="Banesco",
        reference_number="998877",
        amount_ves=1000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        voucher_date=now + timedelta(minutes=45),
    )

    score = engine.calculate_score(voucher, order)
    assert score == 0.0

    match_result = engine.find_best_match(voucher, [order])
    assert match_result.decision == ReconciliationDecision.UNMATCHED


def test_transfer_window_and_scoring():
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)

    order = Order(
        order_number="ORD-TRANSF-103",
        trade_type="BUY",
        fiat_amount=5000.0,
        crypto_amount=100.0,
        unit_price=50.0,
        payment_method="Mercantil",
        created_at=now,
    )

    # Transferencia bancaria dentro de las 48 horas (12 horas después)
    voucher_valid = BankVoucher(
        id=4,
        bank_name="Mercantil",
        reference_number="554433",
        amount_ves=5000.0,
        payment_method="TRANSFERENCIA",
        movement_type="DEBIT",
        voucher_date=now + timedelta(hours=12),
    )

    score = engine.calculate_score(voucher_valid, order)
    assert score >= 60.0  # Monto (30) + Banco (30) = 60

    match_result = engine.find_best_match(voucher_valid, [order])
    assert match_result.decision == ReconciliationDecision.SUGGESTED

    # Transferencia bancaria vencida (> 48 horas = 50 horas)
    voucher_expired = BankVoucher(
        id=5,
        bank_name="Mercantil",
        reference_number="554433",
        amount_ves=5000.0,
        payment_method="TRANSFERENCIA",
        movement_type="DEBIT",
        voucher_date=now + timedelta(hours=50),
    )
    score_expired = engine.calculate_score(voucher_expired, order)
    assert score_expired == 0.0


def test_batch_reconciliation_uniqueness():
    engine = P2PReconciliationEngine()
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=UTC)

    order1 = Order(
        order_number="ORD-A1",
        trade_type="BUY",
        fiat_amount=1000.0,
        payment_method="Banesco",
        created_at=now,
    )
    order2 = Order(
        order_number="ORD-A2",
        trade_type="BUY",
        fiat_amount=1000.0,
        payment_method="Mercantil",
        created_at=now,
    )

    voucher1 = BankVoucher(
        id=10,
        bank_name="Banesco",
        reference_number="REF-001",
        amount_ves=1000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        voucher_date=now + timedelta(minutes=5),
    )
    voucher2 = BankVoucher(
        id=20,
        bank_name="Mercantil",
        reference_number="REF-002",
        amount_ves=1000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        voucher_date=now + timedelta(minutes=5),
    )

    results = engine.reconcile_batch([voucher1, voucher2], [order1, order2])
    assert len(results) == 2

    # Cada voucher debe haberse asignado a su orden correspondiente por banco
    v1_res = next(r for r in results if r.voucher_id == 10)
    v2_res = next(r for r in results if r.voucher_id == 20)

    assert v1_res.matched_order is not None
    assert v1_res.matched_order.order_number == "ORD-A1"

    assert v2_res.matched_order is not None
    assert v2_res.matched_order.order_number == "ORD-A2"
