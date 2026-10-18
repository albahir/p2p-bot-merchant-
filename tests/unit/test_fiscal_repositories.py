"""Tests unitarios (TDD) para los modelos y repositorios de movimientos de billetera,
comprobantes bancarios y snapshots de período fiscal (SPEC-014).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher, FiscalPeriodSnapshot, WalletMovement
from src.data.repositories import (
    BankVoucherRepository,
    FiscalSnapshotRepository,
    IdentityRepository,
    WalletMovementRepository,
)


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_wallet_movement_repository_crud():
    db = setup_in_memory_db()
    repo = WalletMovementRepository(db)

    now = datetime.now(UTC)
    dep = WalletMovement(
        movement_type="DEPOSIT",
        asset="USDT",
        amount=500.0,
        fee=0.0,
        network="TRC20",
        txid="0x_deposit_hash_123",
        address="TXYZ123456789",
        status="Success",
        timestamp=now - timedelta(hours=2),
    )
    saved_dep = repo.create(dep)
    assert saved_dep.id is not None
    assert saved_dep.amount == 500.0

    # Búsqueda por txid
    found = repo.get_by_txid("0x_deposit_hash_123")
    assert found is not None
    assert found.movement_type == "DEPOSIT"
    assert found.asset == "USDT"

    # Inserción de un retiro
    wit = WalletMovement(
        movement_type="WITHDRAWAL",
        asset="USDT",
        amount=200.0,
        fee=1.0,
        network="TRC20",
        txid="0x_withdraw_hash_456",
        address="TABC987654321",
        status="Completed",
        timestamp=now,
    )
    repo.create(wit)

    # Filtrado por período
    movements = repo.list_by_period(
        start_date=now - timedelta(hours=3),
        end_date=now + timedelta(hours=1),
        asset="USDT",
    )
    assert len(movements) == 2

    # Filtrar solo retiros
    withdrawals = repo.list_by_period(
        start_date=now - timedelta(hours=3),
        end_date=now + timedelta(hours=1),
        asset="USDT",
        movement_type="WITHDRAWAL",
    )
    assert len(withdrawals) == 1
    assert withdrawals[0].fee == 1.0


def test_bank_voucher_repository_crud_and_matching():
    db = setup_in_memory_db()
    repo = BankVoucherRepository(db)

    voucher = BankVoucher(
        bank_name="Banco de Venezuela",
        reference_number="0102123456",
        amount_ves=4500.50,
        sender_id="V-18234567",
        sender_name="MANUEL RODRIGUEZ",
        payment_method="PAGO_MOVIL",
        verification_status="UNMATCHED",
        voucher_date=datetime.now(UTC),
    )
    saved = repo.create(voucher)
    assert saved.id is not None
    assert saved.reference_number == "0102123456"

    # Buscar por referencia
    found = repo.get_by_reference("0102123456")
    assert found is not None
    assert found.amount_ves == 4500.50

    # Listar no asociados
    unmatched = repo.list_unmatched()
    assert len(unmatched) == 1

    # Asociar con orden P2P
    matched = repo.match_with_order(voucher_id=saved.id, order_number="P2P-ORD-778899")
    assert matched is not None
    assert matched.associated_order_number == "P2P-ORD-778899"
    assert matched.verification_status == "MATCHED"

    # Ya no debe estar en lista de no asociados
    assert len(repo.list_unmatched()) == 0


def test_fiscal_snapshot_repository_upsert_and_retrieve():
    db = setup_in_memory_db()
    repo = FiscalSnapshotRepository(db)

    snapshot = FiscalPeriodSnapshot(
        period="2026-09",
        initial_balance=100.0,
        inflows_deposits=500.0,
        inflows_p2p_buys=1500.0,
        outflows_withdrawals=200.0,
        outflows_p2p_sells=1700.0,
        volume_operated=3200.0,
        total_fees=12.5,
        calculated_final_balance=200.0,
        actual_final_balance=200.0,
        discrepancy=0.0,
        gross_revenue_ves=68000.0,
        acquisition_cost_ves=64000.0,
        net_profit_ves=4000.0,
        net_profit_usd=109.58,
        status="BALANCED",
    )
    saved = repo.upsert_snapshot(snapshot)
    assert saved.id is not None
    assert saved.period == "2026-09"

    # Recuperar por período
    retrieved = repo.get_by_period("2026-09")
    assert retrieved is not None
    assert retrieved.net_profit_ves == 4000.0
    assert retrieved.status == "BALANCED"

    # Actualizar snapshot existente con nuevo balance
    snapshot_updated = FiscalPeriodSnapshot(
        period="2026-09",
        initial_balance=100.0,
        inflows_deposits=600.0,
        inflows_p2p_buys=1500.0,
        outflows_withdrawals=200.0,
        outflows_p2p_sells=1700.0,
        volume_operated=3200.0,
        total_fees=12.5,
        calculated_final_balance=300.0,
        actual_final_balance=300.0,
        discrepancy=0.0,
        gross_revenue_ves=68000.0,
        acquisition_cost_ves=64000.0,
        net_profit_ves=4000.0,
        net_profit_usd=109.58,
        status="BALANCED",
    )
    updated = repo.upsert_snapshot(snapshot_updated)
    assert updated.calculated_final_balance == 300.0

    # Obtener el snapshot más reciente
    latest = repo.get_latest_snapshot()
    assert latest is not None
    assert latest.period == "2026-09"


def test_identity_repository_crud():
    """Valida la persistencia permanente, búsqueda y deduplicación de identidades."""
    db = setup_in_memory_db()
    repo = IdentityRepository(db)

    # 1. Inserción inicial
    saved = repo.upsert(
        nationality="V",
        cedula="18234567",
        full_name="JUAN CARLOS PEREZ GOMEZ",
        source="METAP2P",
    )
    assert saved.id is not None
    assert saved.nationality == "V"
    assert saved.cedula == "18234567"
    assert saved.full_name == "JUAN CARLOS PEREZ GOMEZ"
    assert saved.source == "METAP2P"

    # 2. Búsqueda por cédula
    found = repo.get_by_cedula("V", "18234567")
    assert found is not None
    assert found.full_name == "JUAN CARLOS PEREZ GOMEZ"

    # 3. Upsert de actualización sin duplicar fila
    updated = repo.upsert(
        nationality="V",
        cedula="18234567",
        full_name="JUAN CARLOS PEREZ GOMEZ ACTUALIZADO",
        source="SENIAT",
    )
    assert updated.id == saved.id
    assert updated.full_name == "JUAN CARLOS PEREZ GOMEZ ACTUALIZADO"
    assert updated.source == "SENIAT"
    assert repo.count() == 1

    # 4. Insertar otra identidad extranjera
    repo.upsert(
        nationality="E",
        cedula="82111222",
        full_name="MARIA SOFIA RODRIGUEZ",
        source="METAP2P",
    )
    assert repo.count() == 2

    # 5. Listar todos
    all_identities = repo.list_all()
    assert len(all_identities) == 2

    # 6. Búsqueda por texto (query)
    results_by_name = repo.search("RODRIGUEZ")
    assert len(results_by_name) == 1
    assert results_by_name[0].cedula == "82111222"

    results_by_cedula = repo.search("18234567")
    assert len(results_by_cedula) == 1
    assert results_by_cedula[0].nationality == "V"

