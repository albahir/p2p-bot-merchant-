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
