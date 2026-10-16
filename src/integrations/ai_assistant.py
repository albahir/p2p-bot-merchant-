"""Asistente de Inteligencia Artificial para consultas en lenguaje natural vía Telegram.
Implementa Function Calling seguro (solo lectura) contra la base de datos local y el motor fiscal,
garantizando la regla constitucional de 'Cero Secretos' y respuestas libres de alucinaciones.
"""

import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx

from src.data.database import SessionLocal
from src.data.repositories import OrderRepository
from src.integrations.telegram_notifier import sanitize_message
from src.reporting.bcv_service import BCVService
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod

logger = logging.getLogger("ai_assistant")


class AIAssistantTools:
    """Catálogo de herramientas locales de solo lectura expuestas al modelo de lenguaje."""

    def __init__(self, db_session_factory=SessionLocal, key_pool: Any = None):
        self.session_factory = db_session_factory
        self.key_pool = key_pool

    def consultar_estado_claves_ia(self) -> dict[str, Any]:
        """Consulta el estado del pool de claves API de Gemini, claves activas y cooldowns."""
        if self.key_pool and hasattr(self.key_pool, "get_pool_status"):
            return cast(dict[str, Any], self.key_pool.get_pool_status())
        return {"info": "Información de pool de claves no disponible"}

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
    },
    {
        "name": "consultar_estado_claves_ia",
        "description": "Consulta la telemetría en vivo del pool de claves de IA (Gemini): cuál está activa, peticiones atendidas, cuáles están en enfriamiento y tiempo restante para restablecerse.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]


class AIKeyPool:
    """Pool y balanceador Round-Robin proactivo de API Keys de IA con failover silencioso,
    enfriamiento automático ante saturación (429/503/red) y telemetría en tiempo real.
    """

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
        self._call_counts: dict[str, int] = {k: 0 for k in self.keys}
        self._rate_limit_counts: dict[str, int] = {k: 0 for k in self.keys}
        self._restored_times: dict[str, float] = {}

    @property
    def has_keys(self) -> bool:
        return len(self.keys) > 0

    @property
    def total_keys(self) -> int:
        return len(self.keys)

    @staticmethod
    def mask_key(k: str) -> str:
        """Enmascara una clave para no revelar secretos en logs ni en Telegram."""
        if len(k) > 10:
            return f"{k[:6]}...{k[-4:]}"
        return "[CLAVE]"

    def record_success(self, key: str) -> None:
        """Registra una llamada exitosa para una clave."""
        with self._lock:
            self._call_counts[key] = self._call_counts.get(key, 0) + 1

    def get_next_key(self) -> str | None:
        """Devuelve la siguiente clave disponible usando Round-Robin proactivo,
        distribuyendo la carga equitativamente y saltando aquellas en enfriamiento.
        """
        with self._lock:
            if not self.keys:
                return None
            now = time.time()
            for i in range(len(self.keys)):
                idx = (self._current_index + i) % len(self.keys)
                k = self.keys[idx]
                cd_until = self._cooldowns.get(k, 0)
                if cd_until <= now:
                    if cd_until > 0 and self._restored_times.get(k, 0) < cd_until:
                        self._restored_times[k] = now
                    # Avanzar el puntero para la próxima petición (Round-Robin proactivo)
                    self._current_index = (idx + 1) % len(self.keys)
                    return k

            # Si todas las claves están en enfriamiento, retornar la que expire primero
            best_idx = min(range(len(self.keys)), key=lambda i: self._cooldowns.get(self.keys[i], 0))
            self._current_index = (best_idx + 1) % len(self.keys)
            return self.keys[best_idx]

    def get_active_key(self) -> str | None:
        """Obtiene la clave activa delegando en get_next_key() para asegurar rotación continua."""
        return self.get_next_key()

    def mark_rate_limited(self, exhausted_key: str, cooldown_seconds: float = 60.0) -> str | None:
        """Pone la clave agotada o saturada en cooldown y rota silenciosamente a la siguiente disponible."""
        with self._lock:
            if not self.keys:
                return None
            now = time.time()
            self._cooldowns[exhausted_key] = now + cooldown_seconds
            self._rate_limit_counts[exhausted_key] = self._rate_limit_counts.get(exhausted_key, 0) + 1

            if self.keys and self.keys[self._current_index % len(self.keys)] == exhausted_key:
                self._current_index = (self._current_index + 1) % len(self.keys)

            next_key = self.keys[self._current_index % len(self.keys)]
            masked_key = self.mask_key(exhausted_key)
            logger.warning(
                f"GEMINI: Clave {masked_key} en cooldown ({cooldown_seconds}s). "
                f"Slot actual [{((self._current_index) % len(self.keys)) + 1}/{len(self.keys)}]."
            )
            return next_key

    def get_pool_status(self) -> dict[str, Any]:
        """Devuelve telemetría completa de cada clave del pool en tiempo real."""
        with self._lock:
            now = time.time()
            current_active_idx = self._current_index % len(self.keys) if self.keys else 0
            active_key = self.keys[current_active_idx] if self.keys else None
            keys_info: list[dict[str, Any]] = []

            for i, k in enumerate(self.keys):
                masked = self.mask_key(k)
                cd_until = self._cooldowns.get(k, 0)
                is_in_cooldown = cd_until > now
                remaining_cd = round(cd_until - now, 1) if is_in_cooldown else 0.0

                if is_in_cooldown:
                    estado = f"⏳ ENFRIAMIENTO (restan {int(remaining_cd)}s)"
                elif k == active_key:
                    estado = "🟢 ACTIVA"
                else:
                    estado = "⚪ DISPONIBLE (En espera)"

                restored_str = ""
                if self._restored_times.get(k):
                    dt = datetime.fromtimestamp(self._restored_times[k], UTC)
                    restored_str = dt.strftime("%H:%M:%S UTC")

                keys_info.append({
                    "slot": i + 1,
                    "clave": masked,
                    "estado": estado,
                    "peticiones_completadas": self._call_counts.get(k, 0),
                    "veces_saturada": self._rate_limit_counts.get(k, 0),
                    "segundos_restantes_cooldown": int(remaining_cd),
                    "ultima_reactivacion": restored_str
                })

            return {
                "total_claves": len(self.keys),
                "indice_activo": current_active_idx + 1,
                "claves": keys_info
            }

    def format_status_summary(self) -> str:
        """Genera un reporte en texto/Markdown apto para Telegram."""
        data = self.get_pool_status()
        if not data["claves"]:
            return "⚠️ No hay claves API configuradas en el pool."

        lines = ["🔑 *Telemetría del Pool de Claves de IA (Gemini)*:\n"]
        for c in data["claves"]:
            lines.append(
                f"• *Clave #{c['slot']}* (`{c['clave']}`): {c['estado']}\n"
                f"   - Peticiones atendidas: *{c['peticiones_completadas']}*\n"
                f"   - Veces saturada: *{c['veces_saturada']}*"
            )
            if c["segundos_restantes_cooldown"] > 0:
                lines.append(f"   - Restablece en: *{c['segundos_restantes_cooldown']}s*")
            if c["ultima_reactivacion"]:
                lines.append(f"   - Última reactivación: `{c['ultima_reactivacion']}`")
        return "\n".join(lines)


class TelegramAIAgent:
    """Agente conversacional de IA con Function Calling para responder consultas en Telegram."""

    def __init__(
        self,
        api_key: str | list[str] = "",
        provider: str = "gemini",
        model_name: str = "gemini-flash-lite-latest",
        db_session_factory=SessionLocal
    ):
        self.key_pool = AIKeyPool(api_key)
        self.provider = provider
        self.model_name = model_name
        self.tools = AIAssistantTools(db_session_factory=db_session_factory, key_pool=self.key_pool)
        self._client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    def _call_gemini_with_failover(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None, str | None]:
        """Envía una petición a Gemini rotando proactivamente con Round-Robin entre las claves del pool
        y realizando failover silencioso ante 429, 503, 500 o fallos de red hacia claves y modelos de respaldo."""
        models_to_try = [self.model_name]
        for fallback in ("gemini-flash-lite-latest", "gemini-3.5-flash-lite"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        attempts = max(self.key_pool.total_keys, 1)
        for model in models_to_try:
            for _ in range(attempts):
                key = self.key_pool.get_next_key()
                if not key:
                    break
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    res = self._client.post(url, json=payload)
                    if res.status_code == 200:
                        self.key_pool.record_success(key)
                        return 200, res.json(), None

                    # Cuota agotada o permisos limitados
                    if res.status_code in (429, 403):
                        logger.warning(
                            f"GEMINI: Cuota alcanzada (HTTP {res.status_code}) en {self.key_pool.mask_key(key)}. "
                            "Rotando silenciosamente a clave de respaldo..."
                        )
                        self.key_pool.mark_rate_limited(key, cooldown_seconds=60.0)
                        continue

                    # Sobrecarga temporal de servidores de Google (503) o error interno de servidor (500, 502, 504)
                    if res.status_code in (500, 502, 503, 504):
                        logger.warning(
                            f"GEMINI: Servidor sobrecargado (HTTP {res.status_code}) en {self.key_pool.mask_key(key)}. "
                            "Poniendo en enfriamiento breve y rotando a clave de respaldo..."
                        )
                        self.key_pool.mark_rate_limited(key, cooldown_seconds=30.0)
                        continue

                    # Clave inválida o argumento erróneo
                    if res.status_code == 400:
                        logger.warning(
                            f"GEMINI: Error 400 en {self.key_pool.mask_key(key)} ({res.text[:100]}). "
                            "Poniendo en enfriamiento y probando respaldo..."
                        )
                        self.key_pool.mark_rate_limited(key, cooldown_seconds=300.0)
                        continue

                    # Modelo no disponible o deprecated (404) -> probar siguiente modelo
                    if res.status_code == 404:
                        logger.warning(f"Modelo {model} no disponible (HTTP 404). Probando siguiente modelo...")
                        break

                    logger.error(f"Error de API Gemini: HTTP {res.status_code} - {res.text}")
                    return res.status_code, None, f"⚠️ Error del servicio de IA (HTTP {res.status_code}). Intenta de nuevo en unos instantes."
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    logger.warning(f"Error de red temporal al conectar con Gemini: {e}")
                    self.key_pool.mark_rate_limited(key, cooldown_seconds=30.0)
                    continue

        return 429, None, "⏳ *Límite de cuota alcanzado o servicio temporalmente saturado*. Por favor intenta en un minuto."

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
            elif tool_name == "consultar_estado_claves_ia":
                tool_result = self.tools.consultar_estado_claves_ia()
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
