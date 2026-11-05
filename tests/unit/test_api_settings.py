"""Pruebas unitarias para gestión cifrada de credenciales Binance y verificación en vivo."""

from unittest.mock import MagicMock, patch

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
def client_and_token(test_db):
    app = create_app(skip_lifespan=True)
    test_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
    )

    def override_get_db():
        yield test_db

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Crear admin y obtener token
    auth_svc = AuthService(db_session=test_db)
    auth_svc.ensure_default_admin(default_username="admin_test", default_password="AdminPass123!")

    client = TestClient(app, base_url="http://127.0.0.1")
    login_res = client.post("/api/auth/login", json={"username": "admin_test", "password": "AdminPass123!"})
    token = login_res.json()["access_token"]

    return client, token


def test_binance_settings_lifecycle(client_and_token):
    """Verifica consulta inicial, guardado cifrado y consulta posterior."""
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Estado inicial sin claves
    get_res = client.get("/api/settings/binance", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["is_configured"] is False
    assert data["api_key_masked"] == "No configurada"

    # 2. Guardar claves válidas
    save_res = client.post(
        "/api/settings/binance",
        headers=headers,
        json={
            "api_key": "vm4Pabcd1234567890efghXk9b",
            "secret_key": "SecretPayload1234567890SecretPayload!",
            "key_type": "HMAC",
        },
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["is_configured"] is True
    assert "vm4P" in save_data["api_key_masked"]
    assert "Xk9b" in save_data["api_key_masked"]
    # Comprobar que no se filtra el secreto
    assert "SecretPayload" not in save_res.text

    # 3. Consulta posterior refleja configuración activa
    get_res2 = client.get("/api/settings/binance", headers=headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["is_configured"] is True


def test_binance_verify_connection_mocked(client_and_token):
    """Verifica endpoint de diagnóstico en caliente con respuesta mockeada de Binance."""
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # Guardar credencial primero
    client.post(
        "/api/settings/binance",
        headers=headers,
        json={
            "api_key": "vm4Pabcd1234567890efghXk9b",
            "secret_key": "SecretPayload1234567890SecretPayload!",
            "key_type": "HMAC",
        },
    )

    # Simular respuesta de Binance API
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"serverTime": 1700000000000}
    mock_response.headers = {"x-mbx-used-weight-1m": "12"}

    with patch("httpx.Client.get", return_value=mock_response):
        res = client.post("/api/settings/binance/verify", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["is_connected"] is True
        assert data["used_weight"] == 12
        assert data["is_weight_safe"] is True
        assert "Conexión Binance 100% activa" in data["message"]
