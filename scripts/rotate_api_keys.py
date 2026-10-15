"""Script interactivo de rotación de credenciales cifradas (AES-256-GCM).
"""

import getpass
import logging
import sys
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path para ejecuciones directas
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rotate_keys")

def main():
    logger.info("==> Iniciando proceso de rotación de claves...")
    try:
        settings = Settings()
        audit = AuditLogger()
        manager = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, audit_logger=audit)

        key_name = input("Identificador de la clave a rotar (ej. binance_p2p): ").strip()
        new_secret = getpass.getpass("Ingrese el nuevo valor del secreto/API Key: ").strip()

        if not key_name or not new_secret:
            logger.error("Error: Ni el identificador ni el secreto pueden estar vacíos.")
            sys.exit(1)

        manager.store_secret(key_name, new_secret)
        logger.info(f"Clave '{key_name}' rotada y cifrada exitosamente con AES-256-GCM.")
    except (ValueError, RuntimeError, OSError) as e:
        logger.error(f"Error rotando clave: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
