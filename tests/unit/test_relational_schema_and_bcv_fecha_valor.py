"""Pruebas TDD para integridad relacional (Foreign Keys + UNIQUE compuesto por usuario),
aislamiento estricto sin fuga de filas NULL, apagado real del Sandbox y regla BCV de Fecha Valor vespertina.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.data.models import (
    AccountingPeriodBalance,
    BankVoucher,
    Base,
    BCVRateHistory,
    FiscalPeriodSnapshot,
    JournalEntry,
    Order,
    User,
    WalletMovement,
)
from src.data.repositories import BCVHistoryRepository, OrderRepository
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.bcv_history_service import BCVHistoryService


def _make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_models_declare_real_foreign_keys_to_app_users() -> None:
    """Todas las tablas operativas del usuario deben declarar clave foránea real a app_users.id."""
    user_tables = [
        Order,
        BankVoucher,
        WalletMovement,
        JournalEntry,
        FiscalPeriodSnapshot,
        AccountingPeriodBalance,
    ]
    for model in user_tables:
        fks = {fk.target_fullname for fk in model.__table__.c.user_id.foreign_keys}
        assert "app_users.id" in fks, f"{model.__tablename__}.user_id debe tener FK a app_users.id"

    voucher_fks = {fk.target_fullname for fk in JournalEntry.__table__.c.voucher_id.foreign_keys}
    assert "bank_vouchers.id" in voucher_fks


def test_user_scope_never_leaks_orphan_null_orders_to_authenticated_user() -> None:
    """Un usuario autenticado jamás debe ver órdenes huérfanas (user_id IS NULL) del Sandbox aunque sea el único usuario."""
    db = _make_session()
    try:
        u1 = User(username="unico_operador", password_hash="h", role="ADMIN", is_active=True)
        db.add(u1)
        db.commit()
        db.refresh(u1)

        # 1 orden huérfana (Sandbox) + 1 orden real de u1
        db.add(
            Order(
                user_id=None,
                order_number="202610140001",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=3650.0,
                crypto_amount=100.0,
                unit_price=36.5,
                bcv_rate=919.8227,
                order_status="COMPLETED",
                created_at=datetime(2026, 11, 20, 19, 50, 0),
            )
        )
        db.add(
            Order(
                user_id=int(u1.id),
                order_number="22956168994483376128",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=36000.0,
                crypto_amount=33.45,
                unit_price=1076.0,
                bcv_rate=915.7476,
                order_status="COMPLETED",
                created_at=datetime(2026, 11, 18, 0, 40, 0),
            )
        )
        db.commit()

        repo = OrderRepository(db, user_id=int(u1.id))
        completed = repo.list_completed()
        assert [o.order_number for o in completed] == ["22956168994483376128"]

        live = AccountingEngine(db=db, user_id=int(u1.id)).get_live_theoretical_balance(year=2026, month=11)
        assert live.inflow_usdt == 33.45
        assert live.theoretical_usdt == 33.45
    finally:
        db.close()


def test_two_users_can_store_same_binance_order_number_composite_unique() -> None:
    """Dos usuarios que operan entre sí en Binance P2P comparten order_number (BUY vs SELL) sin colisión."""
    db = _make_session()
    try:
        u1 = User(username="comprador", password_hash="h", role="TRADER", is_active=True)
        u2 = User(username="vendedor", password_hash="h", role="TRADER", is_active=True)
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)

        o1 = Order(
            user_id=int(u1.id),
            order_number="22990000111122223333",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=100000.0,
            crypto_amount=100.0,
            unit_price=1000.0,
            bcv_rate=919.82,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 24, 15, 0, 0),
        )
        o2 = Order(
            user_id=int(u2.id),
            order_number="22990000111122223333",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=100000.0,
            crypto_amount=100.0,
            unit_price=1000.0,
            bcv_rate=919.82,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 24, 15, 0, 0),
        )
        db.add_all([o1, o2])
        db.commit()

        # Pero el MISMO usuario no puede duplicar el mismo order_number
        dup = Order(
            user_id=int(u1.id),
            order_number="22990000111122223333",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=100000.0,
            crypto_amount=100.0,
            unit_price=1000.0,
            bcv_rate=919.82,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 24, 15, 0, 0),
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_bcv_afternoon_future_fecha_valor_never_overwrites_today_rate() -> None:
    """Si el BCV publica por la tarde la tasa de mañana (Fecha Valor > hoy), se guarda para mañana sin pisar la tasa legal de hoy."""
    db = _make_session()
    try:
        repo = BCVHistoryRepository(db)
        repo.upsert_rate(
            BCVRateHistory(
                fecha_valor=date(2026, 11, 24),
                usd_rate=919.8227,
                eur_rate=1025.0,
                source="bcv_official_seed",
            )
        )

        class AfternoonBCVMock:
            def fetch_full_rates(self):
                return {
                    "usd": 922.56,
                    "eur": 1030.10,
                    "fecha_valor": "Miércoles, 25 Noviembre 2026",
                }

            def fetch_current_rate(self):
                return 922.56

        # Simular consulta el 24/11/2026 a las 17:00 VET (21:00 UTC)
        fake_now_utc = datetime(2026, 11, 24, 21, 0, 0, tzinfo=UTC)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now_utc.astimezone(tz) if tz else fake_now_utc.replace(tzinfo=None)

        svc = BCVHistoryService(db_session=db, bcv_live_service=AfternoonBCVMock())  # type: ignore[arg-type]
        with patch("src.reporting.bcv_history_service.datetime", FakeDateTime):
            active = svc.get_or_fetch_current_rates(force_refresh=True)

        # La tasa de hoy (24/11) NO debe ser sobrescrita por la de mañana (25/11)
        row_today = repo.get_rate_by_date(date(2026, 11, 24))
        row_tomorrow = repo.get_rate_by_date(date(2026, 11, 25))
        assert row_today is not None and abs(float(row_today.usd_rate) - 919.8227) < 0.0001
        assert row_tomorrow is not None and abs(float(row_tomorrow.usd_rate) - 922.56) < 0.0001
        assert abs(float(active["usd"]) - 919.8227) < 0.0001
        assert active["fecha_valor"] == "2026-11-24"
    finally:
        db.close()


def test_engine_with_use_sandbox_false_never_falls_back_to_mock_client() -> None:
    """Con USE_SANDBOX=False y sin llave global heredada, el motor NO debe activar MockBinanceP2PClient."""
    from src.main import P2PBotEngine

    class EmptyKeyManager:
        def get_secret(self, name: str) -> str:
            raise KeyError(name)

    fake_engine = object.__new__(P2PBotEngine)
    fake_engine.key_manager = EmptyKeyManager()
    fake_engine.use_sandbox = False
    fake_engine.client = None
    fake_engine.notifier = SimpleNamespace(use_sandbox=False)

    fake_engine._setup_binance_client()

    assert fake_engine.use_sandbox is False
    assert fake_engine.client is None
    assert fake_engine.notifier.use_sandbox is False
