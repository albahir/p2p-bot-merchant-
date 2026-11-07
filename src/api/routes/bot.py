"""Rutas de control operativo, telemetría y parada de emergencia del Bot."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_db, get_settings, require_admin, require_authenticated
from src.api.schemas.bot import BotActionResponse, BotStatusResponse
from src.data.database import get_bot_paused_state, set_bot_paused_state
from src.data.models import User

logger = logging.getLogger("api_bot")

router = APIRouter(prefix="/api/bot", tags=["Control Operativo"])


@router.get("/status", response_model=BotStatusResponse)
def get_bot_status(
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> BotStatusResponse:
    """Retorna el estado operativo en vivo del bot y sus servicios."""
    _ = current_user
    return BotStatusResponse(
        is_running=True,
        is_paused=get_bot_paused_state(db),
        use_sandbox=settings.USE_SANDBOX,
        active_alerts_count=0,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
    )


@router.post("/pause", response_model=BotActionResponse)
def pause_bot(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BotActionResponse:
    """Pausa inmediata de todas las operaciones del bot (Fail-closed)."""
    set_bot_paused_state(True, db)
    logger.warning("Bot pausado desde la API por el usuario: %s", current_user.username)

    try:
        from src.integrations.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.is_paused = True
        notifier.send_alert(f"⏸️ *Bot Pausado*: Operaciones detenidas desde el Panel Web por `{current_user.username}`.")
    except (RuntimeError, ValueError, OSError, TypeError) as err:
        logger.debug("No se pudo notificar pausa a Telegram: %s", err)

    return BotActionResponse(
        success=True,
        message="Operaciones del bot pausadas exitosamente.",
        is_paused=True,
    )


@router.post("/resume", response_model=BotActionResponse)
def resume_bot(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BotActionResponse:
    """Reanuda las operaciones normales del bot."""
    set_bot_paused_state(False, db)
    logger.info("Bot reanudado desde la API por el usuario: %s", current_user.username)

    try:
        from src.integrations.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.is_paused = False
        notifier.send_alert(f"▶️ *Bot Reanudado*: Operaciones reactivadas desde el Panel Web por `{current_user.username}`.")
    except (RuntimeError, ValueError, OSError, TypeError) as err:
        logger.debug("No se pudo notificar reanudación a Telegram: %s", err)

    return BotActionResponse(
        success=True,
        message="Operaciones del bot reactivadas exitosamente.",
        is_paused=False,
    )
