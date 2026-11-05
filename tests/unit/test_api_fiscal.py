"""Pruebas unitarias de las rutas de reconciliación fiscal de 6 piezas."""

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


def test_fiscal_summary_authenticated_trader(app_client, test_db):
    """Verifica que un TRADER pueda consultar el resumen de la ecuación de 6 piezas."""
    auth_svc = AuthService(db_session=test_db)
    trader = auth_svc.user_repo.create_user(
        username="trader_fiscal",
        password_hash=auth_svc.hash_password("Pass123!"),
        role="TRADER",
    )
    token = create_access_token({"sub": str(trader.id), "username": "trader_fiscal", "role": "TRADER"}, TEST_SECRET)

    res = app_client.get(
        "/api/fiscal/summary?period=2026-10&initial_balance=1000&actual_final_balance=1200",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["period"] == "2026-10"
    assert "calculated_final_balance" in data
    assert "discrepancy" in data
    assert "gross_revenue_ves" in data


def test_fiscal_summary_forbidden_for_invitado(app_client, test_db):
    """Garantiza que un INVITADO no pueda acceder a datos fiscales (Fail-closed RBAC)."""
    auth_svc = AuthService(db_session=test_db)
    guest = auth_svc.user_repo.create_user(
        username="guest_fiscal",
        password_hash=auth_svc.hash_password("Pass123!"),
        role="INVITADO",
    )
    token = create_access_token({"sub": str(guest.id), "username": "guest_fiscal", "role": "INVITADO"}, TEST_SECRET)

    res = app_client.get(
        "/api/fiscal/summary?period=2026-10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
