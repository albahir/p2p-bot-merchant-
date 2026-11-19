"""Utilidades OAuth 2.0 para vincular Google Sheets directamente con la cuenta del operador."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from config.settings import Settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
STATE_TTL_SECONDS = 600
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "email",
]


class GoogleOAuthError(RuntimeError):
    """Error seguro (sin filtrar secretos) durante el flujo Google OAuth 2.0."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def _sign_payload(payload_b64: str, secret: str) -> str:
    if not secret:
        raise GoogleOAuthError("Falta secreto para firmar el estado OAuth.")
    digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_state(user_id: int, secret: str, now: int | None = None) -> str:
    """Genera un parámetro `state` firmado con HMAC-SHA256 anti-CSRF vinculado al usuario."""
    issued_at = int(now if now is not None else time.time())
    nonce = secrets.token_urlsafe(12)
    raw_payload = f"{int(user_id)}.{issued_at}.{nonce}".encode()
    payload_b64 = _b64url_encode(raw_payload)
    sig_b64 = _sign_payload(payload_b64, secret)
    return f"{payload_b64}.{sig_b64}"


def verify_state(state: str, secret: str, now: int | None = None) -> int:
    """Valida firma y vigencia del `state` OAuth y devuelve el `user_id` asociado."""
    if not state or "." not in state:
        raise GoogleOAuthError("Estado OAuth inválido.")

    parts = state.split(".", 1)
    if len(parts) != 2:
        raise GoogleOAuthError("Formato de estado OAuth inválido.")

    payload_b64, provided_sig = parts
    expected_sig = _sign_payload(payload_b64, secret)
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise GoogleOAuthError("Firma de estado OAuth inválida.")

    try:
        decoded = _b64url_decode(payload_b64).decode("utf-8")
        uid_str, issued_str, _nonce = decoded.split(".", 2)
        uid = int(uid_str)
        issued_at = int(issued_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GoogleOAuthError("Contenido de estado OAuth corrupto.") from exc

    current_ts = int(now if now is not None else time.time())
    if current_ts - issued_at > STATE_TTL_SECONDS or issued_at - current_ts > 60:
        raise GoogleOAuthError("La autorización expiró. Intenta conectar nuevamente.")

    return uid


def is_oauth_configured(settings: Settings) -> bool:
    """Indica si el cliente OAuth 2.0 de Google dispone de Client ID y Client Secret."""
    cid = (settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
    csec = (settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip()
    return bool(cid and csec)


def build_authorization_url(
    settings: Settings,
    state: str,
    redirect_uri: str | None = None,
) -> str:
    """Construye la URL de consentimiento de Google OAuth 2.0 solicitando refresh token offline."""
    if not is_oauth_configured(settings):
        raise GoogleOAuthError("Google OAuth 2.0 no está configurado en el servidor.")

    params = {
        "client_id": (settings.GOOGLE_OAUTH_CLIENT_ID or "").strip(),
        "redirect_uri": (redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI).strip(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def decode_id_token_email(id_token: str | None) -> str | None:
    """Extrae el correo del payload JWT del `id_token` entregado por Google token endpoint."""
    if not id_token or id_token.count(".") != 2:
        return None
    try:
        payload_segment = id_token.split(".")[1]
        data = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
        email = data.get("email")
        return str(email).strip() if isinstance(email, str) and email.strip() else None
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


def exchange_code(
    settings: Settings,
    code: str,
    redirect_uri: str | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Intercambia el `code` de autorización por `refresh_token` y metadatos sin exponer secretos."""
    if not is_oauth_configured(settings):
        raise GoogleOAuthError("Google OAuth 2.0 no está configurado.")
    cleaned_code = (code or "").strip()
    if not cleaned_code:
        raise GoogleOAuthError("Código de autorización vacío.")

    client_id = (settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
    client_secret = (settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip()
    target_redirect = (redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI).strip()

    form_data = {
        "code": cleaned_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": target_redirect,
        "grant_type": "authorization_code",
    }

    own_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        resp = client.post(TOKEN_ENDPOINT, data=form_data)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError("Error de red al validar autorización con Google.") from exc
    finally:
        if own_client:
            client.close()

    if resp.status_code != 200:
        err_code = "token_exchange_failed"
        try:
            err_code = str(resp.json().get("error") or err_code)
        except ValueError:
            pass
        raise GoogleOAuthError(f"Google rechazó la autorización ({err_code}).")

    try:
        data = resp.json()
    except ValueError as exc:
        raise GoogleOAuthError("Respuesta inválida del servidor OAuth de Google.") from exc

    refresh_token = str(data.get("refresh_token") or "").strip()
    if not refresh_token:
        raise GoogleOAuthError(
            "Google no devolvió permiso permanente. Vuelve a conectar aceptando el acceso."
        )

    email = decode_id_token_email(data.get("id_token"))
    result: dict[str, Any] = dict(data)
    if email:
        result["email"] = email
    return result
