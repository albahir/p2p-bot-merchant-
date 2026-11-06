"""Rutas de gestión de usuarios, roles RBAC y control de acceso por parte de administradores."""

import logging
import re
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_db, get_settings, require_admin
from src.api.schemas.auth import (
    AuthorizeTelegramRequest,
    RoleUpdateRequest,
    StatusUpdateRequest,
    UpdateUserSheetRequest,
    UserPublicResponse,
)
from src.data.models import User
from src.data.repositories import UserRepository
from src.security.auth_service import AuthService

logger = logging.getLogger("api_users")

router = APIRouter(prefix="/api/users", tags=["Usuarios & RBAC"])


def _extract_sheet_id(raw_input: str | None) -> str | None:
    if not raw_input:
        return None
    cleaned = raw_input.strip()
    if not cleaned:
        return None
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", cleaned)
    return match.group(1) if match else cleaned


def _resolve_permission_source(user: User, settings: Settings) -> str:
    tg = str(user.telegram_id).strip() if user.telegram_id else ""
    if tg.isdigit():
        tg_int = int(tg)
        if tg_int in settings.telegram_allowed_users:
            return ".env (Inmutable)"
        if tg_int in settings.telegram_trader_users:
            return ".env + BD"
    return "Base de Datos"


def _to_public_response(user: User, settings: Settings) -> UserPublicResponse:
    resp = UserPublicResponse.model_validate(user)
    resp.permission_source = _resolve_permission_source(user, settings)
    return resp


@router.get("", response_model=list[UserPublicResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[UserPublicResponse]:
    """Retorna todos los usuarios registrados y sincroniza operadores fijos de .env."""
    _ = current_user
    repo = UserRepository(db)

    # Asegurar que los traders declarados en TELEGRAM_TRADER_USERS aparezcan en la tabla
    for tg_id in settings.telegram_trader_users:
        tg_str = str(tg_id)
        existing = repo.get_by_telegram_id(tg_str)
        if not existing:
            alias = f"tg_{tg_str}"
            if repo.get_by_username(alias):
                alias = f"tg_{tg_str}_{secrets.token_hex(2)}"
            repo.create_user(
                username=alias,
                password_hash=AuthService.hash_password(secrets.token_urlsafe(16)),
                role="TRADER",
                telegram_id=tg_str,
                is_active=True,
            )

    users = repo.list_all()
    return [_to_public_response(u, settings) for u in users]


@router.post("/authorize-telegram", response_model=UserPublicResponse)
def authorize_telegram_user(
    req: AuthorizeTelegramRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublicResponse:
    """Autoriza o promueve un ID numérico de Telegram directamente desde la consola web."""
    repo = UserRepository(db)
    tg_clean = req.telegram_id.strip()
    existing = repo.get_by_telegram_id(tg_clean)

    if existing:
        updated = repo.update_role(int(existing.id), req.role)  # type: ignore[arg-type]
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo actualizar el usuario existente.",
            )
        repo.set_active_status(int(updated.id), True)  # type: ignore[arg-type]
        user_obj = updated
    else:
        alias = (req.username or "").strip() or f"tg_{tg_clean}"
        if repo.get_by_username(alias):
            alias = f"{alias}_{tg_clean[-4:]}"
        user_obj = repo.create_user(
            username=alias,
            password_hash=AuthService.hash_password(secrets.token_urlsafe(16)),
            role=req.role,
            telegram_id=tg_clean,
            is_active=True,
        )

    try:
        from src.integrations.telegram_notifier import TelegramNotifier

        notifier = TelegramNotifier()
        notifier.send_alert(
            f"✅ *Acceso Autorizado en P2P Merchant OS*\n\n"
            f"Tu cuenta (`{user_obj.username}`) fue autorizada con rol *{req.role}* por `{current_user.username}`.",
            chat_id=tg_clean,
            reply_markup=notifier.get_persistent_menu_markup(role=req.role),
        )
    except (RuntimeError, ValueError, OSError, TypeError) as err:
        logger.warning("No se pudo enviar alerta de autorización a %s: %s", tg_clean, err)

    return _to_public_response(user_obj, settings)


@router.patch("/{user_id}/sheet", response_model=UserPublicResponse)
def update_user_sheet(
    user_id: int,
    req: UpdateUserSheetRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublicResponse:
    """Permite al Administrador vincular o cambiar la hoja Google Sheets de un operador."""
    _ = current_user
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado.",
        )

    user.google_sheet_id = _extract_sheet_id(req.google_sheet_id)  # type: ignore[assignment]
    db.commit()
    db.refresh(user)
    return _to_public_response(user, settings)


@router.patch("/{user_id}/role", response_model=UserPublicResponse)
def update_user_role(
    user_id: int,
    req: RoleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublicResponse:
    """Actualiza el rol operativo de un usuario y le notifica vía Telegram si aplica."""
    repo = UserRepository(db)
    user = repo.update_role(user_id, req.role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado.",
        )

    if user.telegram_id:
        try:
            from src.integrations.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier()
            role_emoji = "🛡️" if req.role == "ADMIN" else ("📊" if req.role == "TRADER" else "👀")
            msg = (
                f"🔔 *Actualización de Permisos en P2P Bot*\n\n"
                f"Tu rol en la plataforma ha sido actualizado a: {role_emoji} *{req.role}*\n"
                f"Modificado por: `{current_user.username}`\n\n"
                f"Usa `/ayuda` en el bot o refresca la web para ver tus nuevas opciones."
            )
            notifier.send_alert(
                msg,
                chat_id=str(user.telegram_id),
                reply_markup=notifier.get_persistent_menu_markup(role=req.role),
            )
        except (RuntimeError, ValueError, OSError, TypeError) as err:
            logger.warning("No se pudo enviar notificación de Telegram al usuario %s: %s", user.id, err)

    return _to_public_response(user, settings)


@router.patch("/{user_id}/status", response_model=UserPublicResponse)
def update_user_status(
    user_id: int,
    req: StatusUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublicResponse:
    """Activa o suspende el acceso de un usuario al sistema."""
    if user_id == current_user.id and not req.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un administrador no puede desactivar su propia cuenta.",
        )

    repo = UserRepository(db)
    user = repo.set_active_status(user_id, req.is_active)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado.",
        )

    if user.telegram_id and not req.is_active:
        try:
            from src.integrations.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier()
            notifier.send_alert(
                "⚠️ *Acceso Suspendido*\n\nTu acceso a P2P Bot Merchant ha sido revocado temporalmente.",
                chat_id=str(user.telegram_id),
            )
        except (RuntimeError, ValueError, OSError, TypeError) as err:
            logger.warning("No se pudo enviar notificación de suspensión: %s", err)

    return _to_public_response(user, settings)
