"""Servicio de autenticación, control de roles (RBAC) y gestión de sesiones."""

import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from src.data.models import User
from src.data.repositories import UserRepository

logger = logging.getLogger("auth_service")


class UserRole(str, Enum):
    """Roles disponibles en el sistema con permisos jerárquicos."""
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    INVITADO = "INVITADO"


class AuthService:
    """Motor criptográfico de contraseñas, validación de sesiones y control de roles."""

    ITERATIONS = 100_000
    ALGORITHM = "sha256"

    def __init__(self, user_repo: UserRepository | None = None, db_session: Any = None):
        if user_repo is not None:
            self.user_repo = user_repo
        elif db_session is not None:
            self.user_repo = UserRepository(db_session)
        else:
            raise ValueError("Debe proporcionar user_repo o db_session a AuthService")

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Genera un hash seguro con salting usando PBKDF2-HMAC-SHA256."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            cls.ALGORITHM,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.ITERATIONS
        )
        return f"pbkdf2_{cls.ALGORITHM}${cls.ITERATIONS}${salt}${key.hex()}"

    @classmethod
    def verify_password(cls, password: str, hashed: str) -> bool:
        """Verifica una contraseña contra su hash almacenado en tiempo constante."""
        try:
            parts = hashed.split("$")
            if len(parts) != 4 or not parts[0].startswith("pbkdf2_"):
                return False
            _, iterations_str, salt, key_hex = parts
            iterations = int(iterations_str)
            candidate_key = hashlib.pbkdf2_hmac(
                cls.ALGORITHM,
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations
            )
            return hmac.compare_digest(candidate_key.hex(), key_hex)
        except (ValueError, TypeError, AttributeError):
            return False

    def authenticate(self, username: str, password: str) -> User | None:
        """Valida credenciales web y retorna el usuario si es activo y válido."""
        user = self.user_repo.get_by_username(username.strip())
        if not user or not user.is_active:
            return None
        if self.verify_password(password, str(user.password_hash)):
            return user
        return None

    # Alias para compatibilidad de interfaz
    authenticate_user = authenticate


    def ensure_default_admin(
        self,
        admin_telegram_id: str | int | None = None,
        default_username: str = "admin",
        default_password: str = "AdminP2P2026!"
    ) -> User:
        """Garantiza la existencia de al menos un Administrador en la base de datos."""
        # 1. Verificar si ya existe un admin por telegram_id o rol
        if admin_telegram_id:
            user = self.user_repo.get_by_telegram_id(admin_telegram_id)
            if user:
                if user.role != UserRole.ADMIN.value:
                    self.user_repo.update_role(int(user.id), UserRole.ADMIN.value)
                return user

        # 2. Verificar si existe por username
        existing_admin = self.user_repo.get_by_username(default_username)
        if existing_admin:
            if admin_telegram_id and not existing_admin.telegram_id:
                existing_admin.telegram_id = str(admin_telegram_id)  # type: ignore[assignment]
                self.user_repo.db.commit()
            return existing_admin

        # 3. Crear el primer Administrador
        logger.warning(f"Creando Administrador inicial por defecto ('{default_username}').")
        password_hash = self.hash_password(default_password)
        new_admin = self.user_repo.create_user(
            username=default_username,
            password_hash=password_hash,
            role=UserRole.ADMIN.value,
            telegram_id=admin_telegram_id
        )
        return new_admin

    def get_role_for_telegram_id(self, telegram_id: str | int, fallback_allowed_ids: list[int] | None = None) -> UserRole | None:
        """Determina el rol de un usuario de Telegram consultando la base de datos o whitelist estática."""
        user = self.user_repo.get_by_telegram_id(telegram_id)
        if user and user.is_active:
            try:
                return UserRole(str(user.role))
            except ValueError:
                return UserRole.INVITADO

        # Fallback de compatibilidad: si está en TELEGRAM_ALLOWED_USER_IDS de .env, es ADMIN
        if fallback_allowed_ids:
            try:
                tid_int = int(telegram_id)
                if tid_int in fallback_allowed_ids:
                    return UserRole.ADMIN
            except (ValueError, TypeError):
                pass

        return None

    @staticmethod
    def create_session_token(user: User, secret_key: str, expires_hours: int = 12) -> str:
        """Genera un token de sesión firmado para Streamlit."""
        expiry = datetime.now(UTC) + timedelta(hours=expires_hours)
        payload = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "exp": expiry.timestamp()
        }
        raw_json = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            secret_key.encode("utf-8"),
            raw_json.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        import base64
        encoded_data = base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8").rstrip("=")
        return f"{encoded_data}.{signature}"

    @staticmethod
    def verify_session_token(token: str, secret_key: str) -> dict[str, Any] | None:
        """Verifica la firma y expiración de un token de sesión."""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            encoded_data, signature = parts
            import base64
            # Restaurar padding base64
            padding = len(encoded_data) % 4
            if padding:
                encoded_data += "=" * (4 - padding)
            raw_json = base64.urlsafe_b64decode(encoded_data.encode("utf-8")).decode("utf-8")
            expected_sig = hmac.new(
                secret_key.encode("utf-8"),
                raw_json.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                return None
            payload = json.loads(raw_json)
            if datetime.now(UTC).timestamp() > payload.get("exp", 0):
                return None
            return payload
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
