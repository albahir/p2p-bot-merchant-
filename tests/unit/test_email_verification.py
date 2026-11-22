"""Tests unitarios TDD para verificación de correo vía SMTP, hash HMAC y anti-fuerza bruta."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.routes.auth import register, send_email_verification_code, verify_email_code
from src.api.schemas.auth import EmailSendCodeRequest, EmailVerifyCodeRequest, RegisterRequest
from src.data.database import Base
from src.data.models import SystemState, User

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_email_verification_flow_stores_hashed_otp_and_marks_user_verified() -> None:
    """Verifica envío SMTP mockeado, almacenamiento hasheado, validación de OTP y registro verificado."""
    db = _setup_db()
    try:
        settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            SMTP_HOST="smtp.gmail.com",
            SMTP_PORT=587,
            SMTP_USER="bot.p2p@gmail.com",
            SMTP_PASSWORD="app_password_16ch",
        )

        captured_codes: list[tuple[str, str]] = []

        def fake_smtp_send(self, to_email: str, code: str) -> tuple[bool, str | None]:
            captured_codes.append((to_email, code))
            return True, None

        with patch(
            "src.integrations.email_verifier.EmailVerificationService.send_verification_code",
            fake_smtp_send,
        ):
            send_res = send_email_verification_code(
                req=EmailSendCodeRequest(email="Trader.CCS@Gmail.COM"),
                db=db,
                settings=settings,
            )

        assert send_res["sent"] is True
        assert send_res["smtp_configured"] is True
        assert len(captured_codes) == 1
        sent_to, otp_code = captured_codes[0]
        assert sent_to == "trader.ccs@gmail.com"
        assert len(otp_code) == 6
        assert otp_code.isdigit()

        # Jamás almacenar el código en claro dentro de SystemState
        rows = db.query(SystemState).filter(SystemState.key.like("email_otp:%")).all()
        assert len(rows) == 1
        assert otp_code not in str(rows[0].value)
        assert '"h":' in str(rows[0].value)

        # Verificar código correcto -> entrega verification_token firmado
        verify_res = verify_email_code(
            req=EmailVerifyCodeRequest(email="trader.ccs@gmail.com", code=otp_code),
            db=db,
            settings=settings,
        )
        assert verify_res["verified"] is True
        ver_token = verify_res["verification_token"]
        assert isinstance(ver_token, str) and len(ver_token) > 20

        # Registrar usuario adjuntando email_verification_token -> email_verified=True
        with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert_async"):
            reg_res = register(
                req=RegisterRequest(
                    username="trader_email_ok",
                    password="StrongPassword123!",
                    full_name="Carlos Verificado",
                    email="trader.ccs@gmail.com",
                    telegram_id="6326947793",
                    email_verification_token=ver_token,
                ),
                db=db,
                settings=settings,
            )

        assert reg_res.user.email_verified is True
        db_user = db.query(User).filter(User.username == "trader_email_ok").first()
        assert db_user is not None
        assert bool(db_user.email_verified) is True
    finally:
        db.close()


def test_email_verification_brute_force_lock_and_unconfigured_smtp() -> None:
    """5 fallos de código bloquean por 15 min (HTTP 429) y SMTP sin configurar responde sin falsos positivos."""
    db = _setup_db()
    try:
        # 1. Sin credenciales SMTP -> reporta smtp_configured=False limpiamente
        no_smtp_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            SMTP_USER="",
            SMTP_PASSWORD="",
        )
        no_smtp_res = send_email_verification_code(
            req=EmailSendCodeRequest(email="nuevo@gmail.com"),
            db=db,
            settings=no_smtp_settings,
        )
        assert no_smtp_res["sent"] is False
        assert no_smtp_res["smtp_configured"] is False

        # 2. Con SMTP configurado -> 5 errores de código bloquean temporalmente (HTTP 429)
        smtp_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            SMTP_USER="bot@gmail.com",
            SMTP_PASSWORD="secret_app_password",
        )
        with patch(
            "src.integrations.email_verifier.EmailVerificationService.send_verification_code",
            return_value=(True, None),
        ):
            send_email_verification_code(
                req=EmailSendCodeRequest(email="nuevo@gmail.com"),
                db=db,
                settings=smtp_settings,
            )

        for _ in range(4):
            with pytest.raises(HTTPException) as exc:
                verify_email_code(
                    req=EmailVerifyCodeRequest(email="nuevo@gmail.com", code="000000"),
                    db=db,
                    settings=smtp_settings,
                )
            assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as lock_exc:
            verify_email_code(
                req=EmailVerifyCodeRequest(email="nuevo@gmail.com", code="000000"),
                db=db,
                settings=smtp_settings,
            )
        assert lock_exc.value.status_code == 429
    finally:
        db.close()
