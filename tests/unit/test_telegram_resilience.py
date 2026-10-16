"""Tests unitarios de resiliencia para el servicio de notificaciones de Telegram.
Verifica fallback de Markdown ante HTTP 400, manejo de Rate Limit HTTP 429 y cola en background.
"""

from unittest.mock import MagicMock, patch

from src.integrations.telegram_notifier import (
    TelegramCommandPoller,
    TelegramNotifier,
    TelegramQueueDispatcher,
)


def test_markdown_syntax_error_falls_back_to_plain_text():
    """Si Telegram rechaza el formato Markdown (HTTP 400), debe reenviarse automáticamente como texto plano."""
    notifier = TelegramNotifier(bot_token="test_token", default_chat_id="12345")

    # Simulamos: 1er intento da HTTP 400 (error de parseo Markdown), 2do intento da HTTP 200 (texto plano)
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Bad Request: can't parse entities: Character '_' is reserved"
    mock_resp_400.json.return_value = {"ok": False, "description": mock_resp_400.text}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.text = '{"ok": true}'
    mock_resp_200.json.return_value = {"ok": True}

    with patch.object(notifier._client, "post", side_effect=[mock_resp_400, mock_resp_200]) as mock_post:
        success = notifier.send_alert("Aviso: Orden SIM_BUY_123 procesada")
        assert success is True
        assert mock_post.call_count == 2
        # El segundo intento no debe incluir parse_mode="Markdown"
        second_payload = mock_post.call_args_list[1][1]["json"]
        assert "parse_mode" not in second_payload or second_payload["parse_mode"] is None


def test_rate_limit_429_handles_backoff():
    """Si Telegram responde con HTTP 429 (Flood control), debe reintentar respetando retry_after."""
    notifier = TelegramNotifier(bot_token="test_token", default_chat_id="12345")

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = '{"ok": false, "parameters": {"retry_after": 1}}'
    mock_resp_429.json.return_value = {"ok": False, "parameters": {"retry_after": 1}}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"ok": True}

    with (
        patch.object(notifier._client, "post", side_effect=[mock_resp_429, mock_resp_200]),
        patch("time.sleep") as mock_sleep,
    ):
        success = notifier.send_alert("Alerta de prueba")
        assert success is True
        mock_sleep.assert_called_with(1)


def test_queue_dispatcher_processes_asynchronously():
    """La cola de despacho en segundo plano debe enviar alertas sin bloquear el flujo principal."""
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send_alert.return_value = True

    dispatcher = TelegramQueueDispatcher(notifier)
    dispatcher.start()
    try:
        dispatcher.queue_alert("Mensaje en cola 1")
        dispatcher.queue_alert("Mensaje en cola 2")
        dispatcher.wait_until_empty(timeout=3.0)
        assert notifier.send_alert.call_count == 2
    finally:
        dispatcher.stop()


def test_command_poller_processes_authorized_command():
    """El poller de comandos debe recibir actualizaciones de getUpdates y responder al chat."""
    notifier = TelegramNotifier(
        bot_token="test_token",
        default_chat_id="12345",
        allowed_user_ids=[6326947793]
    )

    poller = TelegramCommandPoller(notifier, poll_interval=0.1)

    # Simular una respuesta de getUpdates
    fake_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1001,
                "message": {
                    "message_id": 50,
                    "from": {"id": 6326947793},
                    "chat": {"id": 6326947793},
                    "text": "/status"
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_updates

    with (
        patch.object(notifier._client, "get", return_value=mock_resp),
        patch.object(notifier, "send_alert", return_value=True) as mock_send,
    ):
        count = poller.poll_once()
        assert count == 1
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert "Estado del Bot" in args[0]
        assert kwargs.get("chat_id") == "6326947793"
