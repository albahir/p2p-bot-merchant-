"""Script de inicialización de esquemas de base de datos para PostgreSQL / SQLite.
Crea las tablas security_events, orders y demás modelos registrados.
"""

import sys
import logging
from src.data.database import engine, Base
import src.data.models  # noqa: F401 - asegura el registro de modelos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

def main():
    logger.info("Iniciando creación de tablas en la base de datos...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas exitosamente.")
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
