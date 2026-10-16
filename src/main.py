"""Punto de entrada principal para la ejecución del bot P2P Binance (Engine).
Orquesta la seguridad, validación fail-closed de IP, auditoría, sincronización de órdenes,
simulación Sandbox y notificaciones resilientes por Telegram.
"""

import logging
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

import src.data.models  # noqa: F401
from config.settings import Settings
from src.core.binance_client import (
    BinanceAuthError,
    BinanceP2PClient,
    BinanceWeightExceededError,
)
from src.core.binance_mock import MockBinanceP2PClient
from src.core.history_ingestor import HistoryIngestor
from src.data.database import Base, SessionLocal, engine
from src.integrations.ai_assistant import TelegramAIAgent
from src.integrations.telegram_notifier import (
    TelegramCommandPoller,
    TelegramNotifier,
    TelegramQueueDispatcher,
)
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger
from src.security.permissions import StartupPermissionValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("p2p_engine")


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Manejador HTTP simple para probes de salud (Koyeb, Render, Docker)."""

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"p2p-bot-merchant"}\n')

    def log_message(self, format: str, *args: object) -> None:
        # Suprimir logs continuos de sondeos de salud
        pass


class KeepAlivePinger:
    """Hilo ligero que envía periódicamente un ping HTTP a la URL pública del servicio
    (Render / Koyeb) para evitar que la plataforma conmute a suspensión por inactividad.
    """

    def __init__(self, target_url: str | None = None, interval_seconds: int = 600):
        # Render expone automáticamente RENDER_EXTERNAL_URL en el contenedor
        self.target_url = target_url or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("KEEP_ALIVE_URL")
        self.interval = interval_seconds
        self.is_running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.target_url:
            logger.info("KeepAlivePinger inactivo: No se configuró URL pública (RENDER_EXTERNAL_URL).")
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="keep_alive_pinger")
        self._thread.start()
        logger.info(f"KeepAlivePinger activo: Auto-ping cada {self.interval}s a {self.target_url}")

    def _run(self) -> None:
        # Esperar 60 segundos tras arranque inicial
        time.sleep(60)
        while self.is_running:
            try:
                if self.target_url:
                    with httpx.Client(timeout=10.0) as client:
                        res = client.get(self.target_url)
                        logger.info(f"KeepAlive ping enviado a {self.target_url} -> HTTP {res.status_code}")
            except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
                logger.debug(f"KeepAlive ping fallo temporal (no crítico): {e}")
            time.sleep(self.interval)

    def stop(self) -> None:
        self.is_running = False


class P2PBotEngine:
    """Motor orquestador del bot P2P Binance con soporte dual Producción / Sandbox."""

    def __init__(self, use_sandbox: bool | None = None):
        self.is_running = True
        logger.info("==> Inicializando p2p-bot-merchant...")

        # 1. Asegurar tablas creadas
        Base.metadata.create_all(bind=engine)

        # 2. Cargar configuración con validación fail-closed
        try:
            self.settings = Settings()
            logger.info("Configuración de entorno cargada correctamente.")
        except (ValueError, RuntimeError) as e:
            logger.critical(f"FAIL-CLOSED: Error cargando configuración: {e}")
            sys.exit(1)

        # Determinar si opera en modo Sandbox o Real
        if use_sandbox is not None:
            self.use_sandbox = use_sandbox
        else:
            self.use_sandbox = self.settings.USE_SANDBOX

        # 3. Auditoría e integridad
        self.audit = AuditLogger(SessionLocal)

        # 4. Verificación de IP en lista blanca
        self.validator = StartupPermissionValidator(self.settings, self.audit)
        try:
            # En entorno local se valida contra 127.0.0.1
            self.validator.verify_ip_whitelist("127.0.0.1")
        except PermissionError as e:
            logger.critical(str(e))
            sys.exit(1)

        # 5. Inicializar gestor de credenciales cifradas (AES-256-GCM)
        self.key_manager = ApiKeyManager(
            master_key=self.settings.MASTER_ENCRYPTION_KEY,
            audit_logger=self.audit,
            db_session_factory=SessionLocal
        )

        # 6. Notificador de Telegram resiliente y cola en background
        self.notifier = TelegramNotifier(
            bot_token=self.settings.TELEGRAM_BOT_TOKEN,
            default_chat_id=self.settings.TELEGRAM_ALERT_CHAT_ID,
            allowed_user_ids=self.settings.telegram_allowed_users,
            proxy_url=self.settings.TELEGRAM_PROXY_URL,
            api_base_url=self.settings.TELEGRAM_API_BASE_URL,
            use_sandbox=self.use_sandbox
        )
        self.dispatcher = TelegramQueueDispatcher(self.notifier)
        self.dispatcher.start()

        # Inicializar Asistente de IA para responder consultas en lenguaje natural
        self.ai_agent = TelegramAIAgent(
            api_key=self.settings.AI_API_KEY,
            provider=self.settings.AI_PROVIDER,
            model_name=self.settings.AI_MODEL_NAME,
            db_session_factory=SessionLocal
        )
        self.poller = TelegramCommandPoller(self.notifier, ai_agent=self.ai_agent, poll_interval=2.0)
        self.poller.start()

        # 7. Cliente Binance P2P (o Sandbox)
        self.client: BinanceP2PClient | MockBinanceP2PClient | None = None
        self._setup_binance_client()

        # Registrar evento de inicio en auditoría append-only
        self.audit.log(
            event_type="ENGINE_START",
            key_identifier="SYSTEM",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        mode_label = "🧪 SANDBOX (Simulación Activa)" if self.use_sandbox else "🔴 PRODUCCIÓN"
        self.instance_tag = f"[`{socket.gethostname()[:8]}` | pid:{os.getpid()}]"
        self.dispatcher.queue_alert(
            f"🟢 *Bot P2P Merchant iniciado exitosamente* {self.instance_tag}\n"
            f"Modo: {mode_label}\n"
            f"Monitoreo y escucha de comandos activos."
        )

        # 8. Iniciar servidores HTTP ligeros para probes de salud (Koyeb, Render, Docker)
        self.httpd_servers: list[HTTPServer] = []
        self._start_healthcheck_server()

        # 9. Iniciar KeepAlivePinger anti-suspensión en Nube (Render / Koyeb)
        self.pinger = KeepAlivePinger(target_url=self.settings.KEEP_ALIVE_URL)
        self.pinger.start()

    def _start_healthcheck_server(self) -> None:
        """Inicia listeners HTTP en los puertos comunes de Cloud (PORT, 8000, 10000)."""
        ports_to_try: list[int] = []
        env_port = os.getenv("PORT")
        if env_port and env_port.strip().isdigit():
            ports_to_try.append(int(env_port.strip()))
        for default_port in (8000, 10000):
            if default_port not in ports_to_try:
                ports_to_try.append(default_port)

        for port in ports_to_try:
            try:
                httpd = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
                self.httpd_servers.append(httpd)
                threading.Thread(target=httpd.serve_forever, daemon=True).start()
                logger.info(f"Servidor de Healthcheck activo en http://0.0.0.0:{port}")
            except OSError as e:
                logger.debug(f"Puerto {port} no disponible o ya enlazado: {e}")

    def _setup_binance_client(self):
        """Inicializa el cliente real de Binance o el simulador Sandbox."""
        has_real_keys = False
        api_key = ""
        private_key = ""
        try:
            api_key = self.key_manager.get_secret("binance_api_key")
            private_key = self.key_manager.get_secret("binance_private_key")
            if api_key and private_key:
                has_real_keys = True
        except (KeyError, ValueError):
            has_real_keys = False

        if not has_real_keys or self.use_sandbox:
            self.client = MockBinanceP2PClient(enable_default_orders=True)
            if not has_real_keys:
                self.use_sandbox = True
                self.notifier.use_sandbox = True
                logger.info("🧪 Modo Sandbox activo: No se encontraron credenciales reales de Binance en la DB.")
            else:
                logger.info("🧪 Modo Sandbox forzado por configuración (USE_SANDBOX=True).")
            return

        try:
            self.client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
            self.use_sandbox = False
            self.notifier.use_sandbox = False
            logger.info("🟢 Cliente oficial de Binance P2P inicializado con credenciales cifradas (MODO PRODUCCIÓN).")
        except (ValueError, KeyError, RuntimeError, BinanceAuthError) as e:
            logger.error(f"Error inicializando cliente real de Binance: {e}. Activando Sandbox de respaldo.")
            self.use_sandbox = True
            self.notifier.use_sandbox = True
            self.client = MockBinanceP2PClient(enable_default_orders=True)

    def run_cycle(self):
        """Ejecuta una iteración de sincronización y monitoreo."""
        if self.client:
            try:
                ingestor = HistoryIngestor(self.client, SessionLocal)
                count = ingestor.ingest_recent_orders(trade_type="ALL", days_back=1)
                mode_str = "[SANDBOX]" if self.use_sandbox else "[PROD]"
                logger.info(f"{mode_str} Sincronización completada: {count} órdenes procesadas.")
                if count > 0:
                    self.dispatcher.queue_alert(
                        f"📦 *{mode_str} Nuevas Órdenes P2P*\n"
                        f"Se han registrado e ingestadas *{count}* órdenes en la base de datos."
                    )
            except (RuntimeError, BinanceAuthError, BinanceWeightExceededError) as e:
                logger.error(f"Error en ciclo de sincronización Binance: {e}")
                self.dispatcher.queue_alert(f"⚠️ Error en sincronización Binance: {e}")
        else:
            logger.info("Ciclo inactivo: Cliente no inicializado.")

    def start(self, poll_interval_seconds: int = 30):
        """Inicia el bucle principal de ejecución."""
        logger.info(f"==> Motor en ejecución. Intervalo de sondeo: {poll_interval_seconds}s.")
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

        while self.is_running:
            try:
                self.run_cycle()
            except (RuntimeError, ValueError, KeyError, OSError):
                logger.exception("Error imprevisto en ciclo de ejecución")
            time.sleep(poll_interval_seconds)

    def handle_exit(self, signum, frame):
        """Cierre limpio y auditado (fail-closed)."""
        logger.info(f"==> Señal de terminación recibida ({signum}). Cerrando bot...")
        self.is_running = False
        self.pinger.stop()
        self.poller.stop()
        self.dispatcher.queue_alert(f"🔴 *Bot P2P Merchant detenido limpiamente* {self.instance_tag}.")
        self.dispatcher.wait_until_empty(timeout=2.0)
        self.dispatcher.stop()
        for server in self.httpd_servers:
            server.shutdown()
        self.audit.log(
            event_type="ENGINE_STOP",
            key_identifier="SYSTEM",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        sys.exit(0)


def main():
    bot = P2PBotEngine()
    bot.start(poll_interval_seconds=30)


if __name__ == "__main__":
    main()
