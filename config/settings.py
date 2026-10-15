"""Configuración global del sistema mediante pydantic-settings.
Aplica principios fail-closed: si variables críticas como MASTER_ENCRYPTION_KEY
o SERVER_IP_WHITELIST no están presentes o son inválidas, la carga falla.
"""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Seguridad y Cifrado
    MASTER_ENCRYPTION_KEY: str = Field(
        ...,
        description="Clave maestra de 32 bytes (64 caracteres hex) para AES-256-GCM"
    )
    SERVER_IP_WHITELIST: str = Field(
        default="127.0.0.1",
        description="Direcciones IP autorizadas para el host, separadas por coma"
    )

    # Base de Datos y Cache
    DATABASE_URL: str = Field(
        default="sqlite:///./p2p_bot.db",
        description="URL de conexión SQLAlchemy"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL del broker Redis"
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Token de bot Telegram")
    TELEGRAM_ALERT_CHAT_ID: str = Field(default="", description="Chat ID para alertas")
    TELEGRAM_ALLOWED_USER_IDS: str = Field(
        default="",
        description="IDs de Telegram autorizados para comandos, separados por coma"
    )

    # Entorno
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    @field_validator("MASTER_ENCRYPTION_KEY")
    @classmethod
    def validate_master_key(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned or len(cleaned) < 32:
            raise ValueError(
                "FAIL-CLOSED: MASTER_ENCRYPTION_KEY debe tener al menos 32 caracteres."
            )
        return cleaned

    @property
    def ip_whitelist(self) -> List[str]:
        return [ip.strip() for ip in self.SERVER_IP_WHITELIST.split(",") if ip.strip()]

    @property
    def telegram_allowed_users(self) -> List[int]:
        if not self.TELEGRAM_ALLOWED_USER_IDS:
            return []
        users: List[int] = []
        for uid in self.TELEGRAM_ALLOWED_USER_IDS.split(","):
            cleaned = uid.strip()
            if cleaned.isdigit():
                users.append(int(cleaned))
        return users
