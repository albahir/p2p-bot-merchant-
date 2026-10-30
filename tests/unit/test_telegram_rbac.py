"""Tests unitarios para RBAC y aislamiento de roles en Telegram."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.repositories import UserRepository
from src.integrations.telegram_notifier import TelegramCommandPoller, TelegramNotifier
from src.security.auth_service import UserRole


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


def test_telegram_guest_menu_isolation():
    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001]
    )

    # Teclado para INVITADO
    guest_keyboard = notifier.get_persistent_menu_markup(role=UserRole.INVITADO.value)
    flat_buttons = [b["text"] for row in guest_keyboard["keyboard"] for b in row]
    assert "📈 Spreads P2P" in flat_buttons
    assert "🏛️ Tasa BCV" in flat_buttons
    assert "❓ Ayuda" in flat_buttons
    # No debe contener órdenes, conciliación ni sheets
    assert "⚖️ Conciliación" not in flat_buttons
    assert "🔄 Sheets" not in flat_buttons
    assert "📊 Estado" not in flat_buttons

    # Teclado para ADMIN o TRADER
    admin_keyboard = notifier.get_persistent_menu_markup(role=UserRole.ADMIN.value)
    admin_buttons = [b["text"] for row in admin_keyboard["keyboard"] for b in row]
    assert "⚖️ Conciliación" in admin_buttons
    assert "📊 Estado" in admin_buttons


def test_telegram_guest_command_restrictions(db_session):
    repo = UserRepository(db_session)
    repo.create_user(username="invitado1", password_hash="hash", role=UserRole.INVITADO.value, telegram_id="9999")
    repo.create_user(username="admin1", password_hash="hash", role=UserRole.ADMIN.value, telegram_id="1001")

    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001],
        session_factory=lambda: db_session
    )

    # 1. Invitado puede consultar /spread y /bcv
    res_spread = notifier.handle_command(user_id=9999, command="/spread")
    assert "⛔" not in res_spread

    res_bcv = notifier.handle_command(user_id=9999, command="/bcv")
    assert "⛔" not in res_bcv

    # 2. Invitado tiene PROHIBIDO consultar /cedula
    res_cedula = notifier.handle_command(user_id=9999, command="/cedula V-18234567")
    assert "Acceso Restringido" in res_cedula or "reservada" in res_cedula

    # 3. Invitado tiene PROHIBIDO pausar el bot
    res_pause = notifier.handle_command(user_id=9999, command="/pause")
    assert "Acceso Restringido" in res_pause or "reservada" in res_pause

    # 4. Invitado tiene PROHIBIDO conciliar
    res_concil = notifier.handle_command(user_id=9999, command="/conciliacion")
    assert "Acceso Restringido" in res_concil or "reservada" in res_concil


def test_telegram_admin_user_management_commands(db_session):
    repo = UserRepository(db_session)
    repo.create_user(username="admin1", password_hash="hash", role=UserRole.ADMIN.value, telegram_id="1001")

    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001],
        session_factory=lambda: db_session,
    )

    with patch.object(notifier, "send_alert", wraps=notifier.send_alert) as mock_send_alert:
        # 1. Admin autoriza a un nuevo usuario como TRADER
        res_auth = notifier.handle_command(user_id=1001, command="/autorizar 8888 TRADER")
        assert "autorizado exitosamente" in res_auth or "actualizado" in res_auth

        user_8888 = repo.get_by_telegram_id("8888")
        assert user_8888 is not None
        assert user_8888.role == "TRADER"
        # Debe haberse notificado al usuario 8888
        assert any(
            str(call.kwargs.get("chat_id")) == "8888" for call in mock_send_alert.call_args_list
        )

        # 2. Admin promueve usuario a ADMIN usando alias /promover
        mock_send_alert.reset_mock()
        res_promote = notifier.handle_command(user_id=1001, command="/promover 8888 ADMIN")
        assert "actualizado exitosamente" in res_promote
        promoted_user = repo.get_by_telegram_id("8888")
        assert promoted_user is not None
        assert promoted_user.role == "ADMIN"
        # Debe notificar al usuario sobre su promoción
        assert any(
            str(call.kwargs.get("chat_id")) == "8888" for call in mock_send_alert.call_args_list
        )

        # 3. Admin lista usuarios
        res_list = notifier.handle_command(user_id=1001, command="/usuarios")
        assert "8888" in res_list
        assert "ADMIN" in res_list

        # 4. Admin revoca usuario
        mock_send_alert.reset_mock()
        res_revoke = notifier.handle_command(user_id=1001, command="/revocar 8888")
        assert "revocado" in res_revoke or "desactivado" in res_revoke
        user_revoked = repo.get_by_telegram_id("8888")
        assert user_revoked is not None
        assert user_revoked.is_active is False
        # Debe notificar al usuario revocado
        assert any(
            str(call.kwargs.get("chat_id")) == "8888" for call in mock_send_alert.call_args_list
        )


def test_telegram_poller_unauthorized_user_approval_workflow(db_session):
    notifier = TelegramNotifier(
        bot_token="fake_token",
        default_chat_id="1001",
        allowed_user_ids=[1001],
        session_factory=lambda: db_session,
    )
    poller = TelegramCommandPoller(notifier=notifier)

    updates_payload = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "chat": {"id": 7777},
                    "from": {"id": 7777, "username": "nuevo_usuario", "first_name": "Juan"},
                    "text": "Hola bot",
                },
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = updates_payload

    sent_messages = []

    def fake_post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        sent_messages.append((url, kwargs.get("json", {})))
        return resp

    with patch.object(notifier._client, "get", return_value=mock_resp), patch.object(
        notifier._client, "post", side_effect=fake_post
    ):
        count = poller.poll_once()
        assert count == 1

    assert len(sent_messages) == 2
    user_msg = next(m[1] for m in sent_messages if str(m[1].get("chat_id")) == "7777")
    admin_msg = next(m[1] for m in sent_messages if str(m[1].get("chat_id")) == "1001")

    assert "pendiente de aprobación" in user_msg["text"]
    assert "7777" in admin_msg["text"]
    assert "inline_keyboard" in admin_msg["reply_markup"]
    assert any(
        "/autorizar 7777 INVITADO" in b["callback_data"]
        for row in admin_msg["reply_markup"]["inline_keyboard"]
        for b in row
    )

