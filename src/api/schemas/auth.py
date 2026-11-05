"""Modelos de datos Pydantic para autenticación, roles y Telegram SSO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credenciales para inicio de sesión clásico con usuario y contraseña."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    """Datos para registro de una cuenta nueva."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, description="Contraseña de al menos 8 caracteres")
    telegram_id: str | None = Field(default=None, description="ID numérico de Telegram para vincular cuenta")


class PasswordRecoveryRequest(BaseModel):
    """Solicitud de recuperación de contraseña."""
    username: str = Field(..., description="Nombre de usuario o ID de Telegram registrado")


class PasswordResetRequest(BaseModel):
    """Restablecimiento de contraseña con código de verificación."""
    username: str = Field(...)
    reset_code: str = Field(..., min_length=6, max_length=16, description="Código de recuperación")
    new_password: str = Field(..., min_length=8, description="Nueva contraseña segura")


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
