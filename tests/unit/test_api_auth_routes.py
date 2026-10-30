"""Pruebas unitarias de las rutas de autenticación y Telegram SSO."""

import hashlib
import hmac
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_db, get_settings
from src.api.main import create_app
from src.data.database import Base
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TEST_BOT_TOKEN = "987654321:AAFakeBotToken_123456789ABC"


@pytest.fixture(autouse=True)
def mock_telegram():
    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        yield


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
def client(test_db):
    app = create_app(skip_lifespan=True)

    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
        TELEGRAM_BOT_TOKEN=TEST_BOT_TOKEN,
        TELEGRAM_ALLOWED_USER_IDS="111222333",
    )

    def override_get_db():
        yield test_db

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    return TestClient(app, base_url="http://127.0.0.1")


def test_login_success_and_me(client, test_db):
    """Verifica inicio de sesión exitoso y consulta del perfil /api/auth/me."""
    auth_svc = AuthService(db_session=test_db)
    auth_svc.ensure_default_admin(default_username="superadmin", default_password="SecretPassword123!")

    # 1. Login exitoso
    res = client.post("/api/auth/login", json={"username": "superadmin", "password": "SecretPassword123!"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "superadmin"
    assert data["user"]["role"] == "ADMIN"
    token = data["access_token"]

    # 2. Consultar perfil con token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["username"] == "superadmin"
    assert me_data["role"] == "ADMIN"


def test_login_invalid_password(client, test_db):
    """Garantiza respuesta 401 ante credenciales inválidas."""
    auth_svc = AuthService(db_session=test_db)
    auth_svc.ensure_default_admin(default_username="superadmin", default_password="SecretPassword123!")

    res = client.post("/api/auth/login", json={"username": "superadmin", "password": "WrongPassword"})
    assert res.status_code == 401
    assert "detail" in res.json()


def test_telegram_sso_auto_registers_and_assigns_role(client, test_db):
    """Verifica autenticación vía Telegram SSO: usuario autorizado obtiene ADMIN."""
    auth_date = int(time.time())
    tg_data = {
        "id": "111222333",  # En TELEGRAM_ALLOWED_USER_IDS
        "first_name": "Carlos",
        "username": "carlos_admin",
        "auth_date": str(auth_date),
    }
    # Firmar según spec Telegram
    secret = hashlib.sha256(TEST_BOT_TOKEN.encode()).digest()
    data_check_string = "\n".join(f"{k}={tg_data[k]}" for k in sorted(tg_data.keys()))
    tg_data["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()

    res = client.post("/api/auth/telegram", json=tg_data)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["user"]["telegram_id"] == "111222333"
    assert res_data["user"]["role"] == "ADMIN"
    assert "access_token" in res_data


def test_telegram_sso_unauthorized_user_gets_invitado(client, test_db):
    """Verifica que un usuario nuevo no listado en admins se cree como INVITADO."""
    auth_date = int(time.time())
    tg_data = {
        "id": "999888777",  # No está en allowed_users
        "first_name": "Nuevo",
        "username": "nuevo_usuario",
        "auth_date": str(auth_date),
    }
    secret = hashlib.sha256(TEST_BOT_TOKEN.encode()).digest()
    data_check_string = "\n".join(f"{k}={tg_data[k]}" for k in sorted(tg_data.keys()))
    tg_data["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()

    res = client.post("/api/auth/telegram", json=tg_data)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["user"]["telegram_id"] == "999888777"
    assert res_data["user"]["role"] == "INVITADO"


def test_register_new_user_and_login(client):
    """Verifica registro de un nuevo usuario e inicio de sesión subsecuente."""
    reg_res = client.post(
        "/api/auth/register",
        json={
            "username": "usuario_nuevo",
            "password": "Password123!",
            "telegram_id": "555444333",
        },
    )
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "usuario_nuevo"
    assert data["user"]["role"] == "INVITADO"

    # Duplicado debe responder 400
    dup_res = client.post(
        "/api/auth/register",
        json={"username": "usuario_nuevo", "password": "AnotherPassword!"},
    )
    assert dup_res.status_code == 400


def test_password_recovery_and_reset_flow(client):
    """Verifica el flujo completo de recuperación con OTP y cambio de contraseña."""
    # 1. Registrar usuario
    client.post(
        "/api/auth/register",
        json={"username": "recovery_user", "password": "InitialPass123!"},
    )

    # 2. Solicitar recuperación
    rec_res = client.post("/api/auth/recover-password", json={"username": "recovery_user"})
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["success"] is True
    # En entorno de prueba sin telegram bot real, retorna debug_code
    otp = rec_data.get("debug_code")
    assert otp is not None
    assert len(otp) == 6

    # 3. Restablecer con código incorrecto falla
    bad_reset = client.post(
        "/api/auth/reset-password",
        json={"username": "recovery_user", "reset_code": "000000", "new_password": "NewStrongPass999!"},
    )
    assert bad_reset.status_code == 400

    # 4. Restablecer con código correcto
    ok_reset = client.post(
        "/api/auth/reset-password",
        json={"username": "recovery_user", "reset_code": otp, "new_password": "NewStrongPass999!"},
    )
    assert ok_reset.status_code == 200
    assert ok_reset.json()["success"] is True

    # 5. Iniciar sesión con nueva contraseña
    login_res = client.post(
        "/api/auth/login",
        json={"username": "recovery_user", "password": "NewStrongPass999!"},
    )
    assert login_res.status_code == 200

