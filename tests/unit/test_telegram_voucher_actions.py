"""Tests unitarios (TDD) para interacción con botones inline de comprobante en Telegram (T18.7)."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import BankVoucher
from src.data.repositories import UserRepository
from src.integrations.telegram_notifier import TelegramNotifier


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_telegram_voucher_type_inline_callback():
    db = setup_in_memory_db()
    repo = UserRepository(db)
    user = repo.create_user(username="button_trader", password_hash="pass", role="TRADER")
    user.telegram_id = "11223344"  # type: ignore[assignment]
    db.commit()

    voucher = BankVoucher(
        bank_name="Banco Mercantil",
        reference_number="REF-MERC-123",
        amount_ves=4500.0,
        bank_fee_ves=0.0,
        total_debited_ves=4500.0,
        payment_method="PAGO_MOVIL",
        movement_type="UNKNOWN",
        associated_order_number=None,
        verification_status="UNMATCHED",
        voucher_date=datetime(2026, 11, 4, 18, 0, 0, tzinfo=UTC),
    )
    db.add(voucher)
    db.commit()

    notifier = TelegramNotifier(
        bot_token="fake:token",
        default_chat_id="11223344",
        session_factory=lambda: db,
    )

    from unittest.mock import patch
    with patch("src.data.database.SessionLocal", return_value=db):
        # El usuario hace clic en el botón [ 🟢 Venta (Recibí VES) ]
        resp = notifier.handle_command(
            user_id="11223344",
            command=f"/vtype:{voucher.id}:CREDIT",
        )

    assert "🟢" in resp
    assert "VENTA" in resp.upper() or "CRÉDITO" in resp.upper()

    from src.data.repositories import BankVoucherRepository
    v_repo = BankVoucherRepository(db)
    updated_voucher = v_repo.get_by_id(voucher.id)
    assert updated_voucher is not None
    assert updated_voucher.movement_type == "CREDIT"


def test_telegram_order_dual_telemetry_notification():
    notifier = TelegramNotifier(
        bot_token="fake:token",
        default_chat_id="11223344",
    )
    from unittest.mock import MagicMock
    notifier.send_alert = MagicMock(return_value=True)  # type: ignore[assignment]

    success = notifier.notify_p2p_order_settled(
        order_number="ORD-TEST-99",
        trade_type="SELL",
        crypto_amount=100.0,
        fiat_amount=5500.0,
        price=55.0,
        bcv_rate=50.0,
    )

    assert success is True
    call_args = notifier.send_alert.call_args[0][0]
    assert "Base Fiscal SENIAT" in call_args
    assert "50.00 VES/USD" in call_args
    assert "5,000.00 VES" in call_args


