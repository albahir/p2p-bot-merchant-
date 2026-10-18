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
import os
import queue
import re
import threading
import time
from datetime import UTC, datetime
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

    def get_quick_actions_markup(self) -> dict[str, Any]:
        """Genera un teclado inline interactivo con las acciones principales del bot."""
        return {
            "inline_keyboard": [
                [
                    {"text": "📈 Spreads P2P", "callback_data": "/spread"},
                    {"text": "🏛️ Tasa BCV", "callback_data": "/bcv"},
                ],
                [
                    {"text": "📊 Estado Bot", "callback_data": "/status"},
                    {"text": "📑 Cierre Fiscal", "callback_data": "/cierre"},
                ],
                [
                    {"text": "⚖️ Conciliación", "callback_data": "/conciliacion"},
                    {"text": "🔄 Sincronizar Sheets", "callback_data": "/sheets"},
                ],
                [
                    {"text": "⏸️ Pausar", "callback_data": "/pause"},
                    {"text": "▶️ Reanudar", "callback_data": "/resume"},
                ],
            ]
        }

    def get_persistent_menu_markup(self) -> dict[str, Any]:
        """Genera un teclado persistente de acceso rápido en la app móvil de Telegram."""
        return {
            "keyboard": [
                [{"text": "📈 Spreads P2P"}, {"text": "🏛️ Tasa BCV"}],
                [{"text": "📊 Estado Bot"}, {"text": "📑 Cierre Mes"}],
                [{"text": "⚖️ Conciliación"}, {"text": "🔄 Sync Sheets"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> bool:
        """Confirma la pulsación de un botón interactivo (InlineKeyboardButton)."""
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            res = self._client.post(f"{self.base_url}/answerCallbackQuery", json=payload)
            return res.status_code == 200
        except (httpx.RequestError, OSError):
            return False

    def set_bot_commands(self) -> bool:
        """Registra la lista oficial de comandos en Telegram para el menú nativo."""
        commands = [
            {"command": "spread", "description": "📈 Spreads por banco y arbitraje cruzado"},
            {"command": "bcv", "description": "🏛️ Tasa oficial BCV y brecha cambiaria"},
            {"command": "status", "description": "📊 Estado del bot y modo operativo"},
            {"command": "cierre", "description": "📑 Cierre fiscal mensual en Excel"},
            {"command": "conciliacion", "description": "⚖️ Reconstrucción 6 piezas y balance"},
            {"command": "sheets", "description": "🔄 Sincronizar con Google Sheets"},
            {"command": "cedula", "description": "👤 Consultar titularidad por cédula"},
            {"command": "pause", "description": "⏸️ Pausar operaciones"},
            {"command": "resume", "description": "▶️ Reanudar operaciones"},
            {"command": "ayuda", "description": "❓ Menú de comandos y botones"},
        ]
        try:
            res = self._client.post(f"{self.base_url}/setMyCommands", json={"commands": commands})
            return res.status_code == 200
        except (httpx.RequestError, OSError):
            return False

    def send_alert(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str | None = "Markdown",
        reply_markup: dict[str, Any] | None = None,
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
        if reply_markup:
            payload["reply_markup"] = reply_markup

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

    def send_document(
        self,
        file_path: str,
        caption: str | None = None,
        chat_id: str | None = None,
        parse_mode: str | None = "Markdown",
    ) -> bool:
        """Envía un archivo binario (ej. .xlsx) al chat de Telegram con sanitización de caption."""
        if self.is_paused:
            logger.info("TELEGRAM: Notificador pausado, omitiendo envío de documento.")
            return False

        if not os.path.exists(file_path):
            self.last_error = f"Archivo no encontrado: {file_path}"
            logger.error(f"TELEGRAM: {self.last_error}")
            return False

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            self.last_error = "No hay un chat_id configurado para enviar el documento."
            logger.warning(f"TELEGRAM: {self.last_error}")
            return False

        sanitized_caption = sanitize_message(caption) if caption else ""
        data: dict[str, Any] = {"chat_id": str(target_chat)}
        if sanitized_caption:
            data["caption"] = sanitized_caption
        if parse_mode:
            data["parse_mode"] = parse_mode

        filename = os.path.basename(file_path)

        for attempt in range(3):
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                files = {"document": (filename, file_bytes, "application/octet-stream")}
                res = self._client.post(f"{self.base_url}/sendDocument", data=data, files=files)
                if res.status_code == 200:
                    logger.info(f"TELEGRAM: Documento '{filename}' enviado con éxito.")
                    self.last_error = None
                    return True

                if res.status_code == 400 and data.get("parse_mode"):
                    logger.warning("TELEGRAM: Error 400 en parseo de entidades de caption. Reintentando sin parse_mode...")
                    data.pop("parse_mode", None)
                    res_fallback = self._client.post(f"{self.base_url}/sendDocument", data=data, files=files)
                    if res_fallback.status_code == 200:
                        logger.info(f"TELEGRAM: Documento '{filename}' entregado con éxito tras fallback.")
                        self.last_error = None
                        return True
                    else:
                        err_msg = f"HTTP {res_fallback.status_code}: {res_fallback.text}"
                        self.last_error = err_msg
                        return False

                if res.status_code == 429:
                    try:
                        resp_data = res.json()
                        retry_after = int(resp_data.get("parameters", {}).get("retry_after", 1))
                    except (ValueError, TypeError, KeyError):
                        retry_after = 1
                    time.sleep(retry_after)
                    continue

                err_msg = f"HTTP {res.status_code}: {res.text}"
                logger.error(f"TELEGRAM: Error enviando documento: {err_msg}")
                self.last_error = err_msg
                return False

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"TELEGRAM: Fallo de red temporal al enviar documento (intento {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(1.0)
                    continue
                err_msg = f"Error de conectividad al enviar documento tras 3 intentos ({e})"
                logger.error(f"TELEGRAM: {err_msg}")
                self.last_error = err_msg
                return False
            except (OSError, httpx.RequestError, ValueError, TypeError) as e:
                err_msg = str(e)
                logger.error(f"TELEGRAM: Excepción inesperada enviando documento: {err_msg}")
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

        # Mapeo de botones de texto (Persistent Reply Keyboard)
        text_menu_map = {
            "📈 spreads p2p": "/spread",
            "📈 spreads & arbitraje": "/spread",
            "🏛️ tasa bcv": "/bcv",
            "📊 estado bot": "/status",
            "📊 estado del sistema": "/status",
            "📑 cierre mes": "/cierre",
            "📑 cierre fiscal": "/cierre",
            "⚖️ conciliación": "/conciliacion",
            "🔄 sync sheets": "/sheets",
            "🔄 sincronizar sheets": "/sheets",
            "❓ ayuda": "/ayuda",
        }
        clean_text_lower = command.strip().lower()
        if clean_text_lower in text_menu_map:
            clean_cmd_str = text_menu_map[clean_text_lower]
        else:
            clean_cmd_str = command.strip()

        cmd = clean_cmd_str.split()[0].lower() if clean_cmd_str else ""
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
        elif cmd in ("/bcv", "/tasa", "/dolar_bcv"):
            return self._handle_bcv_query()
        elif cmd in ("/sheets", "/sync_sheets", "/hojas"):
            return self._handle_sheets_sync()
        elif cmd in ("/sheets_compliance", "/compliance_sheets"):
            return self._handle_compliance_sheets_sync()
        elif cmd in ("/cierre", "/cierre_mensual"):
            return self._handle_monthly_close(clean_cmd_str)
        elif cmd in ("/cedula", "/identidad", "/consultar_cedula"):
            return self._handle_cedula_lookup(clean_cmd_str)
        elif cmd in ("/guardar_cedula", "/registrar_cedula", "/agregar_cedula"):
            return self._handle_save_cedula(clean_cmd_str)
        elif cmd in ("/conciliacion", "/reconciliacion", "/reconstruccion"):
            return self._handle_fiscal_reconciliation(clean_cmd_str)
        elif cmd in ("/spread", "/arbitraje", "/margen"):
            return self._handle_spread_monitor(clean_cmd_str)
        elif cmd in ("/help", "/ayuda", "/start", "/menu"):
            return (
                "🤖 *P2P Merchant Bot — Menú de Comandos y Operaciones*:\n\n"
                "• `/spread`: Monitor de spreads por banco y arbitraje cruzado\n"
                "• `/bcv`: Consultar cotización oficial BCV y brecha cambiaria\n"
                "• `/status`: Ver estado y modo operativo del bot\n"
                "• `/cierre`: Generar y enviar cierre fiscal mensual en Excel\n"
                "• `/conciliacion`: Resumen de 6 piezas fiscales y balance\n"
                "• `/sheets`: Sincronizar y obtener enlace de Google Sheets\n"
                "• `/sheets_compliance`: Expediente de Compliance en Google Sheets\n"
                "• `/cedula V12345678`: Consultar titular oficial por cédula\n"
                "• `/guardar_cedula V12345678 NOMBRE`: Registrar identidad local\n"
                "• `/keys`: Ver estado y cuota del pool de claves de IA\n"
                "• `/pause` / `/resume`: Control de actividad del bot\n\n"
                "💡 *Tip*: Puedes tocar directamente los botones interactivos abajo para ejecutar acciones sin escribir."
            )
        else:
            return f"❓ Comando no reconocido: {command}. Usa /ayuda para ver los disponibles."

    def _handle_sheets_sync(self) -> str:
        """Sincroniza el histórico fiscal con Google Sheets y retorna el estado con enlace directo."""
        import os

        from sqlalchemy.exc import SQLAlchemyError

        from config.settings import Settings
        from src.data.database import SessionLocal
        from src.data.repositories import OrderRepository
        from src.reporting.sheets_exporter import SheetsExporter
        from src.reporting.tax_engine import FIFOCostMethod

        sheet_id: str | None = None
        creds_json: str | None = None
        creds_file: str = "config/google_credentials.json"

        try:
            settings = Settings()
            sheet_id = settings.GOOGLE_SHEET_ID
            creds_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
            creds_file = settings.GOOGLE_CREDENTIALS_FILE
        except (ValueError, KeyError, OSError, RuntimeError):
            sheet_id = os.getenv("GOOGLE_SHEET_ID")
            creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/google_credentials.json")

        if not sheet_id:
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
                credentials_path=creds_file,
                credentials_json=creds_json,
            )
            success = exporter.export(sheet_id, results)
            sheet_url = SheetsExporter.get_sheet_url(sheet_id)

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

    def _handle_monthly_close(self, command: str) -> str:
        """Procesa el comando /cierre [YYYY-MM] y despacha el archivo Excel a Telegram."""
        from src.data.database import SessionLocal
        from src.reporting.monthly_closer import MonthlyFiscalCloser

        parts = command.strip().split()
        now = datetime.now(UTC)
        year = now.year
        month = now.month

        # Por defecto el cierre es del mes anterior, o del mes especificado en el comando
        if len(parts) > 1:
            arg = parts[1]
            try:
                if "-" in arg:
                    y_str, m_str = arg.split("-")
                    year = int(y_str)
                    month = int(m_str)
                else:
                    month = int(arg)
            except (ValueError, TypeError):
                return "⚠️ Formato inválido. Usa `/cierre` (mes anterior) o `/cierre YYYY-MM` (ej. `/cierre 2026-09`)."
        else:
            # Mes anterior por defecto
            if month == 1:
                year -= 1
                month = 12
            else:
                month -= 1

        closer = MonthlyFiscalCloser(session_factory=SessionLocal, notifier=self)
        file_path, metrics = closer.execute_close(year=year, month=month, send_telegram=True)

        if not file_path:
            msg = metrics.get("message") or metrics.get("error") or "No hay datos para el período."
            return f"ℹ️ {msg}"

        return f"✅ Cierre fiscal de `{year}-{month:02d}` generado y enviado como documento adjunto."

    def _handle_cedula_lookup(self, command: str) -> str:
        """Procesa /cedula [V-12345678] consultando vía IdentityService (Caché -> SENIAT -> CNE)."""
        from src.data.database import SessionLocal
        from src.security.identity_service import (
            IdentityService,
            extract_cedula_from_payment_details,
        )

        parts = command.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "ℹ️ Uso: `/cedula V-12345678` o `/cedula 12345678`"

        extracted = extract_cedula_from_payment_details(parts[1])
        if not extracted:
            return f"⚠️ No se pudo reconocer una cédula válida en '{parts[1]}'."

        nat, num = extracted
        db = SessionLocal()
        try:
            service = IdentityService(db=db)
            info = service.lookup(nationality=nat, cedula=num)
            if info.is_valid:
                return (
                    f"👤 *Identidad Verificada*:\n\n"
                    f"• Cédula: `{info.nationality}-{info.cedula}`\n"
                    f"• Nombre Completo: *{info.full_name}*\n"
                    f"• Fuente: `{info.source}`"
                )
            else:
                return f"❌ No se encontró registro para `{nat}-{num}`: {info.error_message}"
        finally:
            db.close()

    def _handle_save_cedula(self, command: str) -> str:
        """Procesa /guardar_cedula V12345678 NOMBRE COMPLETO y lo guarda en la base de datos local."""
        from src.data.database import SessionLocal
        from src.security.identity_service import (
            IdentityService,
            extract_cedula_from_payment_details,
        )

        parts = command.strip().split(maxsplit=2)
        if len(parts) < 3:
            return "ℹ️ Uso: `/guardar_cedula V-18234567 NOMBRE COMPLETO`"

        extracted = extract_cedula_from_payment_details(parts[1])
        if not extracted:
            return f"⚠️ Cédula inválida: '{parts[1]}'."

        nat, num = extracted
        nombre = parts[2].strip().upper()

        db = SessionLocal()
        try:
            service = IdentityService(db=db)
            service.save_to_cache(nationality=nat, cedula=num, full_name=nombre, source="MANUAL")
            return f"✅ Identidad registrada con éxito:\n\n• Cédula: `{nat}-{num}`\n• Titular: *{nombre}*"
        finally:
            db.close()

    def _handle_spread_monitor(self, command: str) -> str:
        """Procesa /spread y reporta cotizaciones bancarias, arbitraje y brecha BCV."""
        from src.core.spread_monitor import SpreadMonitor
        from src.data.database import SessionLocal
        from src.data.models import Order

        monitor = SpreadMonitor()
        quotes = monitor.get_market_quotes()
        if not quotes:
            return "ℹ️ No hay cotizaciones disponibles en este momento."

        bcv_rate = 820.0
        db = SessionLocal()
        try:
            from typing import cast

            from sqlalchemy.exc import SQLAlchemyError
            latest = db.query(Order).filter(cast(Any, Order.bcv_rate > 0)).order_by(Order.id.desc()).first()
            if latest and latest.bcv_rate:
                bcv_rate = float(latest.bcv_rate)
        except (SQLAlchemyError, ValueError, TypeError) as e:
            logger.warning(f"Error consultando última tasa BCV: {e}")
        finally:
            db.close()

        ref_price = quotes[0].buy_rate
        bcv_gap = monitor.calculate_bcv_gap(p2p_price=ref_price, bcv_rate=bcv_rate)

        lines = [
            "📈 *Monitor de Spreads P2P (Binance VES / USDT)*\n",
            f"🏛️ *BCV Oficial*: `{bcv_rate:,.2f} Bs` (Brecha: `{bcv_gap:+.2f}%`)",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

        # Bancos principales
        for q in quotes[:5]:
            calc = monitor.calculate_cycle_net_profit(crypto_amount=100.0, buy_price=q.buy_rate, sell_price=q.sell_rate)
            icon = "🟢" if calc.warning_level == "OK" else ("🟡" if calc.warning_level == "CRITICAL_MARGIN" else "🔴")
            lines.append(
                f"{icon} *{q.bank_name}*:\n"
                f"   Compra: `{q.buy_rate:,.2f}` | Venta: `{q.sell_rate:,.2f}`\n"
                f"   Spread: `{q.spread_pct:+.2f}%` (`{q.spread_ves:+.2f} Bs`) | Retorno: `+{calc.net_profit_ves:,.2f} Bs`"
            )

        cross = monitor.find_best_cross_arbitrage(quotes)
        if cross:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(
                f"⚡ *Mejor Arbitraje Cruzado*:\n"
                f"Comprar en *{cross['buy_bank']}* (`{cross['buy_rate']:,.2f}`)\n"
                f"➔ Vender en *{cross['sell_bank']}* (`{cross['sell_rate']:,.2f}`)\n"
                f"Spread Cruzado: `{cross['spread_pct']:+.2f}%` | Retorno: `+{cross['net_profit_ves_100u']:,.2f} Bs/100u`"
            )

        lines.append("\n💡 *Regla de Oro*: En VES se requiere un spread ≥ *0.80%* para amortizar comisiones de Binance (0.35%) y bancarias (0.30% Pago Móvil).")
        return "\n".join(lines)

    def _handle_bcv_query(self) -> str:
        """Procesa /bcv consultando la cotización oficial en vivo y comparando con P2P."""
        from src.core.spread_monitor import SpreadMonitor
        from src.reporting.bcv_service import BCVService

        bcv = BCVService()
        rates = bcv.fetch_full_rates()
        usd = float(rates.get("usd", 0.0))
        eur = float(rates.get("eur", 0.0))
        fecha = str(rates.get("fecha_valor", "Oficial"))

        monitor = SpreadMonitor()
        quotes = monitor.get_market_quotes()
        ref_p2p = quotes[0].buy_rate if quotes else usd
        gap = monitor.calculate_bcv_gap(p2p_price=ref_p2p, bcv_rate=usd) if usd > 0 else 0.0

        return (
            f"🏛️ *Cotización Oficial Banco Central de Venezuela (BCV)*\n\n"
            f"• *USD Oficial*: `{usd:,.2f} VES/USD`\n"
            f"• *EUR Oficial*: `{eur:,.2f} VES/EUR`\n"
            f"• *Fecha Valor*: {fecha}\n"
            f"• *P2P USDT Referencial*: `{ref_p2p:,.2f} VES`\n"
            f"• *Brecha Cambiaria*: `+{gap:+.2f}%`\n\n"
            f"💡 La tasa oficial del BCV es la base legal para la valoración de inventario FIFO y cumplimiento tributario ante el SENIAT."
        )

    def _handle_compliance_sheets_sync(self) -> str:
        """Sincroniza el expediente de Compliance Bancario (4 pestañas) con Google Sheets."""
        import os
        from datetime import UTC, datetime

        from config.settings import Settings
        from src.data.database import SessionLocal
        from src.data.models import BankVoucher, Order
        from src.reporting.sheets_exporter import SheetsExporter

        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        try:
            settings = Settings()
            sheet_id = settings.GOOGLE_SHEET_ID or sheet_id
        except (ValueError, KeyError, OSError, RuntimeError):
            pass

        if not sheet_id:
            return "⚠️ *Google Sheets no está configurado*. Define `GOOGLE_SHEET_ID` en `config/.env`."

        db = SessionLocal()
        try:
            orders = db.query(Order).order_by(Order.id.desc()).all()
            vouchers = db.query(BankVoucher).all()
            if not orders:
                return "ℹ️ No hay órdenes registradas para generar el expediente de Compliance."

            exporter = SheetsExporter(credentials_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
            now_str = datetime.now(UTC).strftime("%B %Y")
            success = exporter.export_compliance_report(
                sheet_id=sheet_id,
                orders=orders,
                vouchers=vouchers,
                account_holder="COMERCIANTE P2P REGISTRADO",
                rif="V-00000000-0",
                period=now_str,
            )
            sheet_url = SheetsExporter.get_sheet_url(sheet_id)
            if success:
                return (
                    f"🏛️ *Expediente de Compliance Bancario Sincronizado en Google Sheets*\n\n"
                    f"• Órdenes auditadas: `{len(orders)}`\n"
                    f"• Comprobantes vinculados: `{len(vouchers)}`\n"
                    f"• Pestañas: Certificación, Entradas (Ventas), Salidas (Compras), Traza 1:1.\n\n"
                    f"🔗 [Abrir en Google Sheets]({sheet_url})"
                )
            else:
                return f"❌ Error exportando Compliance a Google Sheets: {exporter.last_error}"
        finally:
            db.close()

    def get_file_bytes(self, file_id: str) -> bytes | None:
        """Descarga en memoria volátil los bytes de un archivo o foto de Telegram."""
        try:
            res = self._client.get(f"{self.base_url}/getFile", params={"file_id": file_id})
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    file_path = data.get("result", {}).get("file_path")
                    if file_path:
                        download_url = f"{self.api_base_url}/file/bot{self.bot_token}/{file_path}"
                        img_res = self._client.get(download_url)
                        if img_res.status_code == 200:
                            return img_res.content
        except (httpx.RequestError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Error descargando archivo {file_id} de Telegram: {e}")
        return None

    def process_receipt_photo(self, image_bytes: bytes) -> str:
        """Procesa una foto de comprobante bancario con Gemini OCR y la concilia en la base de datos."""
        from src.data.database import SessionLocal
        from src.integrations.receipt_ocr import BankReceiptOCR, process_and_save_voucher

        db = SessionLocal()
        try:
            ocr = BankReceiptOCR()
            voucher, _matched_order = process_and_save_voucher(image_bytes, db, ocr_service=ocr)
            if voucher:
                status_emoji = "🟢 VINCULADO" if voucher.verification_status == "MATCHED" else "🟡 REGISTRADO (Sin orden coincidente)"
                order_info = f"\n• Orden P2P: `{voucher.associated_order_number}`" if voucher.associated_order_number else ""
                sender_info = f"\n• Titular: {voucher.sender_name or '-'} ({voucher.sender_id or '-'})"
                return (
                    f"🧾 *Comprobante Bancario Procesado (OCR)*\n\n"
                    f"• Banco: *{voucher.bank_name}*\n"
                    f"• Referencia: `{voucher.reference_number}`\n"
                    f"• Monto: `{voucher.amount_ves:,.2f} VES`"
                    f"{sender_info}"
                    f"{order_info}\n"
                    f"• Estado: {status_emoji}"
                )
            else:
                return "⚠️ *No se pudo procesar el comprobante*: No se pudo extraer información clara del comprobante."
        except (ValueError, KeyError, RuntimeError, OSError) as e:
            logger.error(f"Error procesando foto de comprobante en Telegram: {e}")
            return f"❌ Error interno procesando el comprobante: {e}"
        finally:
            db.close()

    def _handle_fiscal_reconciliation(self, command: str) -> str:
        """Procesa /conciliacion [YYYY-MM] y devuelve las 6 piezas contables."""
        from src.data.database import SessionLocal
        from src.reporting.fiscal_reconciler import FiscalReconciler

        parts = command.strip().split()
        now = datetime.now(UTC)
        period = f"{now.year:04d}-{now.month:02d}"
        if len(parts) > 1:
            arg = parts[1].strip()
            if len(arg) == 7 and "-" in arg:
                period = arg

        db = SessionLocal()
        try:
            reconciler = FiscalReconciler(db_session=db)
            res = reconciler.reconcile_period(period=period)

            status_icon = "🟢" if res.status == "BALANCED" else "🔴"
            return (
                f"📑 *Reconstrucción Fiscal P2P — Período `{res.period}`*\n\n"
                f"1️⃣ *Saldo Inicial*: `{res.initial_balance:,.2f} USDT`\n"
                f"2️⃣ *Entradas Cripto*: `{res.total_inflows:,.2f} USDT`\n"
                f"   • Depósitos: `{res.inflows_deposits:,.2f}` | Compras P2P: `{res.inflows_p2p_buys:,.2f}`\n"
                f"3️⃣ *Salidas Cripto*: `{res.total_outflows:,.2f} USDT`\n"
                f"   • Retiros: `{res.outflows_withdrawals:,.2f}` | Ventas P2P: `{res.outflows_p2p_sells:,.2f}`\n"
                f"4️⃣ *Volumen Operado*: `{res.volume_operated:,.2f} USDT`\n"
                f"5️⃣ *Comisiones*: `{res.total_fees:,.4f} USDT`\n"
                f"6️⃣ *Saldo Final*: Teórico `{res.calculated_final_balance:,.2f}` | Real `{res.actual_final_balance:,.2f}`\n"
                f"   • Discrepancia: `{res.discrepancy:,.4f} USDT` ({status_icon} *{res.status}*)\n\n"
                f"💰 *Liquidación ISLR (FIFO)*:\n"
                f"• Ingresos Brutos: `{res.gross_revenue_ves:,.2f} VES`\n"
                f"• Costo Adquisición: `{res.acquisition_cost_ves:,.2f} VES`\n"
                f"• Ganancia Neta Fiscal: `{res.net_profit_ves:,.2f} VES` (`${res.net_profit_usd:,.2f} USD`)\n\n"
                f"🏦 *Conciliación Bancaria*: `{res.matched_vouchers_count}/{res.vouchers_count}` comprobantes vinculados."
            )
        except (ValueError, KeyError, RuntimeError, OSError) as e:
            logger.error(f"Error ejecutando /conciliacion: {e}")
            return f"❌ Error ejecutando la reconciliación contable: {e}"
        finally:
            db.close()



class TelegramQueueDispatcher:
    """Cola asíncrona en segundo plano para envío de alertas sin bloquear la interfaz ni el motor."""

    def __init__(self, notifier: TelegramNotifier, rate_limit_delay: float = 0.5):
        self.notifier = notifier
        self.rate_limit_delay = rate_limit_delay
        self._queue: queue.Queue[tuple[str, str | None, dict[str, Any] | None]] = queue.Queue(maxsize=1000)
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
                self._queue.put_nowait(("", "__STOP__", None))
            except queue.Full:
                pass
            self._worker_thread.join(timeout=2.0)
        logger.info("TelegramQueueDispatcher detenido.")

    def queue_alert(
        self,
        text: str,
        chat_id: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Encola un mensaje para ser enviado en segundo plano de forma no bloqueante."""
        try:
            self._queue.put_nowait((text, chat_id, reply_markup))
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

            text, chat_id, reply_markup = item
            if chat_id == "__STOP__":
                self._queue.task_done()
                break

            try:
                self.notifier.send_alert(text, chat_id=chat_id, reply_markup=reply_markup)
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

                # 1. Manejo de Callback Queries (Botones Inline Interactivos)
                cb = update.get("callback_query")
                if cb:
                    cb_id = str(cb.get("id", ""))
                    from_user = cb.get("from", {})
                    user_id = from_user.get("id")
                    chat_id = str(cb.get("message", {}).get("chat", {}).get("id"))
                    cb_data = str(cb.get("data", "")).strip()

                    self.notifier.answer_callback_query(cb_id)

                    if not self.notifier.is_user_authorized(user_id):
                        self.notifier.send_alert(
                            f"⛔ *Acceso denegado*. Usuario no autorizado.\nTu ID de Telegram es: `{user_id}`.",
                            chat_id=chat_id,
                        )
                    else:
                        response = self.notifier.handle_command(user_id=user_id, command=cb_data)
                        self.notifier.send_alert(
                            response,
                            chat_id=chat_id,
                            reply_markup=self.notifier.get_quick_actions_markup(),
                        )
                    processed += 1
                    continue

                msg = update.get("message") or update.get("channel_post")
                if not msg:
                    continue

                from_user = msg.get("from", {})
                user_id = from_user.get("id")
                chat_id = str(msg.get("chat", {}).get("id"))
                photos = msg.get("photo")
                if photos and isinstance(photos, list) and len(photos) > 0:
                    if not self.notifier.is_user_authorized(user_id):
                        logger.warning(f"Foto no autorizada enviada por user_id={user_id}")
                        self.notifier.send_alert(
                            f"⛔ *Acceso denegado*. Usuario no autorizado.\n"
                            f"Tu ID de Telegram es: `{user_id}`.\n"
                            f"Añádelo a `TELEGRAM_ALLOWED_USER_IDS`.",
                            chat_id=chat_id,
                        )
                    else:
                        file_id = str(photos[-1].get("file_id", ""))
                        if file_id:
                            img_bytes = self.notifier.get_file_bytes(file_id)
                            if img_bytes:
                                ocr_reply = self.notifier.process_receipt_photo(img_bytes)
                                self.notifier.send_alert(ocr_reply, chat_id=chat_id)
                            else:
                                self.notifier.send_alert("⚠️ No se pudo descargar la imagen del comprobante.", chat_id=chat_id)
                    processed += 1
                    continue

                text = str(msg.get("text", "")).strip()

                if text.startswith("/") or text.lower().startswith(("📈", "🏛️", "📊", "📑", "⚖️", "🔄", "❓")):
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
                    markup = (
                        self.notifier.get_persistent_menu_markup()
                        if text.lower().startswith(("/start", "/ayuda", "/menu", "/help"))
                        else self.notifier.get_quick_actions_markup()
                    )
                    self.notifier.send_alert(response, chat_id=chat_id, reply_markup=markup)
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
