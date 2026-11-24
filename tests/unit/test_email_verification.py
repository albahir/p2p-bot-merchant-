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


def test_recovery_profile_updates_verified_email_without_overwriting_existing_fields() -> None:
    """Actualizar correo verificado en Settings persiste email_verified=True sin borrar otros campos."""
    from src.api.routes.auth import update_recovery_profile
    from src.api.schemas.auth import RecoveryProfileUpdateRequest
    from src.security.auth_service import AuthService

    db = _setup_db()
    try:
        smtp_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            SMTP_USER="bot@gmail.com",
            SMTP_PASSWORD="secret_app_password",
        )
        auth = AuthService(db_session=db)
        user = User(
            username="trader_profile_test",
            password_hash=auth.hash_password("ClaveSegura123!"),
            role="TRADER",
            full_name="Nombre Inicial",
            tax_id="V-12345678",
            email="viejo@gmail.com",
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        with patch(
            "src.integrations.email_verifier.EmailVerificationService.send_verification_code",
            return_value=(True, None),
        ) as mock_send:
            send_email_verification_code(
                req=EmailSendCodeRequest(email="nuevo.verificado@gmail.com"),
                db=db,
                settings=smtp_settings,
            )
            otp_code = mock_send.call_args.kwargs["code"]

        ver_res = verify_email_code(
            req=EmailVerifyCodeRequest(email="nuevo.verificado@gmail.com", code=otp_code),
            db=db,
            settings=smtp_settings,
        )
        token = ver_res["verification_token"]

        # 1. Guardar nuevo correo junto al token verificado -> email_verified=True y conserva full_name/tax_id
        upd1 = update_recovery_profile(
            req=RecoveryProfileUpdateRequest(
                email="nuevo.verificado@gmail.com",
                email_verification_token=token,
            ),
            db=db,
            current_user=user,
            settings=smtp_settings,
        )
        assert upd1["user"].email == "nuevo.verificado@gmail.com"
        assert upd1["user"].email_verified is True
        assert upd1["user"].full_name == "Nombre Inicial"
        assert upd1["user"].tax_id == "V-12345678"

        # 2. Actualizar únicamente full_name -> NO reescribe ni invalida el correo verificado previo
        upd2 = update_recovery_profile(
            req=RecoveryProfileUpdateRequest(full_name="Nombre Actualizado"),
            db=db,
            current_user=user,
            settings=smtp_settings,
        )
        assert upd2["user"].full_name == "Nombre Actualizado"
        assert upd2["user"].email == "nuevo.verificado@gmail.com"
        assert upd2["user"].email_verified is True
        assert upd2["user"].tax_id == "V-12345678"

        # 3. Cambiar a otro correo sin verificar -> reinicia email_verified a False (Fail-Closed)
        upd3 = update_recovery_profile(
            req=RecoveryProfileUpdateRequest(email="sinverificar@gmail.com"),
            db=db,
            current_user=user,
            settings=smtp_settings,
        )
        assert upd3["user"].email == "sinverificar@gmail.com"
        assert upd3["user"].email_verified is False

        # 4. Token manipulado o de otro correo debe ser rechazado con HTTP 400
        with pytest.raises(HTTPException) as bad_tok:
            update_recovery_profile(
                req=RecoveryProfileUpdateRequest(
                    email="otro@gmail.com",
                    email_verification_token=token,
                ),
                db=db,
                current_user=user,
                settings=smtp_settings,
            )
        assert bad_tok.value.status_code == 400
    finally:
        db.close()


def test_change_telegram_id_requires_verified_email_and_otp_token() -> None:
    """Cambiar telegram_id exige correo verificado y token OTP válido del correo dueño."""
    from src.api.routes.auth import update_recovery_profile
    from src.api.schemas.auth import RecoveryProfileUpdateRequest
    from src.security.auth_service import AuthService

    db = _setup_db()
    try:
        smtp_settings = Settings(
            MASTER_ENCRYPTION_KEY=TEST_SECRET,
            JWT_SECRET_KEY=TEST_SECRET,
            SMTP_USER="bot@gmail.com",
            SMTP_PASSWORD="secret_app_password",
        )
        auth = AuthService(db_session=db)
        user = User(
            username="tg_owner",
            password_hash=auth.hash_password("ClaveSegura123!"),
            role="TRADER",
            telegram_id="111222333",
            email="dueno@gmail.com",
            email_verified=False,
        )
        other = User(
            username="tg_other",
            password_hash=auth.hash_password("ClaveSegura123!"),
            role="TRADER",
            telegram_id="555666777",
        )
        db.add_all([user, other])
        db.commit()
        db.refresh(user)

        # 1. Sin correo verificado -> falla (400)
        with pytest.raises(HTTPException) as unverified_exc:
            update_recovery_profile(
                req=RecoveryProfileUpdateRequest(telegram_id="998877665"),
                db=db,
                current_user=user,
                settings=smtp_settings,
            )
        assert unverified_exc.value.status_code == 400

        # 2. Marcar correo verificado, intentar sin token OTP -> falla (400/403)
        user.email_verified = True  # type: ignore[assignment]
        db.commit()
        with pytest.raises(HTTPException) as no_tok_exc:
            update_recovery_profile(
                req=RecoveryProfileUpdateRequest(telegram_id="998877665"),
                db=db,
                current_user=user,
                settings=smtp_settings,
            )
        assert no_tok_exc.value.status_code in (400, 403)

        # 3. Obtener OTP real al correo propio del dueño vía endpoint autenticado -> éxito
        from src.api.routes.auth import send_profile_email_otp

        with patch(
            "src.integrations.email_verifier.EmailVerificationService.send_verification_code",
            return_value=(True, None),
        ) as mock_send:
            send_profile_email_otp(
                db=db,
                current_user=user,
                settings=smtp_settings,
            )
            otp_code = mock_send.call_args.kwargs["code"]

        ver_res = verify_email_code(
            req=EmailVerifyCodeRequest(email="dueno@gmail.com", code=otp_code),
            db=db,
            settings=smtp_settings,
        )
        token = ver_res["verification_token"]

        # 4. Intentar usar telegram_id ya perteneciente a otra cuenta -> rechazado (400)
        with pytest.raises(HTTPException) as dup_exc:
            update_recovery_profile(
                req=RecoveryProfileUpdateRequest(
                    telegram_id="555666777",
                    email_verification_token=token,
                ),
                db=db,
                current_user=user,
                settings=smtp_settings,
            )
        assert dup_exc.value.status_code == 400

        # 5. Cambiar a telegram_id libre con token OTP válido -> éxito
        res = update_recovery_profile(
            req=RecoveryProfileUpdateRequest(
                telegram_id="998877665",
                email_verification_token=token,
            ),
            db=db,
            current_user=user,
            settings=smtp_settings,
        )
        assert res["user"].telegram_id == "998877665"
        assert res["user"].email == "dueno@gmail.com"
        assert res["user"].email_verified is True
    finally:
        db.close()
