"""Modelos de datos Pydantic para autenticación, roles y Telegram SSO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credenciales para inicio de sesión clásico con usuario y contraseña."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class TelegramAuthData(BaseModel):
    """Datos recibidos del widget oficial de Telegram Login."""
    id: str | int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: str | int
    hash: str


class TelegramWebAppAuthData(BaseModel):
    """Datos de validación para Telegram Mini App (TMA)."""
    init_data: str = Field(..., description="Query string con los parámetros de Telegram WebApp")


class UserPublicResponse(BaseModel):
    """Representación pública del usuario (sin hash ni secretos)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    telegram_id: str | None = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Respuesta con token JWT de acceso y datos del usuario autenticado."""
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserPublicResponse


class RoleUpdateRequest(BaseModel):
    """Solicitud para actualizar el rol RBAC de un usuario."""
    role: str = Field(..., pattern="^(ADMIN|TRADER|INVITADO)$")


class StatusUpdateRequest(BaseModel):
    """Solicitud para activar o desactivar un usuario."""
    is_active: bool
