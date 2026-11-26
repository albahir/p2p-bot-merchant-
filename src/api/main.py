"""Punto de entrada y configuración de la aplicación FastAPI (P2P Merchant API)."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from config.settings import Settings
from src.api.routes import accounting, auth, bot, fiscal, market, orders, spreads, users, websockets
from src.api.routes import settings as settings_route
from src.core.market_analytics import MarketCollectorService
from src.data.database import SessionLocal, init_db, seed_env_operators
from src.security.auth_service import AuthService

logger = logging.getLogger("api_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización de base de datos y administrador por defecto."""
    logger.info("Iniciando P2P Merchant API...")
    init_db()

    # Garantizar existencia de administrador inicial y operadores blindados en .env
    db = SessionLocal()
    try:
        settings = Settings()
        auth_svc = AuthService(db_session=db)
        admin_tg = settings.telegram_allowed_users[0] if settings.telegram_allowed_users else None
        auth_svc.ensure_default_admin(admin_telegram_id=admin_tg)
        seed_env_operators(db, settings)

        # Garantizar que la tasa oficial BCV del día hábil esté persistida en `bcv_rate_history` al arrancar
        from src.reporting.bcv_history_service import BCVHistoryService

        BCVHistoryService(db_session=db).get_or_fetch_current_rates()
    except (RuntimeError, ValueError, KeyError, OSError) as err:
        logger.warning("Aviso durante la inicialización del administrador por defecto: %s", err)
    finally:
        db.close()

    collector_task: asyncio.Task[None] | None = None
    if os.getenv("DISABLE_MARKET_COLLECTOR") != "1":
        def _collect_market_once(prune_old: bool = False) -> None:
            from src.data.repositories import MarketDataRepository

            session = SessionLocal()
            try:
                MarketCollectorService(session).capture_snapshot(collect_missing_banks=True)
                if prune_old:
                    MarketDataRepository(session).prune_old_snapshots(days_keep=30)
            finally:
                session.close()

        async def _market_collector_loop() -> None:
            await asyncio.sleep(3.0)
            cycle = 0
            while True:
                try:
                    should_prune = (cycle % 30) == 0
                    await asyncio.to_thread(_collect_market_once, should_prune)
                    cycle += 1
                except (httpx.HTTPError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
                    logger.debug("Recolector P2P en espera (%s)", exc)
                await asyncio.sleep(120.0)

        collector_task = asyncio.create_task(_market_collector_loop())

    yield

    if collector_task is not None:
        collector_task.cancel()
        with suppress(asyncio.CancelledError):
            await collector_task

    logger.info("Deteniendo P2P Merchant API.")


class SecurityHeadersMiddleware:
    """Middleware ASGI puro que inyecta cabeceras defensivas OWASP sin depender de BaseHTTPMiddleware."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                if path.startswith("/api/"):
                    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


def create_app(skip_lifespan: bool = False, settings: Settings | None = None) -> FastAPI:
    """Fabrica de la aplicación FastAPI con middlewares, seguridad y enrutadores."""
    try:
        app_settings = settings or Settings()
    except (ValidationError, ValueError, TypeError, OSError):
        # Fallback defensivo ante importación en entornos sin configuración (CI / test collection)
        app_settings = Settings(
            MASTER_ENCRYPTION_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            JWT_SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )

    is_prod = app_settings.ENVIRONMENT.strip().lower() == "production"
    app = FastAPI(
        title="P2P Bot Merchant API",
        description="API REST y WebSockets para el Panel Multi-Usuario de Arbitraje P2P y Gestión Fiscal.",
        version="1.0.0",
        lifespan=None if skip_lifespan else lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # Configuración de CORS para Next.js (Local, Vercel y Cloudflare Tunnel)
    origins = app_settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if "*" not in origins else ["*"],
        allow_credentials=("*" not in origins),
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

    # Enrutadores
    app.include_router(auth.router)
    app.include_router(spreads.router)
    app.include_router(orders.router)
    app.include_router(fiscal.router)
    app.include_router(accounting.router)
    app.include_router(users.router)
    app.include_router(settings_route.router)
    app.include_router(bot.router)
    app.include_router(websockets.router)
    app.include_router(market.router)

    @app.get("/", tags=["Salud"])
    @app.head("/", tags=["Salud"])
    def root_health():
        """Sondeo raíz para balanceadores de carga (Render, Koyeb, Cloudflare)."""
        return {"status": "ok", "service": "p2p-bot-merchant-api"}

    @app.get("/health", tags=["Salud"])
    @app.head("/health", tags=["Salud"])
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


try:
    app = create_app()
except (ValidationError, ValueError, TypeError, OSError) as _init_err:
    logger.debug("Inicialización diferida de app: %s", _init_err)
    app = None  # type: ignore[assignment]
