"""Script de inicialización de esquemas de base de datos para PostgreSQL / SQLite.
Crea las tablas security_events, orders y demás modelos registrados.
"""

import logging
import sys
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path para ejecuciones directas
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.exc import SQLAlchemyError

import src.data.models  # noqa: F401 - asegura el registro de modelos
from src.data.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

def main():
    logger.info("Iniciando creación de tablas en la base de datos...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas exitosamente.")
    except SQLAlchemyError as e:
        logger.error(f"Error inicializando la base de datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
