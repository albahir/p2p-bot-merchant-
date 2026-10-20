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


def test_rate_alert_service_deduplication_anti_spam():
    """Valida que alertas consecutivas con las mismas tasas NO se reenvíen (anti-spam)."""
    from src.core.spread_monitor import BankRateQuote

    # Cooldown de 0 segundos para probar la lógica de deduplicación de tasas
    service = RateAlertService(cooldown_seconds=0)
    quotes = [
        BankRateQuote(bank_name="Banco Activo", buy_rate=998.50, sell_rate=1000.0),
        BankRateQuote(bank_name="Banesco", buy_rate=1005.0, sell_rate=1021.0),
    ]

    # Primera vez: debe emitir alerta
    first_alert = service.check_spread_opportunities(quotes)
    assert first_alert is not None
    assert "ARBITRAJE" in first_alert

    # Segunda vez inmediatamente con las mismas tasas exactas: debe retornar None (DEDUPLICADO)
    second_alert = service.check_spread_opportunities(quotes)
    assert second_alert is None, "No debe reenviar la misma alerta con precios idénticos"


def test_rate_alert_service_fires_on_significant_price_movement():
    """Valida que si las tasas se mueven significativamente (>= 0.50 VES), se emite la nueva alerta."""
    from src.core.spread_monitor import BankRateQuote

    service = RateAlertService(cooldown_seconds=0)
    quotes_initial = [
        BankRateQuote(bank_name="Banco Activo", buy_rate=998.50, sell_rate=1000.0),
        BankRateQuote(bank_name="Banesco", buy_rate=1005.0, sell_rate=1021.0),
    ]
    service.check_spread_opportunities(quotes_initial)

    # Movimiento insignificante (< 0.50 VES y < 0.20% spread): 1021.0 -> 1021.10
    quotes_tiny_shift = [
        BankRateQuote(bank_name="Banco Activo", buy_rate=998.50, sell_rate=1000.0),
        BankRateQuote(bank_name="Banesco", buy_rate=1005.0, sell_rate=1021.10),
    ]
    assert service.check_spread_opportunities(quotes_tiny_shift) is None

    # Movimiento significativo (>= 0.50 VES): 1021.0 -> 1026.0 (+5 VES)
    quotes_major_shift = [
        BankRateQuote(bank_name="Banco Activo", buy_rate=998.50, sell_rate=1000.0),
        BankRateQuote(bank_name="Banesco", buy_rate=1005.0, sell_rate=1026.0),
    ]
    major_alert = service.check_spread_opportunities(quotes_major_shift)
    assert major_alert is not None
    assert "1,026.00" in major_alert


def test_rate_alert_service_anti_flapping_regression_prevention():
    """Valida que una tasa con fecha anterior (Lunes 19) sea descartada si ya se conoce la del Martes 20."""
    service = RateAlertService(cooldown_seconds=0)

    # 1. Registrar tasa de Martes 20 de Octubre
    alert_tue = service.check_bcv_rate_change(current_rate=881.88, fecha_valor="Martes, 20 Octubre 2026")
    # Primera tasa registrada como base
    assert alert_tue is None
    assert service.last_known_bcv_rate == 881.88

    # 2. Llega respuesta rezagada de CDN con Lunes 19 de Octubre
    alert_mon = service.check_bcv_rate_change(current_rate=881.07, fecha_valor="Lunes, 19 Octubre 2026")
    # Debe ser filtrada por fecha anterior
    assert alert_mon is None, "No debe degradar a una fecha anterior ya superada"
    assert service.last_known_bcv_rate == 881.88


def test_rate_alert_service_anti_oscillation_debounce():
    """Valida que la oscilación entre dos tasas dentro de la ventana de 30 minutos no dispare spam."""
    service = RateAlertService(cooldown_seconds=0)
    service.last_known_bcv_rate = 880.0

    # Primer cambio genuino a 881.88
    alert1 = service.check_bcv_rate_change(current_rate=881.88, fecha_valor="Martes, 20 Octubre 2026")
    assert alert1 is not None

    # Supongamos que la fecha es idéntica pero la tasa oscila hacia 881.07
    alert2 = service.check_bcv_rate_change(current_rate=881.07, fecha_valor="Martes, 20 Octubre 2026")
    assert alert2 is not None

    # La tasa vuelve a oscilar inmediatamente a 881.88 (ya vista en los últimos 30 min)
    alert3 = service.check_bcv_rate_change(current_rate=881.88, fecha_valor="Martes, 20 Octubre 2026")
    assert alert3 is None, "Debe suprimir la oscilación repetitiva de CDN"


def test_telegram_matrix_formatting_deduplication():
    """Valida que el reporte de matriz en Telegram deduplique bancos y no muestre '+-'."""
    from src.core.spread_monitor import BankRateQuote
    from src.integrations.telegram_notifier import TelegramNotifier

    quotes = [
        BankRateQuote(bank_name="BBVA Provincial", buy_rate=1010.0, sell_rate=1009.0, total_ads=50),
        BankRateQuote(bank_name="BBVA Provincial", buy_rate=1014.0, sell_rate=1009.0, total_ads=10),
        BankRateQuote(bank_name="Banesco", buy_rate=1012.0, sell_rate=1006.0, total_ads=100),
    ]

    report = TelegramNotifier.format_arbitrage_matrix_report(
        quotes=quotes,
        bcv_rate=881.88,
        bcv_gap=14.50,
    )

    # No debe tener '+-' en ningún punto
    assert "+-" not in report
    assert "++" not in report

    # BBVA Provincial solo debe aparecer una vez en el encabezado de cotizaciones
    lines = report.splitlines()
    provincial_headers = [l for l in lines if "*BBVA Provincial*:" in l]
    assert len(provincial_headers) == 1


