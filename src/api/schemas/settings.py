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
