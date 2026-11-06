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
    message: str


class TelegramStatusResponse(BaseModel):
    """Estado sanitizado del Bot de Telegram (Cero Secretos en Texto Plano)."""
    is_configured: bool
    bot_token_masked: str
    linked_chat_id: str | None = None
    fail_closed_5xx_enabled: bool = True
    weight_pause_enabled: bool = True
    log_sanitization_enabled: bool = True
    message: str


