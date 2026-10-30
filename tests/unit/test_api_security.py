"""Pruebas unitarias para seguridad de la API: JWT y Telegram SSO / WebApp Auth."""

import hashlib
import hmac
import time
from datetime import timedelta

from src.api.security import (
    create_access_token,
    decode_access_token,
    verify_telegram_auth_data,
    verify_telegram_webapp_data,
)

SECRET_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz_1234567"


def test_create_and_decode_valid_jwt():
    """Valida la generación y decodificación correcta de un token JWT."""
    payload = {"sub": "1", "username": "admin", "role": "ADMIN"}
    token = create_access_token(payload, secret_key=SECRET_KEY, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token, secret_key=SECRET_KEY)
    assert decoded is not None
    assert decoded["sub"] == "1"
    assert decoded["username"] == "admin"
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded


def test_decode_expired_jwt():
    """Garantiza que un token expirado sea rechazado (Fail-closed)."""
    payload = {"sub": "1", "username": "admin", "role": "ADMIN"}
    token = create_access_token(payload, secret_key=SECRET_KEY, expires_delta=timedelta(seconds=-10))

    decoded = decode_access_token(token, secret_key=SECRET_KEY)
    assert decoded is None


def test_decode_jwt_with_wrong_secret():
    """Garantiza que un token firmado con otra clave sea rechazado."""
    payload = {"sub": "1", "username": "admin", "role": "ADMIN"}
    token = create_access_token(payload, secret_key=SECRET_KEY, expires_delta=timedelta(minutes=15))

    decoded = decode_access_token(token, secret_key="wrong_secret_key_123456789012345678901234567890")
    assert decoded is None


def test_verify_telegram_auth_data_valid():
    """Valida la firma oficial HMAC-SHA256 del widget de Telegram Login."""
    auth_date = int(time.time())
    data = {
        "id": "987654321",
        "first_name": "Juan",
        "username": "juan_trader",
        "auth_date": str(auth_date),
    }

    # Calcular hash esperado según spec de Telegram
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    expected_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()

    data_with_hash = {**data, "hash": expected_hash}
    assert verify_telegram_auth_data(data_with_hash, bot_token=BOT_TOKEN) is True


def test_verify_telegram_auth_data_forged():
    """Garantiza el rechazo de credenciales manipuladas o con hash falso."""
    data = {
        "id": "987654321",
        "first_name": "Juan",
        "username": "juan_trader",
        "auth_date": str(int(time.time())),
        "hash": "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678",
    }
    assert verify_telegram_auth_data(data, bot_token=BOT_TOKEN) is False


def test_verify_telegram_auth_data_expired():
    """Garantiza el rechazo si la fecha de autenticación es mayor a max_age."""
    old_date = int(time.time()) - 100000  # Mayor a 24 horas (86400s)
    data = {
        "id": "987654321",
        "first_name": "Juan",
        "username": "juan_trader",
        "auth_date": str(old_date),
    }
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    valid_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = valid_hash

    assert verify_telegram_auth_data(data, bot_token=BOT_TOKEN, max_age_seconds=86400) is False


def test_verify_telegram_webapp_data_valid():
    """Valida la autenticación de Telegram Mini App (TMA) vía initData."""
    auth_date = int(time.time())
    params = {
        "query_id": "AAHdF6IQAAAAAN0XohD_123",
        "user": '{"id":987654321,"first_name":"Juan","username":"juan_trader"}',
        "auth_date": str(auth_date),
    }
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    init_data = f"auth_date={auth_date}&query_id=AAHdF6IQAAAAAN0XohD_123&user=%7B%22id%22%3A987654321%2C%22first_name%22%3A%22Juan%22%2C%22username%22%3A%22juan_trader%22%7D&hash={h}"

    parsed = verify_telegram_webapp_data(init_data, bot_token=BOT_TOKEN)
    assert parsed is not None
    assert parsed["user"]["id"] == 987654321
    assert parsed["user"]["username"] == "juan_trader"


def test_verify_telegram_webapp_data_forged():
    """Garantiza que initData manipulado retorne None."""
    init_data = "auth_date=1700000000&query_id=fake&hash=0123456789abcdef"
    assert verify_telegram_webapp_data(init_data, bot_token=BOT_TOKEN) is None
