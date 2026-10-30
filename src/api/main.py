"""Punto de entrada y configuración de la aplicación FastAPI (P2P Merchant API)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import Settings
from src.api.routes import auth, bot, orders, spreads, users, websockets
from src.data.database import SessionLocal, init_db
from src.security.auth_service import AuthService

logger = logging.getLogger("api_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización de base de datos y administrador por defecto."""
    logger.info("Iniciando P2P Merchant API...")
    init_db()

    # Garantizar existencia de administrador inicial
    db = SessionLocal()
    try:
        settings = Settings()
        auth_svc = AuthService(db_session=db)
        admin_tg = settings.telegram_allowed_users[0] if settings.telegram_allowed_users else None
        auth_svc.ensure_default_admin(admin_telegram_id=admin_tg)
    except (RuntimeError, ValueError, KeyError, OSError) as err:
        logger.warning("Aviso durante la inicialización del administrador por defecto: %s", err)
    finally:
        db.close()

    yield

    logger.info("Deteniendo P2P Merchant API.")


def create_app(skip_lifespan: bool = False) -> FastAPI:
    """Fabrica de la aplicación FastAPI con middlewares, seguridad y enrutadores."""
    settings = Settings()

    app = FastAPI(
        title="P2P Bot Merchant API",
        description="API REST y WebSockets para el Panel Multi-Usuario de Arbitraje P2P y Gestión Fiscal.",
        version="1.0.0",
        lifespan=None if skip_lifespan else lifespan,
    )

    # Configuración de CORS para Next.js (Local, Vercel y Cloudflare Tunnel)
    origins = settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if "*" not in origins else ["*"],
        allow_credentials=("*" not in origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Enrutadores
    app.include_router(auth.router)
    app.include_router(spreads.router)
    app.include_router(orders.router)
    app.include_router(users.router)
    app.include_router(bot.router)
    app.include_router(websockets.router)

    @app.get("/health", tags=["Salud"])
    def health_check():
        """Verificación de salud de la API (Healthcheck)."""
        return {"status": "ok", "service": "p2p-bot-merchant-api"}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Manejador global de errores para asegurar el principio de Cero Fugas de Secretos."""
        logger.error("Error no controlado en %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ha ocurrido un error interno en el servidor. La operación fue abortada de forma segura."},
        )

    return app


app = create_app()
