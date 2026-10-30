"""Rutas de gestión de usuarios, roles RBAC y control de acceso por parte de administradores."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_admin
from src.api.schemas.auth import (
    RoleUpdateRequest,
    StatusUpdateRequest,
    UserPublicResponse,
)
from src.data.models import User
from src.data.repositories import UserRepository

logger = logging.getLogger("api_users")

router = APIRouter(prefix="/api/users", tags=["Usuarios & RBAC"])


@router.get("", response_model=list[UserPublicResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> list[UserPublicResponse]:
    """Retorna la lista de todos los usuarios registrados (Solo Administradores)."""
    repo = UserRepository(db)
    users = repo.list_all()
    return [UserPublicResponse.model_validate(u) for u in users]


@router.patch("/{user_id}/role", response_model=UserPublicResponse)
def update_user_role(
    user_id: int,
    req: RoleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> UserPublicResponse:
    """Actualiza el rol operativo de un usuario y le notifica vía Telegram si aplica."""
    repo = UserRepository(db)
    user = repo.update_role(user_id, req.role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {user_id} no encontrado.",
        )

    # Notificar al usuario vía Telegram si tiene telegram_id asociado
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

    return UserPublicResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=UserPublicResponse)
def update_user_status(
    user_id: int,
    req: StatusUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
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

    return UserPublicResponse.model_validate(user)
