"""Tests unitarios para Spec 010 (Resiliencia de API, Pydantic schemas, concurrencia y validación PEM)."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.binance_schemas import BinanceOrderHistoryResponse, OrderStatusEnum, TradeTypeEnum
from src.core.concurrency import SyncLockManager
from src.security.key_validator import KeyValidationError, KeyValidator


def test_binance_pydantic_schema_parsing():
    raw_response = {
        "code": "000000",
        "message": "success",
        "success": True,
        "total": 1,
        "data": [
            {
                "orderNumber": "20219644646554779648",
                "advNo": "11218246497340923904",
                "tradeType": "BUY",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "100.50000000",
                "totalPrice": "3680.00000000",
                "unitPrice": "36.6169",
                "orderStatus": "COMPLETED",
                "createTime": 1700000000000,
                "advertisementRole": "TAKER",
                "takerCommission": "0.15",
                "commission": "0"
            }
        ]
    }
    parsed = BinanceOrderHistoryResponse.model_validate(raw_response)
    assert parsed.code == "000000"
    assert len(parsed.data) == 1
    item = parsed.data[0]
    assert item.orderStatus == OrderStatusEnum.COMPLETED
    assert item.tradeType == TradeTypeEnum.BUY
    assert float(item.amount_decimal) == 100.5
    assert float(item.fee_decimal) == 0.15


def test_sync_lock_prevents_concurrent_execution():
    lock_mgr = SyncLockManager()
    # Adquirir primer bloqueo
    acquired_first = lock_mgr.acquire(task_name="test_sync")
    assert acquired_first is True
    assert lock_mgr.is_locked is True

    # Intentar adquirir segundo bloqueo mientras está activo
    acquired_second = lock_mgr.acquire(task_name="concurrent_sync")
    assert acquired_second is False

    # Liberar y reintentar
    lock_mgr.release()
    assert lock_mgr.is_locked is False
    assert lock_mgr.acquire(task_name="new_sync") is True
    lock_mgr.release()


def test_key_validator_rejects_corrupted_pem():
    with pytest.raises(KeyValidationError, match="Formato de clave inválido"):
        KeyValidator.validate_private_key_pem("not_a_valid_pem_string")

    with pytest.raises(KeyValidationError, match="Formato corrupto"):
        KeyValidator.validate_private_key_pem(
            "-----BEGIN PRIVATE KEY-----\nCORRUPTED_BASE64_PAYLOAD\n-----END PRIVATE KEY-----"
        )


def test_key_validator_accepts_valid_ed25519_pem():
    # Generar clave Ed25519 válida en memoria
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pem_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pem_str = pem_bytes.decode("utf-8")

    validated = KeyValidator.validate_private_key_pem(pem_str)
    assert validated == pem_str.strip()


def test_key_validator_accepts_hmac_secret():
    secret_hex = "f" * 64
    validated = KeyValidator.validate_secret_key(secret_hex)
    assert validated == secret_hex

    with pytest.raises(KeyValidationError, match="demasiado corta"):
        KeyValidator.validate_secret_key("short")
