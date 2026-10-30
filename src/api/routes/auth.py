"""Rutas de autenticación, generación de tokens JWT y Telegram SSO."""

import secrets
import time
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_current_user, get_db, get_settings
from src.api.schemas.auth import (
    LoginRequest,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    RegisterRequest,
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

# Almacén volátil de códigos OTP de recuperación (expiran en 15 minutos)
_RECOVERY_CODES: dict[str, dict[str, Any]] = {}


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


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Registra una nueva cuenta de usuario en el sistema."""
    user_repo = UserRepository(db)
    existing_user = user_repo.get_by_username(req.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre de usuario '{req.username}' ya está registrado.",
        )

    # Evaluar si el Telegram ID está en la whitelist de administradores
    is_admin = False
    tg_id_str = str(req.telegram_id).strip() if req.telegram_id else None
    if tg_id_str:
        try:
            is_admin = int(tg_id_str) in settings.telegram_allowed_users
        except (ValueError, TypeError):
            pass

    assigned_role = "ADMIN" if is_admin else "INVITADO"
    password_hash = AuthService.hash_password(req.password)

    new_user = user_repo.create_user(
        username=req.username,
        password_hash=password_hash,
        role=assigned_role,
        telegram_id=tg_id_str,
        is_active=True,
    )

    # Notificar al administrador por Telegram si está disponible
    try:
        from src.integrations.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_alert(
            "👤 *Nuevo Usuario Registrado*\n\n"
            f"• Usuario: `{new_user.username}`\n"
            f"• Rol Asignado: `{new_user.role}`\n"
            f"• Telegram ID: `{new_user.telegram_id or 'No vinculado'}`\n"
            "Accede a /admin en la web para promover o ajustar permisos."
        )
    except (RuntimeError, ValueError, OSError, TypeError):
        pass

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(new_user.id), "username": new_user.username, "role": new_user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(new_user),
    )


@router.post("/recover-password")
def recover_password(
    req: PasswordRecoveryRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Genera y despacha un código OTP de recuperación al Telegram del usuario."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(req.username)
    if not user:
        # Buscar por Telegram ID
        user = user_repo.get_by_telegram_id(req.username)

    if not user:
        # Mensaje genérico para mitigar enumeración de cuentas
        return {
            "success": True,
            "message": "Si la cuenta existe y tiene Telegram vinculado, se ha enviado el código de recuperación.",
            "has_telegram": False,
        }

    otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = time.time() + 900  # 15 minutos

    _RECOVERY_CODES[user.username.lower()] = {
        "code": otp,
        "expires_at": expires_at,
        "user_id": user.id,
    }

    sent_to_telegram = False
    if user.telegram_id:
        try:
            from src.integrations.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send_alert(
                "🔐 *Recuperación de Contraseña*\n\n"
                f"Hola `{user.username}`, tu código de seguridad es:\n"
                f"👉 `{otp}`\n\n"
                "Válido por 15 minutos. Si no solicitaste este código, ignora este mensaje.",
                chat_id=str(user.telegram_id),
            )
            sent_to_telegram = True
        except (RuntimeError, ValueError, OSError, TypeError):
            pass

    return {
        "success": True,
        "message": (
            "Código de recuperación de 6 dígitos despachado exitosamente"
            + (" a tu Telegram vinculado." if sent_to_telegram else ". Contacta a un administrador.")
        ),
        "has_telegram": sent_to_telegram,
        "debug_code": otp if not sent_to_telegram else None,
    }


@router.post("/reset-password")
def reset_password(
    req: PasswordResetRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Aplica el cambio de contraseña utilizando el código de recuperación."""
    record = _RECOVERY_CODES.get(req.username.lower())
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay ninguna solicitud de recuperación activa para este usuario o ha expirado.",
        )

    if time.time() > record["expires_at"]:
        _RECOVERY_CODES.pop(req.username.lower(), None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código de recuperación ha expirado (límite de 15 minutos).",
        )

    if record["code"] != req.reset_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de recuperación inválido.",
        )

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(record["user_id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    new_hash = AuthService.hash_password(req.new_password)
    user.password_hash = new_hash
    db.commit()

    # Consumir el código para evitar reuso
    _RECOVERY_CODES.pop(req.username.lower(), None)

    return {
        "success": True,
        "message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña.",
    }


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
