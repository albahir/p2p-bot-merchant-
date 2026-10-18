"""Tests unitarios para interactividad de Telegram (Keyboards, Callbacks) y Alertas de Cambio en BCV/Spreads."""

from unittest.mock import MagicMock, patch

from src.core.rate_alert_service import RateAlertService
from src.integrations.telegram_notifier import (
    TelegramCommandPoller,
    TelegramNotifier,
)


def test_telegram_notifier_keyboards_and_markup():
    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="1001", allowed_user_ids=[1001])

    # 1. Inline keyboard markup
    inline_markup = notifier.get_quick_actions_markup()
    assert "inline_keyboard" in inline_markup
    buttons = [btn["callback_data"] for row in inline_markup["inline_keyboard"] for btn in row]
    assert "/spread" in buttons
    assert "/bcv" in buttons
    assert "/status" in buttons

    # 2. Reply keyboard persistent menu
    reply_markup = notifier.get_persistent_menu_markup()
    assert "keyboard" in reply_markup
    assert reply_markup.get("resize_keyboard") is True

    # 3. send_alert con reply_markup
    with patch.object(notifier._client, "post") as mock_post:
        mock_post.return_value.status_code = 200
        sent = notifier.send_alert("Mensaje con botones", reply_markup=inline_markup)
        assert sent is True
        payload = mock_post.call_args[1]["json"]
        assert payload.get("reply_markup") == inline_markup

    # 4. answer_callback_query
    with patch.object(notifier._client, "post") as mock_post:
        mock_post.return_value.status_code = 200
        answered = notifier.answer_callback_query(callback_query_id="query_123", text="Procesando...")
        assert answered is True
        payload = mock_post.call_args[1]["json"]
        assert payload["callback_query_id"] == "query_123"


def test_telegram_command_bcv():
    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="1001", allowed_user_ids=[1001])
    res = notifier.handle_command(user_id=1001, command="/bcv")
    assert "BCV" in res
    assert "USD" in res
    assert "Brecha" in res or "P2P" in res


def test_telegram_poller_handles_callback_query():
    notifier = TelegramNotifier(bot_token="fake_token", default_chat_id="1001", allowed_user_ids=[1001])
    poller = TelegramCommandPoller(notifier=notifier, poll_interval=1.0)

    sample_update = {
        "update_id": 12345,
        "callback_query": {
            "id": "cb_999",
            "from": {"id": 1001},
            "message": {"chat": {"id": 1001}},
            "data": "/bcv",
        },
    }

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"ok": True, "result": [sample_update]}

    with (
        patch.object(notifier._client, "get", return_value=mock_res),
        patch.object(notifier, "answer_callback_query", return_value=True) as mock_answer,
        patch.object(notifier, "send_alert", return_value=True) as mock_send,
    ):
        processed = poller.poll_once()
        assert processed == 1
        assert mock_answer.called
        assert mock_send.called
        call_text = mock_send.call_args[0][0]
        assert "BCV" in call_text


def test_rate_alert_service_bcv_change_detection():
    service = RateAlertService(cooldown_seconds=0)
    service.last_known_bcv_rate = 820.0

    # Tasa idéntica: sin alerta
    alert_none = service.check_bcv_rate_change(current_rate=820.0, fecha_valor="16 Octubre")
    assert alert_none is None

    # Tasa modificada: emite alerta
    alert = service.check_bcv_rate_change(current_rate=835.50, fecha_valor="17 Octubre")
    assert alert is not None
    assert "CAMBIO EN TASA OFICIAL BCV" in alert
    assert "820.00" in alert
    assert "835.50" in alert
    assert service.last_known_bcv_rate == 835.50


def test_rate_alert_service_arbitrage_opportunity():
    from src.core.spread_monitor import BankRateQuote

    service = RateAlertService(cooldown_seconds=0)
    quotes = [
        BankRateQuote(bank_name="Banco de Venezuela", buy_rate=1000.0, sell_rate=1005.0),
        BankRateQuote(bank_name="Bancamiga", buy_rate=1010.0, sell_rate=1025.0),
    ]

    alert = service.check_spread_opportunities(quotes)
    assert alert is not None
    assert "ARBITRAJE" in alert
    assert "Banco de Venezuela" in alert
    assert "Bancamiga" in alert
