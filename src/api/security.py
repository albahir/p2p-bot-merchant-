"""Seguridad criptográfica para la API REST: JWT y validación oficial de Telegram SSO."""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

logger = logging.getLogger("api_security")


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    expires_delta: timedelta | None = None,
    algorithm: str = "HS256",
) -> str:
    """Genera un JWT firmado con payload de usuario y fecha de expiración."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any] | None:
    """Verifica y decodifica un JWT. Retorna None si es inválido o expiró (Fail-closed)."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except (jwt.PyJWTError, ValueError, TypeError) as err:
        logger.debug("Token JWT inválido o expirado: %s", err)
        return None


def verify_telegram_auth_data(
    data: dict[str, Any],
    bot_token: str,
    max_age_seconds: int = 86400,
) -> bool:
    """Valida los datos y la firma HMAC-SHA256 del widget oficial de Telegram Login."""
    if "hash" not in data or not bot_token:
        return False

    received_hash = str(data["hash"])
    auth_date_str = str(data.get("auth_date", "0"))
    try:
        auth_date = int(auth_date_str)
        if (time.time() - auth_date) > max_age_seconds:
            return False
    except (ValueError, TypeError):
        return False

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    data_check_list = [f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"]
    data_check_string = "\n".join(data_check_list)
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)


def verify_telegram_webapp_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, Any] | None:
    """Valida los datos `initData` de Telegram Mini App (TMA). Retorna los parámetros verificados."""
    if not init_data or not bot_token:
        return None

    try:
        parsed_qsl = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        params = dict(parsed_qsl)
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None

        auth_date_str = params.get("auth_date", "0")
        try:
            auth_date = int(auth_date_str)
            if (time.time() - auth_date) > max_age_seconds:
                return None
        except (ValueError, TypeError):
            return None

        # Mini App: secret_key = HMAC_SHA256(b"WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        data_check_list = [f"{k}={v}" for k, v in sorted(params.items())]
        data_check_string = "\n".join(data_check_list)
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        result: dict[str, Any] = dict(params)
        if "user" in result and isinstance(result["user"], str):
            try:
                result["user"] = json.loads(result["user"])
            except json.JSONDecodeError:
                pass
        return result
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as err:
        logger.debug("Error procesando Telegram WebApp initData: %s", err)
        return None
