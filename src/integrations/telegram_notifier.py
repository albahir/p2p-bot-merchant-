"""Servicio de alertas, cola asíncrona y comandos vía Telegram Bot.
Garantiza el principio constitucional de "Cero Secretos":
- Sanitiza el texto de cualquier mensaje saliente.
- Permite control fail-closed validando remitentes autorizados.
- Implementa comandos /status, /pause, /resume, /report y /ayuda.
- Resiliencia ante fallos: fallback automático a texto plano ante HTTP 400 y reintentos ante 429.
- Soporte para proxy HTTP/SOCKS5 y URL base personalizada para eludir bloqueos de ISP.
- Cola de despacho en segundo plano para envíos no bloqueantes.
- Poller de comandos en tiempo real con getUpdates.
"""

import logging
import queue
import re
import threading
import time
from typing import Any

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
    """Notificador de Telegram con envío seguro, sanitización previa y fallback resiliente."""

    def __init__(
        self,
        bot_token: str,
        default_chat_id: str,
        allowed_user_ids: list[int] | None = None,
        proxy_url: str | None = None,
        api_base_url: str = "https://api.telegram.org",
        use_sandbox: bool = True
    ):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.allowed_user_ids = allowed_user_ids or []
        self.proxy_url = proxy_url
        self.api_base_url = api_base_url.rstrip("/")
        self.base_url = f"{self.api_base_url}/bot{bot_token}"
        self.is_paused = False
        self.use_sandbox = use_sandbox
        self.last_error: str | None = None

        # Configuración del cliente HTTP persistente con soporte para proxy
        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(15.0, connect=8.0),
            "limits": httpx.Limits(max_keepalive_connections=5, keepalive_expiry=30.0)
        }
        if self.proxy_url:
            client_kwargs["proxy"] = self.proxy_url

        self._client = httpx.Client(**client_kwargs)

    def send_alert(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str | None = "Markdown"
    ) -> bool:
        """Envía una alerta con formato seguro, fallback a texto plano ante error 400 y reintentos ante 429."""
        if not self.bot_token:
            logger.warning("TELEGRAM: Bot token no configurado. Mensaje omitido.")
            return False

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.warning("TELEGRAM: Chat ID no configurado.")
            return False

        clean_text = sanitize_message(text)

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "text": clean_text
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        # Intentar hasta 3 veces con intervalos breves si hay problemas en la red
        for attempt in range(3):
            try:
                res = self._client.post(f"{self.base_url}/sendMessage", json=payload)
                if res.status_code == 200:
                    logger.info("TELEGRAM: Notificación enviada con éxito.")
                    self.last_error = None
                    return True

                # Caso 1: Error 400 (Bad Request - comúnmente fallo de parseo Markdown por caracteres especiales)
                if res.status_code == 400 and payload.get("parse_mode"):
                    logger.warning("TELEGRAM: Error 400 en parseo de entidades. Reintentando como texto plano...")
                    payload.pop("parse_mode", None)
                    res_fallback = self._client.post(f"{self.base_url}/sendMessage", json=payload)
                    if res_fallback.status_code == 200:
                        logger.info("TELEGRAM: Notificación entregada con éxito tras fallback a texto plano.")
                        self.last_error = None
                        return True
                    else:
                        err_msg = f"HTTP {res_fallback.status_code}: {res_fallback.text}"
                        logger.error(f"TELEGRAM: Fallback también falló: {err_msg}")
                        self.last_error = err_msg
                        return False

                # Caso 2: Error 429 (Flood control / Rate limit)
                if res.status_code == 429:
                    try:
                        data = res.json()
                        retry_after = int(data.get("parameters", {}).get("retry_after", 1))
                    except (ValueError, TypeError, KeyError):
                        retry_after = 1
                    logger.warning(f"TELEGRAM: Rate limit 429 alcanzado. Esperando {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                # Otros errores HTTP (401, 403, 500, etc.)
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

    def is_user_authorized(self, user_id: int | str | None) -> bool:
        """Verifica si un remitente de comando está en la lista autorizada o es el dueño del chat."""
        if user_id is None:
            return False
        user_str = str(user_id).strip()
        # 1. Si coincide con el chat_id predeterminado (en chats privados 1-a-1, user_id == chat_id)
        if self.default_chat_id and user_str == str(self.default_chat_id).strip():
            return True
        # 2. Si está en la lista explícita de allowed_user_ids
        for allowed in self.allowed_user_ids:
            if str(allowed).strip() == user_str:
                return True
        return False

    def handle_command(self, user_id: int | str | None, command: str) -> str:
        """Procesa comandos /status, /pause, /resume, /report y /ayuda respetando permisos."""
        if not self.is_user_authorized(user_id):
            logger.warning(f"Intento de comando no autorizado por user_id={user_id}")
            return (
                f"⛔ *Acceso denegado*. Usuario no autorizado.\n"
                f"Tu ID de Telegram es: `{user_id}`.\n"
                f"Añádelo a `TELEGRAM_ALLOWED_USER_IDS`."
            )

        cmd = command.strip().lower()
        if cmd == "/status":
            state = "⏸️ PAUSADO" if self.is_paused else "🟢 ACTIVO"
            mode = "🧪 SANDBOX (Simulación Activa)" if self.use_sandbox else "🔴 PRODUCCIÓN (Binance Real)"
            return f"🤖 *Estado del Bot*: {state}\nModo: {mode}\nServicios: OK"
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
        elif cmd in ("/keys", "/claves", "/ai_status"):
            return "🔑 Usa `/keys` o pregúntale al bot '¿cuál es el estado de las claves?' para ver la telemetría en vivo."
        elif cmd in ("/sheets", "/sync_sheets", "/hojas"):
            return self._handle_sheets_sync()
        elif cmd in ("/help", "/ayuda", "/start"):
            return (
                "🤖 *Comandos Disponibles*:\n"
                "- `/status`: Ver estado y modo operativo del bot\n"
                "- `/keys`: Ver estado y cuota del pool de claves de IA\n"
                "- `/sheets`: Sincronizar y obtener enlace de Google Sheets\n"
                "- `/pause`: Pausar operaciones comerciales\n"
                "- `/resume`: Reanudar operaciones comerciales\n"
                "- `/report`: Enlace a reportes fiscales\n"
                "- `/ayuda`: Mostrar este menú de ayuda"
            )
        else:
            return f"❓ Comando no reconocido: {command}. Usa /ayuda para ver los disponibles."

    def _handle_sheets_sync(self) -> str:
        """Sincroniza el histórico fiscal con Google Sheets y retorna el estado con enlace directo."""
        from sqlalchemy.exc import SQLAlchemyError

        from config.settings import Settings
        from src.data.database import SessionLocal
        from src.data.repositories import OrderRepository
        from src.reporting.sheets_exporter import SheetsExporter
        from src.reporting.tax_engine import FIFOCostMethod

        try:
            settings = Settings()
        except (ValueError, KeyError, OSError, RuntimeError):
            return "⚠️ No se pudo cargar la configuración del sistema."

        if not settings.GOOGLE_SHEET_ID:
            return (
                "⚠️ *Google Sheets no está configurado*.\n\n"
                "Para activarlo, define `GOOGLE_SHEET_ID` y las credenciales de servicio en `config/.env` o variables de entorno."
            )

        db = SessionLocal()
        try:
            repo = OrderRepository(db)
            completed_orders = repo.list_completed()
            if not completed_orders:
                return "ℹ️ No hay órdenes completadas para sincronizar en Google Sheets."

            fifo = FIFOCostMethod()
            results = fifo.process_orders(completed_orders)

            exporter = SheetsExporter(
                credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
                credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
            )
            success = exporter.export(settings.GOOGLE_SHEET_ID, results)
            sheet_url = SheetsExporter.get_sheet_url(settings.GOOGLE_SHEET_ID)

            if success:
                total_profit_ves = sum(r.net_profit_fiat for r in results)
                total_profit_usd = sum(r.net_profit_usd for r in results)
                return (
                    f"📊 *Google Sheets Sincronizado Exitosamente*\n\n"
                    f"• Órdenes sincronizadas: `{len(results)}`\n"
                    f"• Ganancia Consolidada: `{total_profit_ves:,.2f} VES` (`${total_profit_usd:,.2f} USD`)\n\n"
                    f"🔗 [Abrir en Google Sheets]({sheet_url})"
                )
            else:
                error_detail = exporter.last_error or "Verifica que la cuenta de servicio tenga permisos de Editor sobre el documento."
                return (
                    f"❌ *Error al sincronizar con Google Sheets*:\n\n"
                    f"⚠️ {error_detail}\n\n"
                    f"🔗 [Ver Hoja]({sheet_url})"
                )
        except (SQLAlchemyError, OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Error ejecutando /sheets: {e}")
            return f"❌ Error interno sincronizando Google Sheets: {e}"
        finally:
            db.close()


class TelegramQueueDispatcher:
    """Cola asíncrona en segundo plano para envío de alertas sin bloquear la interfaz ni el motor."""

    def __init__(self, notifier: TelegramNotifier, rate_limit_delay: float = 0.5):
        self.notifier = notifier
        self.rate_limit_delay = rate_limit_delay
        self._queue: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=1000)
        self._is_running = False
        self._worker_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="TelegramQueueWorker"
        )
        self._worker_thread.start()
        logger.info("TelegramQueueDispatcher iniciado en segundo plano.")

    def stop(self) -> None:
        self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            try:
                self._queue.put_nowait(("", "__STOP__"))
            except queue.Full:
                pass
            self._worker_thread.join(timeout=2.0)
        logger.info("TelegramQueueDispatcher detenido.")

    def queue_alert(self, text: str, chat_id: str | None = None) -> bool:
        """Encola un mensaje para ser enviado en segundo plano de forma no bloqueante."""
        try:
            self._queue.put_nowait((text, chat_id))
            return True
        except queue.Full:
            logger.error("TELEGRAM: Cola de mensajes llena (1000 mensajes). Descartando alerta.")
            return False

    def wait_until_empty(self, timeout: float = 5.0) -> bool:
        """Espera a que todos los mensajes en la cola sean procesados."""
        deadline = time.time() + timeout
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.05)
        return self._queue.empty()

    def _process_queue(self) -> None:
        while self._is_running:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            text, chat_id = item
            if chat_id == "__STOP__":
                self._queue.task_done()
                break

            try:
                self.notifier.send_alert(text, chat_id=chat_id)
            except (httpx.RequestError, ValueError, TypeError, OSError) as e:
                logger.error(f"Error procesando mensaje en cola de Telegram: {e}")
            finally:
                self._queue.task_done()

            if self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)


