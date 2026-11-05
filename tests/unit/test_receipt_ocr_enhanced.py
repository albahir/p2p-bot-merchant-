"""Tests unitarios (TDD) para el OCR enriquecido de comprobantes bancarios (SPEC-017)."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.integrations.ai_assistant import AIKeyPool
from src.integrations.receipt_ocr import BankReceiptOCR


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ocr_extracts_concept_phone_and_fees():
    pool = AIKeyPool(["test_key_1"])
    ocr = BankReceiptOCR(key_pool=pool)

    mock_llm_json = {
        "bank_name": "Banco de Venezuela",
        "destination_bank": "Banesco",
        "reference_number": "010298765432",
        "amount_ves": 2500.0,
        "bank_fee_ves": 7.5,
        "sender_cedula": "V-19456789",
        "sender_name": "CARLOS PEREZ",
        "sender_phone": "0414-1234567",
        "concept": "Pago orden Binance P2P",
        "date_time": "2026-11-03 14:35:10",
        "payment_method": "PAGO_MOVIL",
        "movement_type": "DEBIT",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f"```json\n{json.dumps(mock_llm_json)}\n```"}]
                }
            }
        ]
    }

    with patch.object(ocr._client, "post", return_value=mock_resp):
        dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
        result = ocr.extract_from_image(dummy_img, mime_type="image/jpeg")

        assert result.is_valid is True
        assert result.destination_bank == "Banesco"
        assert result.concept == "Pago orden Binance P2P"
        assert result.sender_phone == "0414-1234567"
        assert result.bank_fee_ves == 7.5
        assert result.payment_method == "PAGO_MOVIL"


def test_ocr_auto_calculates_interbank_fee_if_missing():
    pool = AIKeyPool(["test_key_1"])
    ocr = BankReceiptOCR(key_pool=pool)

    # El capture no trajo la comisión explícita (0.0 o null), pero es interbancario (BDV -> Banesco)
    mock_llm_json = {
        "bank_name": "Banco de Venezuela",
        "destination_bank": "Banesco",
        "reference_number": "010298765432",
        "amount_ves": 3000.0,
        "bank_fee_ves": 0.0,
        "sender_cedula": "V-19456789",
        "sender_name": "CARLOS PEREZ",
        "date_time": "2026-11-03 14:35:10",
        "payment_method": "PAGO_MOVIL",
        "movement_type": "DEBIT",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f"```json\n{json.dumps(mock_llm_json)}\n```"}]
                }
            }
        ]
    }

    with patch.object(ocr._client, "post", return_value=mock_resp):
        dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
        result = ocr.extract_from_image(dummy_img, mime_type="image/jpeg")

        # 3000 * 0.30% = 9.00 VES auto-calculado
        assert result.bank_fee_ves == 9.0


def test_ocr_same_bank_has_zero_fee():
    pool = AIKeyPool(["test_key_1"])
    ocr = BankReceiptOCR(key_pool=pool)

    # Mismo banco (Banesco -> Banesco)
    mock_llm_json = {
        "bank_name": "Banesco",
        "destination_bank": "Banesco",
        "reference_number": "010298765432",
        "amount_ves": 4000.0,
        "date_time": "2026-11-03 14:35:10",
        "payment_method": "TRANSFERENCIA",
        "movement_type": "DEBIT",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f"```json\n{json.dumps(mock_llm_json)}\n```"}]
                }
            }
        ]
    }

    with patch.object(ocr._client, "post", return_value=mock_resp):
        dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
        result = ocr.extract_from_image(dummy_img, mime_type="image/jpeg")
        assert result.bank_fee_ves == 0.0


def test_process_and_save_voucher_with_enhanced_fields():
    db = setup_in_memory_db()
    pool = AIKeyPool(["test_key_1"])
    ocr = BankReceiptOCR(key_pool=pool)

    mock_llm_json = {
        "bank_name": "Banco de Venezuela",
        "destination_bank": "Mercantil",
        "reference_number": "0102554433",
        "amount_ves": 1500.0,
        "bank_fee_ves": 4.5,
        "sender_cedula": "V-18234567",
        "sender_name": "ANDRES BELLO",
        "sender_phone": "0412-9988776",
        "concept": "COMPRA CRIPTO VES",
        "date_time": "2026-11-03 16:00:00",
        "payment_method": "PAGO_MOVIL",
        "movement_type": "DEBIT",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f"```json\n{json.dumps(mock_llm_json)}\n```"}]
                }
            }
        ]
    }

    with patch.object(ocr._client, "post", return_value=mock_resp):
        dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
        saved, _ = ocr.process_and_save_voucher(dummy_img, db=db, mime_type="image/jpeg")

        assert saved.id is not None
        assert saved.destination_bank == "Mercantil"
        assert saved.concept == "COMPRA CRIPTO VES"
        assert saved.sender_phone == "0412-9988776"
        assert saved.bank_fee_ves == 4.5
        assert saved.total_debited_ves == 1504.5
