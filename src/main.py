"""Punto de entrada principal para la ejecución del bot P2P Binance (Engine).
Orquesta la seguridad, validación fail-closed de IP, auditoría, sincronización de órdenes
y notificaciones por Telegram.
"""

import logging
import signal
import sys
import time

import src.data.models  # noqa: F401
from config.settings import Settings
from src.core.binance_client import (
    BinanceAuthError,
    BinanceP2PClient,
    BinanceWeightExceededError,
)
from src.core.history_ingestor import HistoryIngestor
from src.data.database import Base, SessionLocal, engine
from src.integrations.telegram_notifier import TelegramNotifier
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger
from src.security.permissions import StartupPermissionValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("p2p_engine")


class P2PBotEngine:
    """Motor orquestador del bot P2P Binance."""

    def __init__(self):
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

        # 6. Notificador de Telegram
        self.notifier = TelegramNotifier(
            bot_token=self.settings.TELEGRAM_BOT_TOKEN,
            default_chat_id=self.settings.TELEGRAM_ALERT_CHAT_ID,
            allowed_user_ids=self.settings.telegram_allowed_users
        )

        # 7. Cliente Binance P2P
        self.client = None
        self._setup_binance_client()

        # Registrar evento de inicio en auditoría append-only
        self.audit.log(
            event_type="ENGINE_START",
            key_identifier="SYSTEM",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        self.notifier.send_alert("🟢 *Bot P2P Merchant iniciado exitosamente* en modo seguro.")

    def _setup_binance_client(self):
        """Intenta recuperar las credenciales cifradas de Binance."""
        try:
            api_key = self.key_manager.get_secret("binance_api_key")
            private_key = self.key_manager.get_secret("binance_private_key")
            self.client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
            logger.info("Cliente de Binance P2P inicializado con credenciales cifradas.")
        except (KeyError, ValueError):
            logger.warning(
                "⚠️ No se encontraron credenciales de Binance ('binance_api_key' o 'binance_private_key') en la DB. "
                "Para agregarlas de forma segura ejecuta: python scripts/rotate_api_keys.py. "
                "El bot continuará en modo monitoreo pasivo / datos locales."
            )
            self.client = None

    def run_cycle(self):
        """Ejecuta una iteración de sincronización y monitoreo."""
        if self.client:
            try:
                ingestor = HistoryIngestor(self.client, SessionLocal)
                count = ingestor.ingest_recent_orders(trade_type="BUY", days_back=1)
                logger.info(f"Sincronización completada: {count} órdenes procesadas.")
            except (RuntimeError, BinanceAuthError, BinanceWeightExceededError) as e:
                logger.error(f"Error en ciclo de sincronización Binance: {e}")
                self.notifier.send_alert(f"⚠️ Error en sincronización Binance: {e}")
        else:
            logger.info("Ciclo activo: Motor funcionando (esperando credenciales de Binance para sincronización en vivo).")

    def start(self, poll_interval_seconds: int = 30):
        """Inicia el bucle principal de ejecución."""
        logger.info(f"==> Motor en ejecución. Intervalo de sondeo: {poll_interval_seconds}s.")
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

        while self.is_running:
            self.run_cycle()
            time.sleep(poll_interval_seconds)

    def handle_exit(self, signum, frame):
        """Cierre limpio y auditado (fail-closed)."""
        logger.info("==> Señal de terminación recibida. Cerrando bot...")
        self.is_running = False
        self.audit.log(
            event_type="ENGINE_STOP",
            key_identifier="SYSTEM",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        self.notifier.send_alert("🔴 *Bot P2P Merchant detenido limpiamente*.")
        sys.exit(0)


def main():
    bot = P2PBotEngine()
    bot.start(poll_interval_seconds=30)


if __name__ == "__main__":
    main()
