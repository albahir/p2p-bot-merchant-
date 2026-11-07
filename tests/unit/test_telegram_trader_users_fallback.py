"""Tests unitarios (TDD) para la preservación de roles de Trader mediante TELEGRAM_TRADER_USERS.
Garantiza que ningún Trader pierda su rol al reiniciar el bot o reconstruir contenedores.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from src.data.database import Base
from src.data.models import User
from src.integrations.telegram_notifier import TelegramNotifier


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_settings_parses_telegram_trader_users(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TRADER_USERS", "6326947793, 88888888, invalid_id, 99999999")
    settings = Settings()
    assert settings.telegram_trader_users == [6326947793, 88888888, 99999999]


def test_telegram_notifier_returns_trader_role_from_static_fallback(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TRADER_USERS", "77777777")
    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001],
        trader_user_ids=[77777777],
    )
    # Admin configurado estáticamente
    assert notifier.get_user_role(1001) == "ADMIN"
    # Trader configurado estáticamente
    assert notifier.get_user_role(77777777) == "TRADER"
    # Usuario desconocido
    assert notifier.get_user_role(9999) == "NONE"


def test_telegram_notifier_promotes_invitado_if_in_trader_whitelist(monkeypatch):
    sm = setup_in_memory_db()
    db = sm()
    # Usuario en DB con rol INVITADO (ej. tras un reinicio de DB)
    user = User(
        username="trader_carlos",
        password_hash="fakehash",
        role="INVITADO",
        telegram_id="77777777",
        is_active=True,
    )
    db.add(user)
    db.commit()

    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001],
        trader_user_ids=[77777777],
        session_factory=sm,
    )

    # Debe retornar TRADER y proteger el acceso del operador
    role = notifier.get_user_role("77777777")
    assert role == "TRADER"


def test_api_auth_register_assigns_trader_role_from_whitelist(monkeypatch):
    from src.api.routes.auth import register
    from src.api.schemas.auth import RegisterRequest

    sm = setup_in_memory_db()
    db = sm()
    settings = Settings(TELEGRAM_TRADER_USER_IDS="88889999", TELEGRAM_ALLOWED_USER_IDS="1001")

    req = RegisterRequest(
        username="operador_otc",
        password="SuperPassword123",
        telegram_id="88889999",
    )
    resp = register(req=req, db=db, settings=settings)
    assert resp.user.role == "TRADER"
    assert resp.user.username == "operador_otc"


def test_usuarios_command_lists_static_env_users_even_after_db_reset():
    """Tras un commit o reinicio en Render (BD vacía), /usuarios debe mostrar los IDs blindados en .env."""
    sm = setup_in_memory_db()
    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="6326947793",
        allowed_user_ids=[6326947793],
        trader_user_ids=[6430765245, 8522428625, 5570646610],
        session_factory=sm,
    )

    output = notifier.handle_command(user_id=6326947793, command="/usuarios")
    assert "6326947793" in output
    assert "6430765245" in output
    assert "8522428625" in output
    assert "5570646610" in output
    assert "ADMIN" in output
    assert "TRADER" in output
    assert "Blindado (.env)" in output


def test_seed_env_operators_and_postgres_url_normalization():
    """Verifica que al arrancar el contenedor se pueblen en BD todos los Admins/Traders de .env y se normalice postgres://."""
    from src.data.database import normalize_database_url, seed_env_operators
    from src.data.repositories import UserRepository

    assert (
        normalize_database_url("postgres://user:pass@ep-cool.eu-central-1.aws.neon.tech/neondb")
        == "postgresql+psycopg2://user:pass@ep-cool.eu-central-1.aws.neon.tech/neondb"
    )
    assert (
        normalize_database_url("postgresql://user:pass@ep-cool.eu-central-1.aws.neon.tech/neondb")
        == "postgresql+psycopg2://user:pass@ep-cool.eu-central-1.aws.neon.tech/neondb"
    )

    sm = setup_in_memory_db()
    db = sm()
    settings = Settings(
        TELEGRAM_ALERT_CHAT_ID="6326947793",
        TELEGRAM_ALLOWED_USER_IDS="6326947793",
        TELEGRAM_TRADER_USER_IDS="6430765245,8522428625,5570646610",
    )

    counts = seed_env_operators(db, settings)
    assert counts == {"admins": 1, "traders": 3}

    repo = UserRepository(db)
    all_users = repo.list_all()
    assert len(all_users) == 4
    roles_by_tg = {str(u.telegram_id): str(u.role) for u in all_users}
    assert roles_by_tg["6326947793"] == "ADMIN"
    assert roles_by_tg["6430765245"] == "TRADER"
    assert roles_by_tg["8522428625"] == "TRADER"
    assert roles_by_tg["5570646610"] == "TRADER"
    db.close()




