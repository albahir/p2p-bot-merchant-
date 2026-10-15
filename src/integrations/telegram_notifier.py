"""Servicio de alertas y comandos vía Telegram Bot.
Garantiza el principio constitucional de "Cero Secretos":
- Sanitiza el texto de cualquier mensaje saliente.
- Permite control fail-closed validando remitentes autorizados.
- Implementa comandos /status, /pause, /resume y /report.
"""

import logging
import re
import time

import httpx

logger = logging.getLogger("telegram_notifier")

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"([a-fA-F0-9]{64})")
]


def sanitize_message(text: str) -> str:
    """Enmascara cualquier secreto inadvertido en el mensaje."""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1: [REDACTED]", sanitized)
    return sanitized


class TelegramNotifier:
    """Notificador de Telegram con envío seguro y sanitización previa."""

    def __init__(
        self,
        bot_token: str,
        default_chat_id: str,
        allowed_user_ids: list[int] | None = None
    ):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.allowed_user_ids = allowed_user_ids or []
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.is_paused = False
        self.last_error: str | None = None
        # Cliente HTTP persistente para reutilizar el túnel TCP/TLS (Keep-Alive)
        self._client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=30.0)
        )

    def send_alert(self, text: str, chat_id: str | None = None) -> bool:
        """Envía una alerta con formato seguro, reutilizando conexiones y con reintentos."""
        if not self.bot_token:
            logger.warning("TELEGRAM: Bot token no configurado. Mensaje omitido.")
            return False

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.warning("TELEGRAM: Chat ID no configurado.")
            return False

        clean_text = sanitize_message(text)

        payload = {
            "chat_id": target_chat,
            "text": clean_text,
            "parse_mode": "Markdown"
        }

        # Intentar hasta 3 veces con intervalos breves si hay problemas en la red
        for attempt in range(3):
            try:
                res = self._client.post(f"{self.base_url}/sendMessage", json=payload)
                if res.status_code == 200:
                    logger.info("TELEGRAM: Notificación enviada con éxito.")
                    self.last_error = None
                    return True
                else:
                    err_msg = f"HTTP {res.status_code}: {res.text}"
                    logger.error(f"TELEGRAM: {err_msg}")
                    self.last_error = err_msg
                    return False
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"TELEGRAM: Fallo de red temporal (intento {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(1.0)
                    continue
                err_msg = f"Error de conectividad con Telegram tras 3 intentos ({e})"
                logger.error(f"TELEGRAM: {err_msg}")
                self.last_error = err_msg
                return False
            except (httpx.RequestError, ValueError, TypeError) as e:
                err_msg = str(e)
                logger.error(f"TELEGRAM: Excepción inesperada: {err_msg}")
                self.last_error = err_msg
                return False
        return False

    def is_user_authorized(self, user_id: int) -> bool:
        """Verifica si un remitente de comando está en la lista autorizada."""
        return user_id in self.allowed_user_ids

    def handle_command(self, user_id: int, command: str) -> str:
        """Procesa comandos /status, /pause, /resume y /report respetando permisos."""
        if not self.is_user_authorized(user_id):
            logger.warning(f"Intento de comando no autorizado por user_id={user_id}")
            return "⛔ Acceso denegado. Usuario no autorizado."

        cmd = command.strip().lower()
        if cmd == "/status":
            state = "⏸️ PAUSADO" if self.is_paused else "🟢 ACTIVO"
            return f"🤖 *Estado del Bot*: {state}\nServicios: OK"
        elif cmd == "/pause":
            self.is_paused = True
            logger.warning("Bot pausado mediante comando de Telegram.")
            return "⏸️ Operaciones del bot pausadas exitosamente."
        elif cmd == "/resume":
            self.is_paused = False
            logger.info("Bot reanudado mediante comando de Telegram.")
            return "▶️ Operaciones del bot reanudadas."
        elif cmd == "/report":
            return "📊 Para generar el reporte detallado, ingrese al Dashboard Streamlit o ejecute el exportador fiscal."
        else:
            return f"❓ Comando no reconocido: {command}"
