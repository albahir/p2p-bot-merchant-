"""Modelos de datos Pydantic para autenticación, roles y Telegram SSO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credenciales para inicio de sesión clásico con usuario y contraseña."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    """Datos para registro de una cuenta nueva con perfil de recuperación segura."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, description="Contraseña de al menos 8 caracteres")
    full_name: str | None = Field(default=None, max_length=120, description="Nombre completo o razón comercial")
    email: str | None = Field(default=None, max_length=150, description="Correo electrónico de respaldo y recuperación")
    telegram_id: str | None = Field(default=None, description="ID numérico de Telegram para vincular cuenta")
    google_sheet_id: str | None = Field(default=None, description="ID o URL de Google Sheets opcional")
    security_question: str | None = Field(default=None, max_length=200, description="Pregunta secreta de recuperación")
    security_answer: str | None = Field(default=None, max_length=120, description="Respuesta secreta de recuperación")


class PasswordRecoveryRequest(BaseModel):
    """Solicitud de recuperación de contraseña."""
    username: str = Field(..., description="Alias de usuario, correo electrónico o ID de Telegram registrado")


class RecoveryOptionsResponse(BaseModel):
    """Métodos de recuperación disponibles para un perfil."""
    has_telegram: bool = False
    has_security_question: bool = False
    security_question: str | None = None
    has_recovery_key: bool = False
    is_locked: bool = False


class PasswordResetRequest(BaseModel):
    """Restablecimiento de contraseña multi-método."""
    username: str = Field(..., description="Alias de usuario, correo electrónico o ID de Telegram")
    reset_code: str = Field(..., min_length=3, max_length=120, description="Código OTP, respuesta secreta o Llave Maestra")
    new_password: str = Field(..., min_length=8, description="Nueva contraseña segura")
    method: str = Field(
        default="telegram_otp",
        pattern="^(telegram_otp|security_question|recovery_key)$",
        description="Método de recuperación utilizado",
    )


class RecoveryProfileUpdateRequest(BaseModel):
    """Actualización de datos de respaldo y recuperación para usuarios existentes."""
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=150)
    security_question: str | None = Field(default=None, max_length=200)
    security_answer: str | None = Field(default=None, max_length=120)
    regenerate_recovery_key: bool = Field(default=False)


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
    """Representación pública del usuario (sin hash, claves ni saldos privados)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    role: str
    telegram_id: str | None = None
    google_sheet_id: str | None = None
    permission_source: str = "Base de Datos"
    telegram_linked: bool = False
    has_security_question: bool = False
    has_recovery_key: bool = False
    binance_api_configured: bool = False
    binance_key_type: str | None = None
    google_sheet_configured: bool = False
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Respuesta con token JWT de acceso y datos del usuario autenticado."""
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserPublicResponse
    recovery_key: str | None = Field(
        default=None,
        description="Llave Maestra de un solo uso emitida únicamente al crear el perfil",
    )


class RoleUpdateRequest(BaseModel):
    """Solicitud para actualizar el rol RBAC de un usuario."""
    role: str = Field(..., pattern="^(ADMIN|TRADER|INVITADO)$")


class StatusUpdateRequest(BaseModel):
    """Solicitud para activar o desactivar un usuario."""
    is_active: bool


class AuthorizeTelegramRequest(BaseModel):
    """Solicitud para autorizar o registrar un operador por ID de Telegram desde la web."""
    telegram_id: str = Field(..., min_length=4, max_length=30)
    username: str | None = Field(default=None, max_length=50)
    role: str = Field(default="TRADER", pattern="^(ADMIN|TRADER|INVITADO)$")


class UpdateUserSheetRequest(BaseModel):
    """Solicitud de administrador para vincular/editar la hoja Google Sheets de un operador."""
    google_sheet_id: str | None = Field(default=None, max_length=255)
