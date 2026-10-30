"""Inyección de dependencias para FastAPI: Base de datos, configuración y RBAC."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.security import decode_access_token
from src.data.database import get_db
from src.data.models import User
from src.data.repositories import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Retorna la instancia global única de configuración del sistema."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Extrae y valida el usuario actual desde el JWT Bearer token (Fail-closed)."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Token no suministrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(
        token=token,
        secret_key=settings.jwt_secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido en token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario asociado al token no existe.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta de usuario ha sido desactivada.",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Fabrica de dependencias para control de acceso basado en roles (RBAC)."""

    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        user_role = str(current_user.role).upper()
        allowed_upper = [r.upper() for r in allowed_roles]
        if user_role not in allowed_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Rol requerido: {', '.join(allowed_upper)}",
            )
        return current_user

    return role_checker


# Atajos semánticos para rutas
require_admin = require_role("ADMIN")
require_trader = require_role("ADMIN", "TRADER")
require_authenticated = get_current_user
