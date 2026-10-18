"""Tests unitarios para la autenticación y control de vistas en el Dashboard."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.security.auth_service import AuthService, UserRole


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_dashboard_user_authentication(db_session):
    auth = AuthService(db_session=db_session)
    auth.ensure_default_admin()

    # Autenticación exitosa del admin por defecto
    admin = auth.authenticate_user("admin", "AdminP2P2026!")
    assert admin is not None
    assert admin.role == UserRole.ADMIN.value

    # Contraseña incorrecta falla
    fail_pass = auth.authenticate_user("admin", "wrong_password")
    assert fail_pass is None

    # Usuario inexistente falla
    fail_user = auth.authenticate_user("no_user", "123456")
    assert fail_user is None


def test_dashboard_role_tab_definitions():
    """Verifica que los roles determinen los conjuntos exactos de pestañas sin exponer datos a INVITADO."""
    from src.reporting.dashboard.app import get_visible_tabs_for_role

    guest_tabs = get_visible_tabs_for_role("INVITADO")
    assert guest_tabs == ["📈 Monitor & Arbitraje P2P"]
    assert "📊 Visión General" not in guest_tabs
    assert "🧾 Comprobantes OCR" not in guest_tabs
    assert "🔑 Credenciales" not in guest_tabs
    assert "👤 Directorio Cédulas" not in guest_tabs

    trader_tabs = get_visible_tabs_for_role("TRADER")
    assert "📊 Visión General" in trader_tabs
    assert "📈 Monitor & Arbitraje P2P" in trader_tabs
    assert "👤 Directorio Cédulas" in trader_tabs
    assert "🧾 Comprobantes OCR" in trader_tabs
    assert "⚖️ Reconstrucción 6 Piezas" in trader_tabs
    assert "🔑 Credenciales" not in trader_tabs
    assert "🕹️ Panel de Tareas" not in trader_tabs

    admin_tabs = get_visible_tabs_for_role("ADMIN")
    assert "📊 Visión General" in admin_tabs
    assert "👤 Directorio Cédulas" in admin_tabs
    assert "🔑 Credenciales" in admin_tabs
    assert "🕹️ Panel de Tareas" in admin_tabs
    assert len(admin_tabs) == 11
