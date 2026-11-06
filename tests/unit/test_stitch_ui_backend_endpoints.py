"""Pruebas unitarias TDD para endpoints backend de la interfaz institucional SPEC-020."""

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from src.api.routes.auth import register
from src.api.routes.settings import (
    get_telegram_status,
    sync_user_sheets_now,
    update_user_sheets_config,
)
from src.api.routes.users import (
    authorize_telegram_user,
    list_users,
    update_user_sheet,
)
from src.api.schemas.auth import (
    AuthorizeTelegramRequest,
    RegisterRequest,
    UpdateUserSheetRequest,
)
from src.api.schemas.settings import UpdateGoogleSheetsConfigRequest
from src.data.database import Base
from src.data.repositories import UserRepository
from src.security.auth_service import AuthService


def _setup_env():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    test_settings = Settings(
        MASTER_ENCRYPTION_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        JWT_SECRET_KEY="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        TELEGRAM_BOT_TOKEN="123456789:AAH_SUPER_SECRET_BOT_TOKEN_9999",
        TELEGRAM_ALERT_CHAT_ID="6326947793",
        TELEGRAM_ALLOWED_USER_IDS="6326947793",
        TELEGRAM_TRADER_USER_IDS="6430765245,8522428625",
    )

    repo = UserRepository(db)
    admin_user = repo.create_user(
        username="admin",
        password_hash=AuthService.hash_password("AdminPass123!"),
        role="ADMIN",
        telegram_id="6326947793",
    )
    return db, test_settings, admin_user


def test_register_extracts_and_stores_google_sheet_id():
    """Al registrarse con una URL completa de Google Sheets, extrae y guarda el Sheet ID."""
    db, settings, _ = _setup_env()
    req = RegisterRequest(
        username="trader_ccs",
        password="StrongPassword123!",
        telegram_id="6430765245",
        google_sheet_id="https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgm78Qk91xLk2/edit#gid=0",
    )
    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        resp = register(req=req, db=db, settings=settings)

    assert resp.user.role == "TRADER"
    assert resp.user.google_sheet_id == "1BxiMVs0XRA5nFMdKvBdBZjgm78Qk91xLk2"


def test_users_list_includes_permission_source_and_authorize_endpoint():
    """list_users expone permission_source (.env vs BD) y permite autorizar IDs y editar Sheet."""
    db, settings, admin_user = _setup_env()

    with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
        created = authorize_telegram_user(
            req=AuthorizeTelegramRequest(
                telegram_id="9988776655",
                username="op_valencia",
                role="TRADER",
            ),
            db=db,
            current_user=admin_user,
            settings=settings,
        )
    assert created.telegram_id == "9988776655"
    assert created.role == "TRADER"
    assert created.permission_source == "Base de Datos"

    updated = update_user_sheet(
        user_id=created.id,
        req=UpdateUserSheetRequest(google_sheet_id="1SheetIdOperadorValencia999"),
        db=db,
        current_user=admin_user,
        settings=settings,
    )
    assert updated.google_sheet_id == "1SheetIdOperadorValencia999"

    users = list_users(db=db, current_user=admin_user, settings=settings)
    by_tg = {u.telegram_id: u for u in users if u.telegram_id}
    assert by_tg["6326947793"].permission_source == ".env (Inmutable)"
    assert "6430765245" in by_tg
    assert ".env" in by_tg["6430765245"].permission_source


def test_telegram_status_masks_bot_token_strictly():
    """get_telegram_status jamás expone el token en texto plano (Regla #5 Constitución)."""
    _, settings, admin_user = _setup_env()
    status_resp = get_telegram_status(current_user=admin_user, settings=settings)

    assert status_resp.is_configured is True
    assert settings.TELEGRAM_BOT_TOKEN not in status_resp.model_dump_json()
    assert "••••" in status_resp.bot_token_masked


def test_manual_sheets_sync_endpoint():
    """sync_user_sheets_now dispara exportación sobre la hoja configurada."""
    db, settings, admin_user = _setup_env()
    update_user_sheets_config(
        payload=UpdateGoogleSheetsConfigRequest(
            google_sheet_id="1TestSheetSyncId12345",
            google_auth_type="SERVICE_ACCOUNT",
        ),
        current_user=admin_user,
        settings=settings,
        db=db,
    )

    with (
        patch("src.reporting.sheets_exporter.SheetsExporter.export", return_value=True),
        patch("src.reporting.sheets_exporter.SheetsExporter.export_accounting", return_value=True),
    ):
        sync_res = sync_user_sheets_now(current_user=admin_user, settings=settings, db=db)

    assert sync_res.success is True
    assert sync_res.google_sheet_id == "1TestSheetSyncId12345"
