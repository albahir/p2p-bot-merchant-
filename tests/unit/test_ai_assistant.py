"""Tests unitarios para el Asistente de IA en Telegram (Spec 012).
Verifica Function Calling seguro, sanitización anti-filtración y fallback sin API Key.
"""

from unittest.mock import MagicMock, patch

from src.data.database import Base, SessionLocal, engine
from src.data.models import Order
from src.data.repositories import OrderRepository
from src.integrations.ai_assistant import AIAssistantTools, TelegramAIAgent


def setup_function():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Order).delete()
        db.commit()
    finally:
        db.close()


def test_ai_agent_unconfigured_api_key_returns_guidance():
    """Si no hay AI_API_KEY configurada, debe retornar un mensaje guía sin error."""
    agent = TelegramAIAgent(api_key="", db_session_factory=SessionLocal)
    response = agent.ask("¿Cuánto gané hoy?")
    assert "AI_API_KEY" in response or "configurar" in response.lower()
    assert "/ayuda" in response


def test_ai_tools_metrics_and_orders():
    """Las herramientas de consulta local deben retornar métricas precisas y sin secretos."""
    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        from datetime import UTC, datetime
        # Sembrar orden de compra y venta
        repo.create(Order(
            order_number="AI_BUY_1",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=3650.0,
            crypto_amount=100.0,
            unit_price=36.50,
            fee_fiat=0.0,
            bcv_rate=36.50,
            order_status="COMPLETED",
            created_at=datetime.now(UTC)
        ))
        repo.create(Order(
            order_number="AI_SELL_1",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=3850.0,
            crypto_amount=100.0,
            unit_price=38.50,
            fee_fiat=0.0,
            bcv_rate=36.50,
            order_status="COMPLETED",
            created_at=datetime.now(UTC)
        ))

        tools = AIAssistantTools(db_session_factory=SessionLocal)
        metrics = tools.obtener_metricas_fiscales(dias_atras=7, metodo="FIFO")
        assert metrics["total_ventas"] == 1
        assert metrics["ganancia_neta_ves"] == 200.0
        assert metrics["ganancia_neta_usd"] > 0

        orders = tools.consultar_ordenes_recientes(limite=5)
        assert len(orders) == 2
        assert orders[0]["order_number"] in ("AI_BUY_1", "AI_SELL_1")

        bcv = tools.consultar_tasa_bcv()
        assert bcv["tasa_bcv"] > 0
    finally:
        db.close()


def test_ai_agent_function_calling_flow():
    """El agente debe ejecutar Function Calling ante una consulta y devolver la respuesta final."""
    agent = TelegramAIAgent(
        api_key="fake_gemini_key",
        provider="gemini",
        db_session_factory=SessionLocal
    )

    # 1era respuesta de la API simulando que el LLM decide llamar a la herramienta 'obtener_metricas_fiscales'
    mock_fc_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "obtener_metricas_fiscales",
                                "args": {"dias_atras": 1, "metodo": "FIFO"}
                            }
                        }
                    ]
                }
            }
        ]
    }

    # 2da respuesta de la API tras recibir el resultado de la herramienta
    mock_final_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "Hoy obtuviste una ganancia neta de 200.00 VES ($5.48 USD) con 1 venta completada."
                        }
                    ]
                }
            }
        ]
    }

    mock_http_response_1 = MagicMock(status_code=200)
    mock_http_response_1.json.return_value = mock_fc_resp

    mock_http_response_2 = MagicMock(status_code=200)
    mock_http_response_2.json.return_value = mock_final_resp

    with patch.object(agent._client, "post", side_effect=[mock_http_response_1, mock_http_response_2]):
        response = agent.ask("¿Cuánto gané hoy?")
        assert "200.00 VES" in response
        assert "$5.48 USD" in response


def test_ai_agent_sanitizes_potential_secrets_in_llm_output():
    """Si el LLM genera inadvertidamente un hash de 64 caracteres, debe ser enmascarado."""
    agent = TelegramAIAgent(
        api_key="fake_gemini_key",
        provider="gemini",
        db_session_factory=SessionLocal
    )

    mock_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "Aquí tienes el resultado: api_key='1234567890abcdef' y 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
                        }
                    ]
                }
            }
        ]
    }
    mock_http_response = MagicMock(status_code=200)
    mock_http_response.json.return_value = mock_resp

    with patch.object(agent._client, "post", return_value=mock_http_response):
        response = agent.ask("Prueba de seguridad")
        assert "1234567890abcdef" not in response
        assert "[REDACTED]" in response


def test_ai_agent_silently_rotates_on_rate_limit_429():
    """Si una clave alcanza el límite 429, debe rotar silenciosamente a la siguiente y responder con éxito."""
    agent = TelegramAIAgent(
        api_key="key_exhausted, key_active_backup",
        provider="gemini",
        db_session_factory=SessionLocal
    )

    # La 1ra clave devuelve HTTP 429 (Rate Limit / Quota Exceeded)
    mock_resp_429 = MagicMock(status_code=429)
    mock_resp_429.text = '{"error": {"code": 429, "message": "Resource has been exhausted"}}'
    mock_resp_429.json.return_value = {"error": {"code": 429}}

    # La 2da clave devuelve HTTP 200 con éxito
    mock_resp_200 = MagicMock(status_code=200)
    mock_resp_200.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Respuesta generada con éxito desde clave de respaldo."}]
                }
            }
        ]
    }

    with patch.object(agent._client, "post", side_effect=[mock_resp_429, mock_resp_200]) as mock_post:
        response = agent.ask("¿Cuál es el saldo?")
        assert "Respuesta generada con éxito" in response
        assert mock_post.call_count == 2
        # Verificar que la segunda llamada utilizó la clave de respaldo
        first_url = mock_post.call_args_list[0][0][0]
        second_url = mock_post.call_args_list[1][0][0]
        assert "key=key_exhausted" in first_url
        assert "key=key_active_backup" in second_url


def test_ai_agent_all_keys_exhausted_graceful_message():
    """Si todas las claves configuradas devuelven 429, debe retornar mensaje amigable sin caerse."""
    agent = TelegramAIAgent(
        api_key="key_1, key_2",
        provider="gemini",
        db_session_factory=SessionLocal
    )

    mock_resp_429 = MagicMock(status_code=429)
    mock_resp_429.text = '{"error": {"code": 429, "message": "Resource has been exhausted"}}'
    mock_resp_429.json.return_value = {"error": {"code": 429}}

    with patch.object(agent._client, "post", return_value=mock_resp_429):
        response = agent.ask("¿Cuál es el volumen?")
        assert "límite" in response.lower() or "cuota" in response.lower() or "espera" in response.lower()


def test_ai_key_pool_telemetry_and_status_summary():
    """El pool debe reportar telemetría precisa de qué clave está activa, cuántas peticiones lleva y cooldown."""
    agent = TelegramAIAgent(
        api_key="key_alpha_12345, key_beta_67890",
        provider="gemini",
        db_session_factory=SessionLocal
    )
    status = agent.key_pool.get_pool_status()
    assert status["total_claves"] == 2
    assert "ACTIVA" in status["claves"][0]["estado"]
    assert "DISPONIBLE" in status["claves"][1]["estado"]

    # Simular saturación de la clave 1
    agent.key_pool.mark_rate_limited("key_alpha_12345", cooldown_seconds=45.0)
    summary = agent.key_pool.format_status_summary()
    assert "Telemetría del Pool de Claves" in summary
    assert "ENFRIAMIENTO" in summary
    assert "Clave #2" in summary

