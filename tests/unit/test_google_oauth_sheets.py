"""Tests TDD para la vinculación directa de Google Sheets mediante OAuth 2.0 (ADR 059)."""

import base64
import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.data.database import Base
from src.data.repositories import UserRepository

SECRET = "s" * 64


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "MASTER_ENCRYPTION_KEY": "x" * 64,
        "GOOGLE_OAUTH_CLIENT_ID": "client-123.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "super-secret-value",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:3000/sheets",
    }
    base.update(overrides)
    return Settings(**base)


def _db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# Estado firmado (anti-CSRF)
# ---------------------------------------------------------------------------

def test_state_roundtrip_returns_user_id():
    from src.integrations.google_oauth import create_state, verify_state

    state = create_state(user_id=42, secret=SECRET, now=1_000)
    assert verify_state(state, secret=SECRET, now=1_100) == 42


def test_state_rejects_tampering_and_expiry():
    from src.integrations.google_oauth import (
        STATE_TTL_SECONDS,
        GoogleOAuthError,
        create_state,
        verify_state,
    )

    state = create_state(user_id=7, secret=SECRET, now=1_000)
    _payload, sig = state.split(".")
    forged_payload = base64.urlsafe_b64encode(b"8.99999999999.abc").decode().rstrip("=")

    with pytest.raises(GoogleOAuthError):
        verify_state(f"{forged_payload}.{sig}", secret=SECRET, now=1_000)
    with pytest.raises(GoogleOAuthError):
        verify_state(state, secret="otro" * 16, now=1_000)
    with pytest.raises(GoogleOAuthError):
        verify_state(state, secret=SECRET, now=1_000 + STATE_TTL_SECONDS + 1)
    with pytest.raises(GoogleOAuthError):
        verify_state("basura", secret=SECRET, now=1_000)


# ---------------------------------------------------------------------------
# URL de autorización y configuración
# ---------------------------------------------------------------------------

def test_is_oauth_configured():
    from src.integrations.google_oauth import is_oauth_configured

    assert is_oauth_configured(_settings()) is True
    assert is_oauth_configured(_settings(GOOGLE_OAUTH_CLIENT_ID=None)) is False
    assert is_oauth_configured(_settings(GOOGLE_OAUTH_CLIENT_SECRET="")) is False


def test_build_authorization_url_requests_offline_access():
    from urllib.parse import parse_qs, urlparse

    from src.integrations.google_oauth import SCOPES, build_authorization_url

    url = build_authorization_url(_settings(), state="abc.def")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert parsed.netloc == "accounts.google.com"
    assert qs["client_id"] == ["client-123.apps.googleusercontent.com"]
    assert qs["redirect_uri"] == ["http://localhost:3000/sheets"]
    assert qs["response_type"] == ["code"]
    assert qs["access_type"] == ["offline"]
    assert qs["prompt"] == ["consent"]
    assert qs["state"] == ["abc.def"]
    assert set(qs["scope"][0].split(" ")) == set(SCOPES)
    # El secreto del cliente jamás viaja en la URL del navegador
    assert "super-secret-value" not in url


def test_decode_id_token_email():
    from src.integrations.google_oauth import decode_id_token_email

    body = base64.urlsafe_b64encode(json.dumps({"email": "op@gmail.com"}).encode()).decode().rstrip("=")
    assert decode_id_token_email(f"hdr.{body}.sig") == "op@gmail.com"
    assert decode_id_token_email(None) is None
    assert decode_id_token_email("no-es-jwt") is None


# ---------------------------------------------------------------------------
# Intercambio de código
# ---------------------------------------------------------------------------

def test_exchange_code_success():
    from src.integrations.google_oauth import exchange_code

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "oauth2.googleapis.com"
        form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
        assert form["grant_type"] == "authorization_code"
        assert form["code"] == "auth-code"
        return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt-1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tokens = exchange_code(_settings(), "auth-code", http_client=client)
    assert tokens["refresh_token"] == "rt-1"


def test_exchange_code_error_does_not_leak_secret():
    from src.integrations.google_oauth import GoogleOAuthError, exchange_code

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GoogleOAuthError) as exc:
        exchange_code(_settings(), "bad", http_client=client)
    assert "super-secret-value" not in str(exc.value)


def test_exchange_code_without_refresh_token_fails_closed():
    from src.integrations.google_oauth import GoogleOAuthError, exchange_code

    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"access_token": "at"}))
    )
    with pytest.raises(GoogleOAuthError):
        exchange_code(_settings(), "code", http_client=client)


