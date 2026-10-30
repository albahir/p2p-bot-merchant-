"""Configuración global del sistema mediante pydantic-settings.
Aplica principios fail-closed: si variables críticas como MASTER_ENCRYPTION_KEY
o SERVER_IP_WHITELIST no están presentes o son inválidas, la carga falla.
"""


from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Seguridad y Cifrado
    MASTER_ENCRYPTION_KEY: str = Field(
        default="",
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
        validation_alias=AliasChoices("TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_ALLOWED_USERS"),
        description="IDs de Telegram autorizados para comandos, separados por coma"
    )
    TELEGRAM_PROXY_URL: str | None = Field(
        default=None,
        description="URL de proxy opcional para Telegram (ej. socks5://127.0.0.1:1080 o http://127.0.0.1:8080)"
    )
    TELEGRAM_API_BASE_URL: str = Field(
        default="https://api.telegram.org",
        description="URL base de la API de Telegram o reverse proxy"
    )

    # Asistente de IA (LLM) para consultas en lenguaje natural
    AI_PROVIDER: str = Field(default="gemini", description="Proveedor de IA: gemini o openai")
    AI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("AI_API_KEY", "AI_API_KEYS"),
        description="API Key(s) para el asistente de IA, separadas por coma para rotación automática"
    )
    AI_MODEL_NAME: str = Field(default="gemini-flash-lite-latest", description="Modelo LLM a utilizar")

    # Anti-suspensión en Nube (Keep-Alive)
    KEEP_ALIVE_URL: str | None = Field(
        default=None,
        description="URL pública para auto-ping keep-alive anti-suspensión (ej. https://p2p-bot-merchant.onrender.com)"
    )

    # Google Sheets
    GOOGLE_SHEET_ID: str | None = Field(
        default=None,
        description="ID del documento Google Sheets para sincronización remota"
    )
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = Field(
        default=None,
        description="Contenido JSON de la cuenta de servicio de Google para entornos Cloud"
    )
    GOOGLE_CREDENTIALS_FILE: str = Field(
        default="config/google_credentials.json",
        description="Ruta local al archivo de credenciales de Google Service Account"
    )

    # API REST, WebSockets & JWT
    JWT_SECRET_KEY: str = Field(
        default="",
        description="Clave secreta para firmar tokens JWT. Si está vacía se deriva de MASTER_ENCRYPTION_KEY"
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="Algoritmo de firma JWT")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="Expiración de tokens de acceso en minutos (por defecto 24 horas)"
    )
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,*",
        description="Orígenes CORS permitidos separados por coma"
    )

    # Entorno y Operaciones
    ENVIRONMENT: str = Field(default="development")
    USE_SANDBOX: bool = Field(default=True, description="Activa el simulador P2P si no hay claves reales")
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
    def ip_whitelist(self) -> list[str]:
        return [ip.strip() for ip in self.SERVER_IP_WHITELIST.split(",") if ip.strip()]

    @property
    def telegram_allowed_users(self) -> list[int]:
        users: list[int] = []
        if self.TELEGRAM_ALLOWED_USER_IDS:
            for uid in self.TELEGRAM_ALLOWED_USER_IDS.split(","):
                cleaned = uid.strip()
                if cleaned.isdigit():
                    users.append(int(cleaned))
        # Si no se configuró allowed_users pero hay un alert chat ID numérico (chat privado con el bot), autorizarlo
        if not users and self.TELEGRAM_ALERT_CHAT_ID:
            clean_chat = self.TELEGRAM_ALERT_CHAT_ID.strip()
            if clean_chat.isdigit() and not clean_chat.startswith("-"):
                users.append(int(clean_chat))
        return users

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET_KEY.strip() or self.MASTER_ENCRYPTION_KEY

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
