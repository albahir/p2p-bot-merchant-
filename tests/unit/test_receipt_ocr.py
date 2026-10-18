"""Tests unitarios (TDD) para el servicio BankReceiptOCR con Gemini Vision (SPEC-014)."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import Order
from src.integrations.ai_assistant import AIKeyPool
from src.integrations.receipt_ocr import BankReceiptOCR, ReceiptExtractionResult


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_bank_receipt_ocr_successful_extraction():
    # Mock de pool de claves
    pool = AIKeyPool(["test_key_1", "test_key_2", "test_key_3"])
    ocr = BankReceiptOCR(key_pool=pool)

    mock_llm_json = {
        "bank_name": "Banco de Venezuela",
        "reference_number": "010298765432",
        "amount_ves": 4500.0,
        "sender_cedula": "V-18234567",
        "sender_name": "MANUEL RODRIGUEZ",
        "date_time": "2026-10-16 14:35:10",
        "payment_method": "PAGO_MOVIL",
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
        dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"  # fake jpeg header
        result = ocr.extract_from_image(dummy_img, mime_type="image/jpeg")

        assert result.is_valid is True
        assert result.bank_name == "Banco de Venezuela"
        assert result.reference_number == "010298765432"
        assert result.amount_ves == 4500.0
        assert result.sender_cedula == "V-18234567"
        assert result.payment_method == "PAGO_MOVIL"


def test_bank_receipt_ocr_auto_matching_with_p2p_order():
    ocr = BankReceiptOCR()

    extracted = ReceiptExtractionResult(
        bank_name="Banesco",
        reference_number="0134887766",
        amount_ves=4500.0,
        sender_cedula="V-18234567",
        sender_name="MANUEL RODRIGUEZ",
        date_time="2026-10-16 14:35:10",
        payment_method="PAGO_MOVIL",
        is_valid=True,
    )

    o1 = Order(
        order_number="ORD-MATCH-100",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=4500.0,
        crypto_amount=100.0,
        unit_price=45.0,
        order_status="COMPLETED",
        created_at=datetime.now(UTC),
    )
    o2 = Order(
        order_number="ORD-OTHER-200",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=1200.0,
        crypto_amount=26.66,
        unit_price=45.0,
        order_status="COMPLETED",
        created_at=datetime.now(UTC),
    )

    matched = ocr.match_receipt_with_orders(extracted, [o1, o2], tolerance_ves=0.05)
    assert matched is not None
    assert matched.order_number == "ORD-MATCH-100"


def test_bank_receipt_process_and_save_voucher_to_db():
    db = setup_in_memory_db()
    pool = AIKeyPool(["test_key_1"])
    ocr = BankReceiptOCR(key_pool=pool)

    # Pre-crear orden en BD
    from src.data.repositories import OrderRepository
    ord_repo = OrderRepository(db)
    order = Order(
        order_number="ORD-DB-555",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=2250.0,
        crypto_amount=50.0,
        unit_price=45.0,
        order_status="COMPLETED",
        created_at=datetime.now(UTC),
    )
    ord_repo.create(order)

    mock_llm_json = {
        "bank_name": "Mercantil",
        "reference_number": "0105334455",
        "amount_ves": 2250.0,
        "sender_cedula": "V-20111222",
        "sender_name": "CARLOS PEREZ",
        "date_time": "2026-10-16 16:00:00",
        "payment_method": "TRANSFERENCIA",
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(mock_llm_json)}]}}]
    }

    with patch.object(ocr._client, "post", return_value=mock_resp):
        voucher, matched_ord = ocr.process_and_save_voucher(b"fake_image", db)

        assert voucher.id is not None
        assert voucher.bank_name == "Mercantil"
        assert voucher.amount_ves == 2250.0
        assert voucher.associated_order_number == "ORD-DB-555"
        assert voucher.verification_status == "MATCHED"
        assert matched_ord is not None
        assert matched_ord.order_number == "ORD-DB-555"
