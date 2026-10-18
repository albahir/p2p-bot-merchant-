"""Tests unitarios para AuthService, UserRepository y roles RBAC."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.repositories import UserRepository
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


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = AuthService.hash_password(password)

    assert hashed != password
    assert hashed.startswith("pbkdf2_sha256$")
    assert AuthService.verify_password(password, hashed) is True
    assert AuthService.verify_password("WrongPassword!", hashed) is False


def test_user_repository_crud(db_session):
    repo = UserRepository(db_session)

    # 1. Crear usuario
    password_hash = AuthService.hash_password("TraderPass2026")
    user = repo.create_user(
        username="carlos_trader",
        password_hash=password_hash,
        role=UserRole.TRADER.value,
        telegram_id="11223344"
    )

    assert user.id is not None
    assert user.username == "carlos_trader"
    assert user.role == "TRADER"
    assert user.telegram_id == "11223344"
    assert user.is_active is True

    # 2. Consultar por username y telegram_id
    by_user = repo.get_by_username("carlos_trader")
    assert by_user is not None
    assert by_user.id == user.id

    by_tg = repo.get_by_telegram_id("11223344")
    assert by_tg is not None
    assert by_tg.id == user.id

    # 3. Actualizar rol
    updated = repo.update_role(user.id, UserRole.INVITADO.value)
    assert updated is not None
    assert updated.role == "INVITADO"

    # 4. Desactivar usuario
    deactivated = repo.set_active_status(user.id, is_active=False)
    assert deactivated is not None
    assert deactivated.is_active is False


def test_auth_service_authenticate(db_session):
    repo = UserRepository(db_session)
    auth = AuthService(repo)

    # Crear usuario
    repo.create_user(
        username="elena",
        password_hash=AuthService.hash_password("ElenaSecret123"),
        role=UserRole.TRADER.value
    )

    # Autenticación exitosa
    user = auth.authenticate("elena", "ElenaSecret123")
    assert user is not None
    assert user.username == "elena"
    assert user.role == "TRADER"

    # Autenticación fallida por contraseña
    assert auth.authenticate("elena", "BadPassword") is None

    # Autenticación fallida por usuario inexistente
    assert auth.authenticate("no_existe", "Password123") is None


def test_auth_service_seeding_default_admin(db_session):
    repo = UserRepository(db_session)
    auth = AuthService(repo)

    # Seeding con admin inicial
    admin = auth.ensure_default_admin(
        admin_telegram_id="6326947793",
        default_username="admin",
        default_password="AdminInitialPassword2026!"
    )

    assert admin is not None
    assert admin.username == "admin"
    assert admin.role == "ADMIN"
    assert admin.telegram_id == "6326947793"

    # Llamar de nuevo no duplica el admin
    admin_again = auth.ensure_default_admin(
        admin_telegram_id="6326947793",
        default_username="admin"
    )
    assert admin_again.id == admin.id
    assert len(repo.list_all()) == 1