# ---------------------------------------------------------------------------
# SheetsExporter con credenciales OAuth
# ---------------------------------------------------------------------------

def test_sheets_exporter_uses_oauth_credentials():
    from src.reporting import sheets_exporter as module

    exporter = module.SheetsExporter(
        oauth_credentials={
            "client_id": "cid",
            "client_secret": "csecret",
            "refresh_token": "rt",
        }
    )
    fake_client = MagicMock()
    with patch.object(module.gspread, "authorize", return_value=fake_client) as auth:
        assert exporter._get_client() is fake_client
    creds = auth.call_args.args[0]
    assert creds.refresh_token == "rt"
    assert exporter.uses_oauth is True


def test_sheets_exporter_auth_error_fails_closed():
    from src.reporting.sheets_exporter import SheetsExporter

    exporter = SheetsExporter(auth_error="Reconecta tu cuenta de Google.")
    assert exporter._get_client() is None
    assert exporter.last_error == "Reconecta tu cuenta de Google."
    assert exporter.export("sheet", []) is False


# ---------------------------------------------------------------------------
# Rutas API
# ---------------------------------------------------------------------------

def test_start_oauth_requires_configuration():
    from src.api.routes.settings import start_google_oauth

    db = _db()
    user = UserRepository(db).create_user(username="t1", password_hash="x", role="TRADER")
    with pytest.raises(HTTPException) as exc:
        start_google_oauth(current_user=user, settings=_settings(GOOGLE_OAUTH_CLIENT_ID=None))
    assert exc.value.status_code == 503

    res = start_google_oauth(current_user=user, settings=_settings())
    assert res.authorization_url.startswith("https://accounts.google.com/")


def test_complete_oauth_rejects_state_of_another_user():
    from src.api.routes.settings import complete_google_oauth
    from src.api.schemas.settings import GoogleOAuthCallbackRequest
    from src.integrations.google_oauth import create_state

    db = _db()
    repo = UserRepository(db)
    attacker = repo.create_user(username="attacker", password_hash="x", role="TRADER")
    victim = repo.create_user(username="victim", password_hash="x", role="TRADER")
    settings = _settings()
    state = create_state(user_id=int(attacker.id), secret=settings.jwt_secret)

    with pytest.raises(HTTPException) as exc:
        complete_google_oauth(
            payload=GoogleOAuthCallbackRequest(code="c", state=state),
            current_user=victim,
            settings=settings,
            db=db,
        )
    assert exc.value.status_code == 403


def test_complete_oauth_links_account_and_creates_sheet():
    from src.api.routes import settings as route
    from src.api.schemas.settings import GoogleOAuthCallbackRequest
    from src.integrations.google_oauth import create_state

    db = _db()
    user = UserRepository(db).create_user(username="op", password_hash="x", role="TRADER")
    settings = _settings()
    state = create_state(user_id=int(user.id), secret=settings.jwt_secret)

    stored: dict[str, str] = {}
    fake_km = MagicMock()
    fake_km.store_secret.side_effect = lambda k, v, **_: stored.__setitem__(k, v)

    with (
        patch.object(route, "exchange_code", return_value={"refresh_token": "rt-xyz", "email": "op@gmail.com"}),
        patch.object(route, "ApiKeyManager", return_value=fake_km),
        patch.object(route.SheetsExporter, "create_spreadsheet", return_value="new-sheet-id"),
    ):
        res = route.complete_google_oauth(
            payload=GoogleOAuthCallbackRequest(code="c", state=state),
            current_user=user,
            settings=settings,
            db=db,
        )

    assert stored == {f"user_{user.id}:google_refresh_token": "rt-xyz"}
    assert res.oauth_connected is True
    assert res.google_account_email == "op@gmail.com"
    assert res.google_sheet_id == "new-sheet-id"
    assert user.google_auth_type == "OAUTH2"
    # El refresh token nunca se guarda en texto plano en la tabla de usuarios
    assert "rt-xyz" not in str(user.google_refresh_token_enc or "")


def test_get_config_reports_oauth_flags():
    from src.api.routes.settings import get_user_sheets_config

    db = _db()
    user = UserRepository(db).create_user(username="cfg", password_hash="x", role="TRADER")
    res = get_user_sheets_config(current_user=user, settings=_settings())
    assert res.oauth_available is True
    assert res.oauth_connected is False

    res2 = get_user_sheets_config(current_user=user, settings=_settings(GOOGLE_OAUTH_CLIENT_ID=None))
    assert res2.oauth_available is False
