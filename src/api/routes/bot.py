"""Rutas de control operativo, telemetría y parada de emergencia del Bot."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from config.settings import Settings
from src.api.deps import get_settings, require_admin, require_authenticated
from src.api.schemas.bot import BotActionResponse, BotStatusResponse
from src.data.models import User

logger = logging.getLogger("api_bot")

router = APIRouter(prefix="/api/bot", tags=["Control Operativo"])

# Estado operacional compartido
_IS_PAUSED: bool = False


@router.get("/status", response_model=BotStatusResponse)
def get_bot_status(
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BotStatusResponse:
    """Retorna el estado operativo en vivo del bot y sus servicios."""
    return BotStatusResponse(
        is_running=True,
        is_paused=_IS_PAUSED,
        use_sandbox=settings.USE_SANDBOX,
        active_alerts_count=0,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
    )


@router.post("/pause", response_model=BotActionResponse)
def pause_bot(
    current_user: Annotated[User, Depends(require_admin)],
) -> BotActionResponse:
    """Pausa inmediata de todas las operaciones del bot (Fail-closed)."""
    global _IS_PAUSED
    _IS_PAUSED = True
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
) -> BotActionResponse:
    """Reanuda las operaciones normales del bot."""
    global _IS_PAUSED
    _IS_PAUSED = False
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
