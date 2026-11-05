"""Tests unitarios (TDD) para el soporte dual de Google Sheets por usuario (SPEC-018)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import User
from src.data.repositories import UserRepository


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_user_model_has_google_sheet_and_oauth_fields():
    db = setup_in_memory_db()
    repo = UserRepository(db)

    user = User(
        username="trader_sheet_test",
        password_hash="fakehash",
        role="TRADER",
        google_sheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        google_refresh_token_enc="enc_token_12345",
        google_auth_type="SERVICE_ACCOUNT",  # SERVICE_ACCOUNT | OAUTH2
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    fetched = repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.google_sheet_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    assert fetched.google_refresh_token_enc == "enc_token_12345"
    assert fetched.google_auth_type == "SERVICE_ACCOUNT"


def test_update_user_google_sheet_settings():
    db = setup_in_memory_db()
    repo = UserRepository(db)

    user = repo.create_user(
        username="trader_update",
        password_hash="fakehash",
        role="TRADER",
    )

    # Actualizar configuración de Google Sheet
    user.google_sheet_id = "new_sheet_id_999"  # type: ignore[assignment]
    user.google_auth_type = "OAUTH2"  # type: ignore[assignment]
    db.commit()
    db.refresh(user)

    updated = repo.get_by_id(user.id)
    assert updated is not None
    assert updated.google_sheet_id == "new_sheet_id_999"
    assert updated.google_auth_type == "OAUTH2"


def test_sheets_exporter_append_single_voucher():
    from unittest.mock import MagicMock
    from src.reporting.sheets_exporter import SheetsExporter

    exporter = SheetsExporter(credentials_json={"dummy": "true"})
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_ws = MagicMock()
    mock_client.open_by_key.return_value = mock_sheet
    mock_sheet.worksheets.return_value = [mock_ws]
    mock_ws.title = "Comprobantes y Diario"

    exporter._get_client = MagicMock(return_value=mock_client)

    success = exporter.append_voucher_entry(
        sheet_id="test_sheet_id_123",
        date_time_str="2026-11-04 22:30:00",
        bank_name="Banco de Venezuela",
        reference_number="REF-987654",
        amount_ves=1500.50,
        sender_id="V-12345678",
        sender_name="Juan Perez",
        payment_method="PAGO_MOVIL",
        order_number="ORD-20261104-001",
        status="MATCHED",
    )

    assert success is True
    mock_client.open_by_key.assert_called_with("test_sheet_id_123")
    # Si estaba vacío, se agrega encabezado y luego la fila (2 llamadas)
    assert mock_ws.append_row.call_count == 2


def test_api_sheets_settings_endpoints():
    from config.settings import Settings
    from src.api.routes.settings import (
        _extract_sheet_id,
        get_user_sheets_config,
        update_user_sheets_config,
    )
    from src.api.schemas.settings import UpdateGoogleSheetsConfigRequest

    # Test regex extractor
    assert _extract_sheet_id("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    assert _extract_sheet_id("https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    # Test get_user_sheets_config
    db = setup_in_memory_db()
    repo = UserRepository(db)
    user = repo.create_user(username="sheets_trader", password_hash="pass", role="TRADER")
    settings = Settings(MASTER_ENCRYPTION_KEY="x" * 64, GOOGLE_SHEET_ID=None)

    config_res = get_user_sheets_config(current_user=user, settings=settings)
    assert config_res.is_connected is False
    assert config_res.google_auth_type == "SERVICE_ACCOUNT"


    # Test update_user_sheets_config
    req = UpdateGoogleSheetsConfigRequest(
        google_sheet_id="https://docs.google.com/spreadsheets/d/abc-123_XYZ/edit",
        google_auth_type="OAUTH2",
    )
    update_res = update_user_sheets_config(
        payload=req,
        current_user=user,
        settings=settings,
        db=db,
    )
    assert update_res.is_connected is True
    assert update_res.google_sheet_id == "abc-123_XYZ"
    assert update_res.google_auth_type == "OAUTH2"
    assert update_res.google_sheet_url == "https://docs.google.com/spreadsheets/d/abc-123_XYZ/edit"


def test_telegram_sheets_id_command():
    from unittest.mock import MagicMock
    from src.integrations.telegram_notifier import TelegramNotifier

    db = setup_in_memory_db()
    repo = UserRepository(db)
    user = repo.create_user(username="tg_trader", password_hash="pass", role="TRADER")
    user.telegram_id = "987654321"  # type: ignore[assignment]
    db.commit()


    # Pasar session_factory que devuelva la base de datos de test
    notifier = TelegramNotifier(
        bot_token="fake:token",
        default_chat_id="987654321",
        session_factory=lambda: db,
    )

    from unittest.mock import patch
    with patch("src.data.database.SessionLocal", return_value=db):
        resp = notifier.handle_command(
            user_id="987654321",
            command="/sheets_id https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
        )

    assert "✅" in resp
    assert "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" in resp

    # Consultar desde la base de datos para verificar persistencia
    updated_user = repo.get_by_telegram_id("987654321")
    assert updated_user is not None
    assert updated_user.google_sheet_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"






