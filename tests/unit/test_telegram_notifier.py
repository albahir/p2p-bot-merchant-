"""Tests unitarios para TelegramNotifier (sanitización de secretos y control de comandos)."""

from src.integrations.telegram_notifier import TelegramNotifier, sanitize_message


def test_sanitize_message_redacts_secrets():
    message_with_secrets = "Error de conexión: api_key='a1b2c3d4e5f6g7h8' y token: 1234567890abcdef"
    clean = sanitize_message(message_with_secrets)
    assert "a1b2c3d4e5f6g7h8" not in clean
    assert "[REDACTED]" in clean

def test_unauthorized_user_is_blocked():
    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="123", allowed_user_ids=[1001, 1002])
    # Usuario no autorizado intenta pausar
    res = notifier.handle_command(user_id=9999, command="/pause")
    assert "Acceso denegado" in res
    assert notifier.is_paused is False

def test_authorized_user_can_pause_and_resume():
    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="123", allowed_user_ids=[1001])
    res_pause = notifier.handle_command(user_id=1001, command="/pause")
    assert notifier.is_paused is True
    assert "pausadas" in res_pause

    res_resume = notifier.handle_command(user_id=1001, command="/resume")
    assert notifier.is_paused is False
    assert "reanudadas" in res_resume
