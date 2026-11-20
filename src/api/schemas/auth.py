"""Modelos de datos Pydantic para autenticación, roles y Telegram SSO."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    """Credenciales para inicio de sesión clásico con usuario y contraseña."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    """Datos para registro de una cuenta nueva con perfil de recuperación segura."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, description="Contraseña de al menos 8 caracteres")
    full_name: str | None = Field(default=None, max_length=120, description="Nombre completo o razón comercial")
    tax_id: str | None = Field(default=None, max_length=30, description="Cédula de Identidad o RIF (ej. V-12345678 o J-12345678-9)")
    email: str | None = Field(default=None, max_length=150, description="Correo electrónico de respaldo y recuperación")
    email_verification_token: str | None = Field(default=None, description="Token firmado tras verificar correo por OTP")
    telegram_id: str | None = Field(default=None, description="ID numérico de Telegram para vincular cuenta")
    google_sheet_id: str | None = Field(default=None, description="ID o URL de Google Sheets opcional")
    preferred_banks: list[str] = Field(default_factory=list, description="Bancos venezolanos con los que opera el usuario")
    security_question: str | None = Field(default=None, max_length=200, description="Pregunta secreta de recuperación")
    security_answer: str | None = Field(default=None, max_length=120, description="Respuesta secreta de recuperación")


class EmailSendCodeRequest(BaseModel):
    """Solicitud para enviar código OTP de 6 dígitos al correo durante registro."""
    email: str = Field(..., min_length=5, max_length=150)


class EmailVerifyCodeRequest(BaseModel):
    """Solicitud para validar el código OTP de 6 dígitos recibido en el correo."""
    email: str = Field(..., min_length=5, max_length=150)
    code: str = Field(..., min_length=6, max_length=6)


class PasswordRecoveryRequest(BaseModel):
    """Solicitud de recuperación de contraseña."""
    username: str = Field(..., description="Alias de usuario, correo electrónico o ID de Telegram registrado")
    channel: str = Field(
        default="telegram",
        pattern="^(telegram|email)$",
        description="Canal para envío del código OTP de recuperación",
    )


class RecoveryOptionsResponse(BaseModel):
    """Métodos de recuperación disponibles para un perfil."""
    has_email: bool = False
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
        pattern="^(telegram_otp|email_otp|security_question|recovery_key)$",
        description="Método de recuperación utilizado",
    )


class RecoveryProfileUpdateRequest(BaseModel):
    """Actualización de datos de respaldo y recuperación para usuarios existentes."""
    full_name: str | None = Field(default=None, max_length=120)
    tax_id: str | None = Field(default=None, max_length=30)
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
    tax_id: str | None = None
    email: str | None = None
    email_verified: bool = False
    role: str
    telegram_id: str | None = None
    google_sheet_id: str | None = None
    google_auth_type: str | None = None
    google_oauth_connected: bool = False
    google_account_email: str | None = None
    permission_source: str = "Base de Datos"
    telegram_linked: bool = False
    has_security_question: bool = False
    has_recovery_key: bool = False
    binance_api_configured: bool = False
    binance_key_type: str | None = None
    google_sheet_configured: bool = False
    preferred_banks: list[str] = Field(default_factory=list)
    bank_initial_balances: dict[str, float] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _populate_derived_connection_flags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        sheet_id_raw = getattr(data, "google_sheet_id", None)
        sheet_id = str(sheet_id_raw).strip() if sheet_id_raw else None
        auth_type = str(getattr(data, "google_auth_type", None) or "SERVICE_ACCOUNT")
        raw_marker = str(getattr(data, "google_refresh_token_enc", "") or "").strip()
        has_marker = bool(raw_marker)
        account_email: str | None = None
        if raw_marker.startswith("vault:"):
            account_email = raw_marker.split("vault:", 1)[1].strip() or None
        oauth_connected = auth_type == "OAUTH2" and has_marker
        tg_id = getattr(data, "telegram_id", None)

        pref_banks = list(getattr(data, "preferred_banks", []) or [])
        bank_bals = dict(getattr(data, "bank_initial_balances", {}) or {})

        return {
            "id": getattr(data, "id", 0),
            "username": getattr(data, "username", ""),
            "full_name": getattr(data, "full_name", None),
            "tax_id": getattr(data, "tax_id", None),
            "email": getattr(data, "email", None),
            "email_verified": bool(getattr(data, "email_verified", False)),
            "role": getattr(data, "role", "INVITADO"),
            "telegram_id": tg_id,
            "google_sheet_id": sheet_id,
            "google_auth_type": auth_type,
            "google_oauth_connected": oauth_connected,
            "google_account_email": account_email,
            "permission_source": getattr(data, "permission_source", "Base de Datos"),
            "telegram_linked": bool(tg_id and str(tg_id).strip()),
            "has_security_question": bool(getattr(data, "security_question", None)),
            "has_recovery_key": bool(getattr(data, "recovery_key_hash", None)),
            "binance_api_configured": bool(getattr(data, "binance_api_configured", False)),
            "binance_key_type": getattr(data, "binance_key_type", None),
            "google_sheet_configured": bool(sheet_id or oauth_connected),
            "preferred_banks": pref_banks,
            "bank_initial_balances": bank_bals,
            "is_active": bool(getattr(data, "is_active", True)),
            "created_at": getattr(data, "created_at", None),
        }


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
