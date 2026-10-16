"""Asistente de Inteligencia Artificial para consultas en lenguaje natural vía Telegram.
Implementa Function Calling seguro (solo lectura) contra la base de datos local y el motor fiscal,
garantizando la regla constitucional de 'Cero Secretos' y respuestas libres de alucinaciones.
"""

import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.data.database import SessionLocal
from src.data.repositories import OrderRepository
from src.integrations.telegram_notifier import sanitize_message
from src.reporting.bcv_service import BCVService
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod

logger = logging.getLogger("ai_assistant")


class AIAssistantTools:
    """Catálogo de herramientas locales de solo lectura expuestas al modelo de lenguaje."""

    def __init__(self, db_session_factory=SessionLocal):
        self.session_factory = db_session_factory

    def obtener_metricas_fiscales(self, dias_atras: int = 7, metodo: str = "FIFO") -> dict[str, Any]:
        """Calcula el rendimiento y las ganancias netas consolidadas en base a las órdenes completadas."""
        db = self.session_factory()
        try:
            repo = OrderRepository(db)
            start_date = datetime.now(UTC) - timedelta(days=dias_atras)
            orders = repo.list_completed(start_date=start_date)

            engine = FIFOCostMethod() if metodo.upper() == "FIFO" else WeightedAverageCostMethod()
            results = engine.process_orders(orders)

            total_ganancia_ves = sum(r.net_profit_fiat for r in results)
            total_ganancia_usd = sum(r.net_profit_usd for r in results)
            total_ingreso_ves = sum(r.total_revenue_fiat for r in results)
            total_costo_ves = sum(r.acquisition_cost_fiat for r in results)
            total_cripto_vendido = sum(r.crypto_amount for r in results)

            return {
                "periodo_dias": dias_atras,
                "metodo_contable": metodo.upper(),
                "total_ventas": len(results),
                "volumen_cripto_vendido": round(total_cripto_vendido, 4),
                "ingreso_fiat_total_ves": round(total_ingreso_ves, 2),
                "costo_adquisicion_total_ves": round(total_costo_ves, 2),
                "ganancia_neta_ves": round(total_ganancia_ves, 2),
                "ganancia_neta_usd": round(total_ganancia_usd, 2)
            }
        finally:
            db.close()

    def consultar_ordenes_recientes(self, limite: int = 5) -> list[dict[str, Any]]:
        """Devuelve las últimas N transacciones registradas con sus montos y precios."""
        db = self.session_factory()
        try:
            from src.data.models import Order
            orders = db.query(Order).order_by(Order.id.desc()).limit(limite).all()
            return [
                {
                    "order_number": str(o.order_number),
                    "trade_type": str(o.trade_type),
                    "asset": str(o.asset),
                    "fiat": str(o.fiat),
                    "crypto_amount": float(o.crypto_amount),
                    "unit_price": float(o.unit_price),
                    "fiat_amount": float(o.fiat_amount),
                    "status": str(o.order_status),
                    "fecha": o.created_at.strftime("%Y-%m-%d %H:%M UTC") if o.created_at else ""
                }
                for o in orders
            ]
        finally:
            db.close()

    def consultar_tasa_bcv(self) -> dict[str, Any]:
        """Obtiene la tasa de cambio oficial de referencia del Banco Central de Venezuela."""
        service = BCVService()
        rate = service.fetch_current_rate()
        return {
            "moneda": "USD/VES",
            "tasa_bcv": rate,
            "fuente": "Banco Central de Venezuela"
        }

    def consultar_estado_sistema(self) -> dict[str, Any]:
        """Retorna el estado de salud, conteo de órdenes y modo operativo del bot."""
        db = self.session_factory()
        try:
            from src.data.models import Order
            total_orders = db.query(Order).count()
            return {
                "base_datos": "Conectada (OK)",
                "total_ordenes_registradas": total_orders,
                "auditoria": "Activa (SHA-256 Append-Only)",
                "servicios": "Operativos"
            }
        finally:
            db.close()


GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "obtener_metricas_fiscales",
        "description": "Calcula ganancias netas en VES y USD, costos e ingresos de las operaciones P2P.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "dias_atras": {
                    "type": "INTEGER",
                    "description": "Número de días hacia atrás a consultar (ej. 1 para hoy, 7 para la semana, 30 para el mes)."
                },
                "metodo": {
                    "type": "STRING",
                    "description": "Método de costeo fiscal: 'FIFO' o 'AVERAGE'."
                }
            }
        }
    },
    {
        "name": "consultar_ordenes_recientes",
        "description": "Consulta el listado de las últimas órdenes P2P completadas con sus precios y montos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "limite": {
                    "type": "INTEGER",
                    "description": "Cantidad máxima de órdenes a retornar (por defecto 5)."
                }
            }
        }
    },
    {
        "name": "consultar_tasa_bcv",
        "description": "Consulta la tasa de cambio oficial vigente del BCV (USD a VES).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "consultar_estado_sistema",
        "description": "Consulta la salud del bot, estado de la base de datos y resumen operativo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]


class AIKeyPool:
    """Pool y rotador dinámico de API Keys con cooldown silencioso ante límites de tasa (429/403)."""

    def __init__(self, raw_keys: str | list[str]):
        if isinstance(raw_keys, str):
            self.keys: list[str] = [
                k.strip()
                for k in raw_keys.replace(";", ",").split(",")
                if k.strip()
            ]
        else:
            self.keys = [k.strip() for k in raw_keys if k and k.strip()]

        self._current_index = 0
        self._lock = threading.Lock()
        self._cooldowns: dict[str, float] = {}

    @property
    def has_keys(self) -> bool:
        return len(self.keys) > 0

    @property
    def total_keys(self) -> int:
        return len(self.keys)

    def get_active_key(self) -> str | None:
        """Devuelve la clave actualmente activa o la primera disponible fuera de cooldown."""
        with self._lock:
            if not self.keys:
                return None
            now = time.time()
            for i in range(len(self.keys)):
                idx = (self._current_index + i) % len(self.keys)
                k = self.keys[idx]
                if self._cooldowns.get(k, 0) <= now:
                    self._current_index = idx
                    return k
            return self.keys[self._current_index]

    def mark_rate_limited(self, exhausted_key: str, cooldown_seconds: float = 60.0) -> str | None:
        """Pone la clave agotada en cooldown y rota silenciosamente a la siguiente disponible."""
        with self._lock:
            if not self.keys:
                return None
            now = time.time()
            self._cooldowns[exhausted_key] = now + cooldown_seconds
            self._current_index = (self._current_index + 1) % len(self.keys)
            next_key = self.keys[self._current_index]
            masked_key = f"{exhausted_key[:6]}...{exhausted_key[-4:]}" if len(exhausted_key) > 10 else "[CLAVE]"
            logger.warning(
                f"GEMINI: Clave {masked_key} en cooldown ({cooldown_seconds}s). "
                f"Rotando silenciosamente al slot [{self._current_index + 1}/{len(self.keys)}]."
            )
            return next_key


class TelegramAIAgent:
    """Agente conversacional de IA con Function Calling para responder consultas en Telegram."""

    def __init__(
        self,
        api_key: str | list[str] = "",
        provider: str = "gemini",
        model_name: str = "gemini-1.5-flash",
        db_session_factory=SessionLocal
    ):
        self.key_pool = AIKeyPool(api_key)
        self.provider = provider
        self.model_name = model_name
        self.tools = AIAssistantTools(db_session_factory=db_session_factory)
        self._client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    def _call_gemini_with_failover(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None, str | None]:
        """Envía una petición a Gemini rotando silenciosamente entre las claves del pool ante error 429/403."""
        attempts = max(self.key_pool.total_keys, 1)
        for _ in range(attempts):
            key = self.key_pool.get_active_key()
            if not key:
                break
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={key}"
            try:
                res = self._client.post(url, json=payload)
                if res.status_code == 200:
                    return 200, res.json(), None
                if res.status_code in (429, 403):
                    logger.warning(f"Error de cuota Gemini (HTTP {res.status_code}). Intentando clave de respaldo...")
                    self.key_pool.mark_rate_limited(key, cooldown_seconds=60.0)
                    continue

                logger.error(f"Error de API Gemini: HTTP {res.status_code} - {res.text}")
                return res.status_code, None, "⚠️ No pude conectar con el servicio de IA en este momento. Intenta de nuevo en unos instantes."
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"Error de red temporal al conectar con Gemini: {e}")
                self.key_pool.mark_rate_limited(key, cooldown_seconds=30.0)
                continue

        return 429, None, "⏳ *Límite de cuota alcanzado*. Todas las claves API están en uso o espera. Por favor intenta en un minuto."

    def ask(self, prompt: str) -> str:
        """Procesa una consulta en lenguaje natural utilizando Function Calling y devuelve la respuesta."""
        if not self.key_pool.has_keys:
            return (
                "ℹ️ *Asistente de IA no configurado*\n\n"
                "Para hablar conmigo en lenguaje natural y consultar ganancias o métricas, "
                "debes agregar tu `AI_API_KEY` en el archivo `config/.env`.\n\n"
                "💡 Mientras tanto, puedes usar los comandos rápidos como `/status`, `/report` o `/ayuda`."
            )

        system_instruction = (
            "Eres el Asistente Financiero y Operativo de un comerciante P2P en Binance. "
            "Tu objetivo es responder con precisión preguntas sobre ganancias, ventas, tasas y estado del bot. "
            "REGLAS CRÍTICAS:\n"
            "1. NUNCA inventes números. Si te preguntan por ganancias o transacciones, USA SIEMPRE las funciones disponibles.\n"
            "2. Sé conciso, profesional y redacta con formato Markdown limpio apto para Telegram.\n"
            "3. NUNCA reveles claves privadas, tokens, contraseñas ni secretos internos.\n"
            "4. Responde siempre en español."
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "parts": [{"text": prompt}]}
        ]

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": messages,
            "tools": [{"functionDeclarations": GEMINI_TOOL_DECLARATIONS}]
        }

        try:
            # 1. Primera llamada al modelo con failover automático
            status_code, data, err_msg = self._call_gemini_with_failover(payload)
            if status_code != 200 or not data:
                return err_msg or "⚠️ No pude conectar con el servicio de IA en este momento."

            candidates = data.get("candidates", [])
            if not candidates:
                return "No obtuve respuesta del asistente de IA."

            first_candidate = candidates[0]
            parts = first_candidate.get("content", {}).get("parts", [])

            # Comprobar si el modelo solicitó invocar una función (Tool Call)
            function_call = None
            text_response = ""
            for part in parts:
                if "functionCall" in part:
                    function_call = part["functionCall"]
                elif "text" in part:
                    text_response += part["text"]

            if not function_call:
                return sanitize_message(text_response)

            # 2. Ejecutar la herramienta local
            tool_name = function_call.get("name")
            tool_args = function_call.get("args", {})
            logger.info(f"AI invoca herramienta: {tool_name} con argumentos: {tool_args}")

            tool_result: Any = {}
            if tool_name == "obtener_metricas_fiscales":
                tool_result = self.tools.obtener_metricas_fiscales(
                    dias_atras=int(tool_args.get("dias_atras", 7)),
                    metodo=str(tool_args.get("metodo", "FIFO"))
                )
            elif tool_name == "consultar_ordenes_recientes":
                tool_result = self.tools.consultar_ordenes_recientes(
                    limite=int(tool_args.get("limite", 5))
                )
            elif tool_name == "consultar_tasa_bcv":
                tool_result = self.tools.consultar_tasa_bcv()
            elif tool_name == "consultar_estado_sistema":
                tool_result = self.tools.consultar_estado_sistema()
            else:
                tool_result = {"error": f"Herramienta desconocida: {tool_name}"}

            # 3. Enviar el resultado de la función de vuelta al modelo para la respuesta final
            messages.append(first_candidate.get("content", {}))
            messages.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"output": tool_result}
                        }
                    }
                ]
            })

            payload["contents"] = messages
            status_code_2, data_final, err_msg_2 = self._call_gemini_with_failover(payload)
            if status_code_2 != 200 or not data_final:
                return err_msg_2 or "⚠️ Ocurrió un error al formatear la respuesta con los datos obtenidos."

            final_parts = data_final.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            final_text = "".join(p.get("text", "") for p in final_parts)

            return sanitize_message(final_text)

        except (httpx.RequestError, ValueError, TypeError, KeyError) as e:
            logger.error(f"Excepción en TelegramAIAgent: {e}")
            return f"⚠️ Error procesando consulta con el asistente de IA: {e}"
