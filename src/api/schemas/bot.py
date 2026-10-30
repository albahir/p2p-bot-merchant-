"""Modelos de datos Pydantic para el estado y control del Bot."""

from datetime import datetime

from pydantic import BaseModel


class BotStatusResponse(BaseModel):
    """Estado operativo del bot y de los servicios de monitoreo."""
    is_running: bool
    is_paused: bool
    use_sandbox: bool
    active_alerts_count: int
    environment: str
    timestamp: datetime


class BotActionResponse(BaseModel):
    """Confirmación de acción administrativa sobre el bot."""
    success: bool
    message: str
    is_paused: bool
