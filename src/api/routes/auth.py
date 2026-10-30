"""Rutas de autenticación, generación de tokens JWT y Telegram SSO."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_current_user, get_db, get_settings
from src.api.schemas.auth import (
    LoginRequest,
    TelegramAuthData,
    TelegramWebAppAuthData,
    TokenResponse,
    UserPublicResponse,
)
from src.api.security import (
    create_access_token,
    verify_telegram_auth_data,
    verify_telegram_webapp_data,
)
from src.data.models import User
from src.data.repositories import UserRepository
from src.security.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Inicia sesión con credenciales tradicionales de usuario y contraseña."""
    auth_svc = AuthService(db_session=db)
    user = auth_svc.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


@router.post("/telegram", response_model=TokenResponse)
def login_telegram(
    data: TelegramAuthData,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Autentica a un usuario mediante el widget oficial de Telegram Login (SSO)."""
    payload_dict = data.model_dump(exclude_none=True)
    is_valid = verify_telegram_auth_data(
        data=payload_dict,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de Telegram inválida o datos adulterados.",
        )

    user_repo = UserRepository(db)
    telegram_id_str = str(data.id)
    user = user_repo.get_by_telegram_id(telegram_id_str)

    # Evaluar si el ID de Telegram está en la lista de administradores autorizados
    is_admin_allowed = False
    try:
        is_admin_allowed = int(data.id) in settings.telegram_allowed_users
    except (ValueError, TypeError):
        pass

    if not user:
        # Registrar nuevo usuario con rol según whitelist
        assigned_role = "ADMIN" if is_admin_allowed else "INVITADO"
        username = data.username or f"tg_{data.id}"
        # Generar hash aleatorio para contraseñas de cuentas SSO puras
        random_pass = AuthService.hash_password(f"sso_{data.id}_{data.auth_date}")
        user = user_repo.create_user(
            username=username,
            password_hash=random_pass,
            role=assigned_role,
            telegram_id=telegram_id_str,
            is_active=True,
        )
    elif is_admin_allowed and user.role != "ADMIN":
        user_repo.update_role(int(user.id), "ADMIN")
        user = user_repo.get_by_id(int(user.id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra inactiva o suspendida.",
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


@router.post("/telegram-webapp", response_model=TokenResponse)
def login_telegram_webapp(
    data: TelegramWebAppAuthData,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Autentica a un usuario que abre la aplicación como Telegram Mini App (TMA)."""
    parsed = verify_telegram_webapp_data(
        init_data=data.init_data,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
    )
    if not parsed or "user" not in parsed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma initData de Telegram Mini App inválida.",
        )

    tg_user = parsed["user"]
    tg_id = str(tg_user.get("id"))
    username = tg_user.get("username") or f"tg_{tg_id}"

    user_repo = UserRepository(db)
    user = user_repo.get_by_telegram_id(tg_id)

    is_admin_allowed = False
    try:
        is_admin_allowed = int(tg_id) in settings.telegram_allowed_users
    except (ValueError, TypeError):
        pass

    if not user:
        assigned_role = "ADMIN" if is_admin_allowed else "INVITADO"
        random_pass = AuthService.hash_password(f"tma_{tg_id}")
        user = user_repo.create_user(
            username=username,
            password_hash=random_pass,
            role=assigned_role,
            telegram_id=tg_id,
            is_active=True,
        )
    elif is_admin_allowed and user.role != "ADMIN":
        user_repo.update_role(int(user.id), "ADMIN")
        user = user_repo.get_by_id(int(user.id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva.",
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


@router.get("/me", response_model=UserPublicResponse)
def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPublicResponse:
    """Retorna los datos de perfil del usuario que posee la sesión activa."""
    return UserPublicResponse.model_validate(current_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Renueva el token de acceso para la sesión en curso."""
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(current_user.id), "username": current_user.username, "role": current_user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )
    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(current_user),
    )
