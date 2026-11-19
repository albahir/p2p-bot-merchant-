"""Tests unitarios (TDD) para Registro Enriquecido y Recuperación Segura Multi-Factor de Perfil."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.data.database import Base
from src.data.models import User
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_settings():
    return Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
        TELEGRAM_BOT_TOKEN="123456:fake",
    )


def test_register_with_recovery_profile_hashes_secrets_and_returns_one_time_key(test_db, test_settings):
    """El registro guarda hashes PBKDF2 (nunca texto plano) y entrega Llave Maestra única."""
    from src.api.routes.auth import get_my_profile, register
    from src.api.schemas.auth import RegisterRequest

    req = RegisterRequest(
        username="operador_seguro",
        password="ClaveInicial2026!",
        full_name="Carlos Mendoza",
        email="Carlos.Mendoza@Ejemplo.COM",
        security_question="¿Cuál fue tu primer banco en Venezuela?",
        security_answer="  Banco de Venezuela  ",
    )

    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        token_resp = register(req=req, db=test_db, settings=test_settings)

    # 1. Entrega llave maestra una sola vez con formato P2P-XXXX-XXXX-XXXX
    assert token_resp.recovery_key is not None
    assert token_resp.recovery_key.startswith("P2P-")
    assert len(token_resp.recovery_key) >= 15

    # 2. Usuario persistido con email normalizado en minúsculas y hashes PBKDF2 reales
    db_user = test_db.query(User).filter(User.username == "operador_seguro").first()
    assert db_user is not None
    assert db_user.full_name == "Carlos Mendoza"
    assert db_user.email == "carlos.mendoza@ejemplo.com"
    assert db_user.security_question == "¿Cuál fue tu primer banco en Venezuela?"
    assert db_user.security_answer_hash is not None
    assert "Banco de Venezuela" not in str(db_user.security_answer_hash)
    assert str(db_user.security_answer_hash).startswith("pbkdf2_sha256$")
    assert db_user.recovery_key_hash is not None
    assert token_resp.recovery_key not in str(db_user.recovery_key_hash)

    # 3. /api/auth/me nunca expone hashes ni llave maestra, solo booleanos de configuración
    public_me = get_my_profile(current_user=db_user)
    assert public_me.email == "carlos.mendoza@ejemplo.com"
    assert public_me.full_name == "Carlos Mendoza"
    assert public_me.has_security_question is True
    assert public_me.has_recovery_key is True


def test_recover_options_and_reset_via_security_question_and_rate_limit(test_db, test_settings):
    """Permite buscar perfil por correo y recuperar con Pregunta Secreta + bloqueo tras 5 fallos."""
    from fastapi import HTTPException

    from src.api.routes.auth import get_recovery_options, login, register, reset_password
    from src.api.schemas.auth import (
        LoginRequest,
        PasswordRecoveryRequest,
        PasswordResetRequest,
        RegisterRequest,
    )

    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        register(
            req=RegisterRequest(
                username="trader_valencia",
                password="ClaveVieja2026!",
                full_name="Ana Sofía Pérez",
                email="ana.perez@correo.com",
                security_question="Nombre de tu mascota",
                security_answer="Firulais",
            ),
            db=test_db,
            settings=test_settings,
        )

    # 1. Consultar opciones de recuperación ingresando correo en vez de username
    opts = get_recovery_options(req=PasswordRecoveryRequest(username="ANA.PEREZ@CORREO.COM"), db=test_db)
    assert opts.has_security_question is True
    assert opts.security_question == "Nombre de tu mascota"
    assert opts.has_recovery_key is True
    assert opts.has_telegram is False

    # 2. Respuesta incorrecta incrementa intentos y al 5to intento bloquea Fail-Closed (HTTP 429)
    for attempt in range(5):
        with pytest.raises(HTTPException) as exc_info:
            reset_password(
                req=PasswordResetRequest(
                    username="ana.perez@correo.com",
                    method="security_question",
                    reset_code="Incorrecta",
                    new_password="NuevaClaveSegura2026!",
                ),
                db=test_db,
            )
        expected_code = 429 if attempt == 4 else 400
        assert exc_info.value.status_code == expected_code

    # Aunque ahora envíe la respuesta correcta durante el bloqueo de 15 min, debe seguir bloqueado
    with pytest.raises(HTTPException) as locked_exc:
        reset_password(
            req=PasswordResetRequest(
                username="ana.perez@correo.com",
                method="security_question",
                reset_code="firulais",
                new_password="NuevaClaveSegura2026!",
            ),
            db=test_db,
        )
    assert locked_exc.value.status_code == 429

    # Simular expiración del bloqueo limpiando recovery_locked_until en BD
    user = test_db.query(User).filter(User.username == "trader_valencia").first()
    user.recovery_locked_until = None
    user.failed_recovery_attempts = 0
    test_db.commit()

    # 3. Recuperación exitosa con respuesta normalizada (mayúsculas/espacios no afectan)
    res = reset_password(
        req=PasswordResetRequest(
            username="ana.perez@correo.com",
            method="security_question",
            reset_code="  FIRULAIS  ",
            new_password="NuevaClaveSegura2026!",
        ),
        db=test_db,
    )
    assert res["success"] is True

    # 4. Iniciar sesión con la nueva contraseña funciona
    logged = login(
        req=LoginRequest(username="trader_valencia", password="NuevaClaveSegura2026!"),
        db=test_db,
        settings=test_settings,
    )
    assert logged.access_token != ""


def test_reset_via_recovery_key_rotates_key_single_use(test_db, test_settings):
    """La Llave Maestra permite recuperar la cuenta sin Telegram y rota automáticamente tras un solo uso."""
    from fastapi import HTTPException

    from src.api.routes.auth import login, register, reset_password
    from src.api.schemas.auth import LoginRequest, PasswordResetRequest, RegisterRequest

    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        reg = register(
            req=RegisterRequest(
                username="trader_maracay",
                password="OldPassword2026!",
                email="maracay@p2p.ve",
            ),
            db=test_db,
            settings=test_settings,
        )

    first_key = reg.recovery_key
    assert first_key is not None

    # 1. Recuperar usando la primera Llave Maestra
    reset_res = reset_password(
        req=PasswordResetRequest(
            username="maracay@p2p.ve",
            method="recovery_key",
            reset_code=first_key,
            new_password="ResetViaMasterKey2026!",
        ),
        db=test_db,
    )
    assert reset_res["success"] is True
    new_key = reset_res.get("new_recovery_key")
    assert new_key is not None
    assert new_key.startswith("P2P-")
    assert new_key != first_key

    # 2. La llave vieja NO debe servir por segunda vez (Single-use Fail-Closed)
    with pytest.raises(HTTPException) as reuse_exc:
        reset_password(
            req=PasswordResetRequest(
                username="maracay@p2p.ve",
                method="recovery_key",
                reset_code=first_key,
                new_password="OtroIntentoPassword2026!",
            ),
            db=test_db,
        )
    assert reuse_exc.value.status_code == 400

    # 3. Verificar login con la contraseña restablecida
    logged = login(
        req=LoginRequest(username="trader_maracay", password="ResetViaMasterKey2026!"),
        db=test_db,
        settings=test_settings,
    )
    assert logged.user.username == "trader_maracay"


def test_update_recovery_profile_authenticated_endpoint(test_db):
    """Permite a usuarios existentes configurar correo, pregunta secreta y regenerar llave maestra."""
    from src.api.routes.auth import update_recovery_profile
    from src.api.schemas.auth import RecoveryProfileUpdateRequest
    from src.data.repositories import UserRepository

    repo = UserRepository(test_db)
    existing = repo.create_user(
        username="usuario_antiguo",
        password_hash=AuthService.hash_password("Clave12345!"),
        role="TRADER",
    )

    resp = update_recovery_profile(
        req=RecoveryProfileUpdateRequest(
            full_name="Luis Rojas",
            email="luis.rojas@trading.ve",
            security_question="¿En qué ciudad naciste?",
            security_answer="Barquisimeto",
            regenerate_recovery_key=True,
        ),
        db=test_db,
        current_user=existing,
    )

    assert resp["success"] is True
    assert resp["recovery_key"] is not None
    assert resp["recovery_key"].startswith("P2P-")
    assert existing.full_name == "Luis Rojas"
    assert existing.email == "luis.rojas@trading.ve"
    assert existing.security_question == "¿En qué ciudad naciste?"
    assert existing.security_answer_hash is not None