class TelegramCommandPoller:
    """Escucha activa de comandos y consultas en lenguaje natural vía long-polling (getUpdates)."""

    def __init__(
        self,
        notifier: TelegramNotifier,
        ai_agent: Any = None,
        poll_interval: float = 2.0
    ):
        self.notifier = notifier
        self.ai_agent = ai_agent
        self.poll_interval = poll_interval
        self._last_offset = 0
        self._is_running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="TelegramCommandPoller"
        )
        self._thread.start()
        logger.info("TelegramCommandPoller iniciado en segundo plano.")

    def stop(self) -> None:
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("TelegramCommandPoller detenido.")

    def poll_once(self) -> int:
        """Consulta actualizaciones pendientes y ejecuta comandos o consultas con IA si son de usuarios autorizados."""
        url = f"{self.notifier.base_url}/getUpdates"
        params: dict[str, str | int] = {
            "offset": self._last_offset + 1,
            "timeout": 5
        }
        try:
            res = self.notifier._client.get(url, params=params)
            if res.status_code != 200:
                return 0
            data = res.json()
            if not data.get("ok"):
                return 0
            updates = data.get("result", [])
            processed = 0
            for update in updates:
                update_id = int(update.get("update_id", 0))
                self._last_offset = max(self._last_offset, update_id)

                msg = update.get("message") or update.get("channel_post")
                if not msg:
                    continue

                from_user = msg.get("from", {})
                user_id = from_user.get("id")
                chat_id = str(msg.get("chat", {}).get("id"))
                text = str(msg.get("text", "")).strip()

                if text.startswith("/"):
                    cmd = text.strip().lower()
                    if cmd in ("/keys", "/claves", "/ai_status") and self.ai_agent and hasattr(self.ai_agent, "key_pool"):
                        if not self.notifier.is_user_authorized(user_id):
                            self.notifier.send_alert(
                                f"⛔ *Acceso denegado*. Usuario no autorizado.\n"
                                f"Tu ID de Telegram es: `{user_id}`.\n"
                                f"Añádelo a `TELEGRAM_ALLOWED_USER_IDS`.",
                                chat_id=chat_id
                            )
                        else:
                            summary = self.ai_agent.key_pool.format_status_summary()
                            self.notifier.send_alert(summary, chat_id=chat_id)
                        processed += 1
                        continue

                    response = self.notifier.handle_command(user_id=user_id, command=text)
                    self.notifier.send_alert(response, chat_id=chat_id)
                    processed += 1
                elif text:
                    # Consulta en lenguaje natural
                    if not self.notifier.is_user_authorized(user_id):
                        logger.warning(f"Consulta no autorizada de user_id={user_id}")
                        self.notifier.send_alert(
                            f"⛔ *Acceso denegado*. Usuario no autorizado.\n"
                            f"Tu ID de Telegram es: `{user_id}`.\n"
                            f"Añádelo a `TELEGRAM_ALLOWED_USER_IDS`.",
                            chat_id=chat_id
                        )
                    else:
                        if self.ai_agent:
                            ai_response = self.ai_agent.ask(text)
                            self.notifier.send_alert(ai_response, chat_id=chat_id)
                        else:
                            self.notifier.send_alert(
                                "ℹ️ *Asistente de IA no configurado*.\n"
                                "Configura `AI_API_KEY` en `config/.env` para habilitar preguntas en lenguaje natural, "
                                "o utiliza comandos directos como `/status`, `/report` o `/ayuda`.",
                                chat_id=chat_id
                            )
                    processed += 1
            return processed
        except (httpx.RequestError, ValueError, TypeError, OSError) as e:
            logger.debug(f"Error consultando getUpdates: {e}")
            return 0

    def _run_loop(self) -> None:
        while self._is_running:
            self.poll_once()
            time.sleep(self.poll_interval)
