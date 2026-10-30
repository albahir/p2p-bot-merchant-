"""Pruebas unitarias de las rutas de gestión de usuarios (RBAC) y control del bot."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_db, get_settings
from src.api.main import create_app
from src.api.security import create_access_token
from src.data.database import Base
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


@pytest.fixture(autouse=True)
def mock_telegram_notifier(monkeypatch):
    """Evita llamadas reales a Telegram en pruebas unitarias."""
    from src.integrations.telegram_notifier import TelegramNotifier
    monkeypatch.setattr(TelegramNotifier, "send_alert", lambda *args, **kwargs: True)


@pytest.fixture
def app_client(test_db):
    app = create_app(skip_lifespan=True)
    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
    )

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    return TestClient(app, base_url="http://127.0.0.1")


def test_users_list_admin_only(app_client, test_db):
    """Verifica que solo administradores puedan consultar la lista de usuarios."""
    auth_svc = AuthService(db_session=test_db)
    admin = auth_svc.ensure_default_admin(default_username="admin1")
    trader = auth_svc.user_repo.create_user(
        username="trader1",
        password_hash=auth_svc.hash_password("Pass123!"),
        role="TRADER",
    )

    token_trader = create_access_token({"sub": str(trader.id), "username": "trader1", "role": "TRADER"}, TEST_SECRET)
    token_admin = create_access_token({"sub": str(admin.id), "username": "admin1", "role": "ADMIN"}, TEST_SECRET)

    # 1. TRADER intenta listar usuarios -> 403 Forbidden
    res_trader = app_client.get("/api/users", headers={"Authorization": f"Bearer {token_trader}"})
    assert res_trader.status_code == 403

    # 2. ADMIN lista usuarios -> 200 OK
    res_admin = app_client.get("/api/users", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200
    users = res_admin.json()
    assert len(users) >= 2


def test_users_update_role(app_client, test_db, monkeypatch):
    """Verifica la actualización de roles RBAC por parte de un administrador."""
    from src.integrations.telegram_notifier import TelegramNotifier
    monkeypatch.setattr(TelegramNotifier, "send_alert", lambda *args, **kwargs: True)

    auth_svc = AuthService(db_session=test_db)
    admin = auth_svc.ensure_default_admin(default_username="admin1")
    user = auth_svc.user_repo.create_user(
        username="guest_user",
        password_hash=auth_svc.hash_password("Pass123!"),
        role="INVITADO",
        telegram_id="555666777",
    )

    token_admin = create_access_token({"sub": str(admin.id), "username": "admin1", "role": "ADMIN"}, TEST_SECRET)

    res = app_client.patch(
        f"/api/users/{user.id}/role",
        json={"role": "TRADER"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["role"] == "TRADER"


def test_bot_status_and_pause_resume(app_client, test_db):
    """Verifica lectura de estado y pausa/reanudación operativa del bot."""
    auth_svc = AuthService(db_session=test_db)
    admin = auth_svc.ensure_default_admin(default_username="admin_bot")
    token_admin = create_access_token({"sub": str(admin.id), "username": "admin_bot", "role": "ADMIN"}, TEST_SECRET)

    # 1. Estado inicial
    res_status = app_client.get("/api/bot/status", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_status.status_code == 200
    assert "is_running" in res_status.json()

    # 2. Pausar bot
    res_pause = app_client.post("/api/bot/pause", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_pause.status_code == 200
    assert res_pause.json()["is_paused"] is True

    # 3. Reanudar bot
    res_resume = app_client.post("/api/bot/resume", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_resume.status_code == 200
    assert res_resume.json()["is_paused"] is False
