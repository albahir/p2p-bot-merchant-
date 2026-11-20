"""Modelos de datos Pydantic para configuración de claves de Binance y verificación en vivo."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BinanceStatusResponse(BaseModel):
    """Estado actual de las credenciales de Binance API y salud de conexión."""
    is_configured: bool
    api_key_masked: str
    key_type: str
    is_connected: bool
    latency_ms: float = 0.0
    clock_drift_ms: int = 0
    used_weight: int = 0
    max_weight: int = 5000
    permissions: list[str] = Field(default_factory=list)
    message: str


class SaveBinanceKeysRequest(BaseModel):
    """Solicitud para almacenar de forma cifrada las claves API de Binance."""
    api_key: str = Field(..., min_length=16, max_length=128, description="API Key pública de Binance")
    secret_key: str = Field(..., min_length=16, description="Secret Key (HMAC) o Clave Privada PEM (Ed25519/RSA)")
    key_type: Literal["HMAC", "Ed25519"] = Field(default="HMAC", description="Algoritmo de firma de la API Key")


class VerifyBinanceResponse(BaseModel):
    """Resultado del diagnóstico en caliente de la API de Binance."""
    success: bool
    is_connected: bool
    latency_ms: float
    clock_drift_ms: int
    used_weight: int
    max_weight: int = 5000
    is_weight_safe: bool
    server_time_utc: datetime | None = None
    message: str


class GoogleSheetsConfigResponse(BaseModel):
    """Configuración actual de sincronización con Google Sheets para el usuario."""
    google_sheet_id: str | None = None
    google_sheet_url: str | None = None
    google_auth_type: str = "SERVICE_ACCOUNT"  # SERVICE_ACCOUNT | OAUTH2
    service_account_email: str | None = None
    oauth_available: bool = False
    oauth_connected: bool = False
    google_account_email: str | None = None
    oauth_custom_configured: bool = False
    is_connected: bool = False
    message: str = ""


class UpdateGoogleSheetsConfigRequest(BaseModel):
    """Solicitud para actualizar el ID de la hoja o método de sincronización."""
    google_sheet_id: str | None = Field(None, description="ID o URL completa del Google Sheet")
    google_auth_type: Literal["SERVICE_ACCOUNT", "OAUTH2"] = "SERVICE_ACCOUNT"


class GoogleSheetsSyncResponse(BaseModel):
    """Resultado de sincronización manual hacia Google Sheets."""
    success: bool
    google_sheet_id: str | None = None
    google_sheet_url: str | None = None
    rows_exported: int = 0
    journal_entries_exported: int = 0
    service_account_email: str | None = None
    oauth_connected: bool = False
    message: str


class GoogleOAuthStartResponse(BaseModel):
    """URL generada para iniciar autorización directa con Google OAuth 2.0."""
    authorization_url: str


class GoogleOAuthCallbackRequest(BaseModel):
    """Código OAuth recibido desde Google y estado firmado anti-CSRF."""
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    redirect_uri: str | None = None


class GoogleOAuthClientConfigRequest(BaseModel):
    """Credenciales de aplicación Google Cloud OAuth 2.0 almacenadas cifradas (AES-256-GCM)."""
    client_id: str = Field(..., min_length=10)
    client_secret: str = Field(..., min_length=8)
    redirect_uri: str | None = None


class TelegramStatusResponse(BaseModel):
    """Estado sanitizado del Bot de Telegram (Cero Secretos en Texto Plano)."""
    is_configured: bool
    bot_token_masked: str
    linked_chat_id: str | None = None
    fail_closed_5xx_enabled: bool = True
    weight_pause_enabled: bool = True
    log_sanitization_enabled: bool = True
    message: str


class UpdateUserBanksRequest(BaseModel):
    """Solicitud para registrar o actualizar los bancos y saldos iniciales por banco del operador."""
    preferred_banks: list[str] = Field(
        default_factory=list,
        description="Lista de bancos venezolanos con los que trabaja el usuario",
    )
    bank_initial_balances: dict[str, float] = Field(
        default_factory=dict,
        description="Saldos iniciales en VES por cada banco del usuario",
    )


class UserBanksConfigResponse(BaseModel):
    """Configuración persistida de bancos preferidos y saldos iniciales del usuario."""
    preferred_banks: list[str] = Field(default_factory=list)
    bank_initial_balances: dict[str, float] = Field(default_factory=dict)
    total_initial_ves: float = 0.0
    message: str = ""



