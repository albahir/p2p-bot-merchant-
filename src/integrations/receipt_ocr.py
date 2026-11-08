"""Servicio de OCR inteligente para comprobantes bancarios venezolanos (Pago Móvil y Transferencias).
Utiliza Google Gemini Vision multimodal aprovechando el pool de claves API con round-robin.
Extrae referencia, banco, monto en bolívares, cédula del titular y auto-concilia con órdenes P2P.
"""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.models import BankVoucher, Order
from src.data.repositories import BankVoucherRepository, OrderRepository
from src.integrations.ai_assistant import AIKeyPool

logger = logging.getLogger("bank_receipt_ocr")

OCR_SYSTEM_PROMPT = """Eres un asistente contable especializado en procesar comprobantes bancarios en Venezuela (Pago Móvil y Transferencias de Banco de Venezuela, Banesco, Mercantil, Provincial, Bancamiga, BNC, etc.).
Analiza la imagen adjunta y extrae la información en un formato JSON estricto con las siguientes claves:
{
  "bank_name": "Nombre oficial del banco emisor u origen (ej. Banco de Venezuela, Banesco, Mercantil)",
  "destination_bank": "Nombre oficial del banco destino si aparece (ej. Banesco, Banco de Venezuela)",
  "reference_number": "Número de referencia bancaria o número de confirmación",
  "amount_ves": 0.0,
  "bank_fee_ves": 0.0,
  "sender_cedula": "Cédula o RIF del emisor si aparece (ej. V-12345678 o V12345678)",
  "sender_name": "Nombre del emisor o titular si aparece",
  "sender_phone": "Teléfono del emisor o receptor si aparece (ej. 0414-1234567)",
  "concept": "Concepto, motivo o descripción de la transferencia o pago móvil",
  "date_time": "Fecha y hora del pago (ej. YYYY-MM-DD HH:MM:SS)",
  "payment_method": "PAGO_MOVIL o TRANSFERENCIA",
  "movement_type": "DEBIT (si es envío/débito) o CREDIT (si es recepción/crédito)"
}
Si algún dato no aparece claramente en el comprobante, déjalo como null o cadena vacía. Solo responde con el bloque JSON."""


@dataclass
class ReceiptExtractionResult:
    bank_name: str
    reference_number: str
    amount_ves: float
    sender_cedula: str | None = None
    sender_name: str | None = None
    date_time: str | None = None
    payment_method: str = "PAGO_MOVIL"
    destination_bank: str | None = None
    sender_phone: str | None = None
    concept: str | None = None
    bank_fee_ves: float = 0.0
    movement_type: str = "DEBIT"
    raw_text: str | None = None
    is_valid: bool = False
    error_message: str | None = None


class BankReceiptOCR:
    """Extractor multimodal con Gemini Vision y conciliador bancario automático."""

    GEMINI_MODELS: ClassVar[tuple[str, ...]] = (
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-flash-lite-latest",
    )

    def __init__(
        self,
        key_pool: AIKeyPool | None = None,
        http_client: httpx.Client | None = None,
    ):
        if key_pool is None:
            raw_keys = os.getenv("AI_API_KEYS") or os.getenv("AI_API_KEY") or ""
            keys = [k.strip() for k in re.split(r"[,;]", raw_keys) if k.strip()]
            self.key_pool = AIKeyPool(keys or ["dummy_key"])
        else:
            self.key_pool = key_pool

        self._client = http_client or httpx.Client(timeout=15.0)

    def extract_from_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> ReceiptExtractionResult:
        """Envía la imagen a Gemini Vision multimodal y procesa la respuesta estructurada."""
        if not image_bytes:
            return ReceiptExtractionResult(
                bank_name="",
                reference_number="",
                amount_ves=0.0,
                is_valid=False,
                error_message="Búfer de imagen vacío.",
            )

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        total_keys = len(self.key_pool.keys)

        for _ in range(max(1, total_keys)):
            active_key = self.key_pool.get_active_key()
            if not active_key or active_key == "dummy_key":
                break

            for model in self.GEMINI_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={active_key}"
                payload: dict[str, Any] = {
                    "contents": [
                        {
                            "parts": [
                                {"text": OCR_SYSTEM_PROMPT},
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": encoded_image,
                                    }
                                },
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "response_mime_type": "application/json",
                    },
                }

                try:
                    resp = self._client.post(url, json=payload)
                    if resp.status_code == 200:
                        self.key_pool.record_success(active_key)
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            # Limpiar bloques markdown si existen
                            clean_json_str = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
                            parsed = json.loads(clean_json_str)

                            amount_raw = parsed.get("amount_ves")
                            amount_ves = float(amount_raw) if amount_raw is not None else 0.0
                            ref_num = str(parsed.get("reference_number") or "").strip()
                            bank_name = str(parsed.get("bank_name") or "Banco Desconocido").strip()
                            dest_bank_raw = parsed.get("destination_bank")
                            destination_bank = str(dest_bank_raw).strip() if dest_bank_raw else None
                            concept = str(parsed.get("concept") or "").strip() or None
                            phone_raw = parsed.get("sender_phone") or parsed.get("phone_number")
                            sender_phone = str(phone_raw).strip() if phone_raw else None
                            payment_method = str(parsed.get("payment_method") or "PAGO_MOVIL").upper()
                            movement_type = str(parsed.get("movement_type") or "DEBIT").upper()

                            fee_raw = parsed.get("bank_fee_ves")
                            bank_fee = float(fee_raw) if fee_raw is not None else 0.0

                            if bank_fee <= 0.0 and movement_type == "DEBIT" and amount_ves > 0:
                                if destination_bank and destination_bank.lower() != bank_name.lower():
                                    bank_fee = round(amount_ves * 0.003, 2)
                                else:
                                    bank_fee = 0.0
                            elif movement_type == "CREDIT":
                                bank_fee = 0.0

                            return ReceiptExtractionResult(
                                bank_name=bank_name,
                                reference_number=ref_num,
                                amount_ves=amount_ves,
                                sender_cedula=parsed.get("sender_cedula"),
                                sender_name=parsed.get("sender_name"),
                                date_time=parsed.get("date_time"),
                                payment_method=payment_method,
                                destination_bank=destination_bank,
                                sender_phone=sender_phone,
                                concept=concept,
                                bank_fee_ves=bank_fee,
                                movement_type=movement_type,
                                raw_text=raw_text,
                                is_valid=bool(ref_num and amount_ves > 0),
                            )

                    elif resp.status_code in (429, 403, 503):
                        logger.warning(f"Error {resp.status_code} en Gemini Vision con clave actual. Rotando.")
                        self.key_pool.mark_rate_limited(active_key, cooldown_seconds=60.0)
                        break
                except (httpx.RequestError, json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Excepción procesando OCR con modelo {model}: {e}")
                    continue

        return ReceiptExtractionResult(
            bank_name="",
            reference_number="",
            amount_ves=0.0,
            is_valid=False,
            error_message="No se pudo procesar el comprobante con la API de Vision.",
        )

    def match_receipt_with_orders(
        self,
        receipt: ReceiptExtractionResult,
        orders: list[Order],
        tolerance_ves: float = 0.05,
    ) -> Order | None:
        """Busca una orden P2P que coincida en monto en bolívares y contraparte."""
        if not receipt.is_valid or receipt.amount_ves <= 0:
            return None

        candidates: list[Order] = []
        for ord_item in orders:
            diff = abs(float(ord_item.fiat_amount) - receipt.amount_ves)
            if diff <= tolerance_ves:
                candidates.append(ord_item)

        if not candidates:
            return None

        # Si hay más de un candidato por monto, desempatar por nombre de contraparte o cédula
        if len(candidates) > 1:
            if receipt.sender_name:
                sender_words = [w.lower() for w in re.split(r"\s+", receipt.sender_name) if len(w) > 2]
                for cand in candidates:
                    if cand.counterparty_name:
                        cand_lower = cand.counterparty_name.lower()
                        if any(w in cand_lower for w in sender_words):
                            return cand

            if receipt.sender_cedula:
                clean_cedula = re.sub(r"\D", "", receipt.sender_cedula)
                for cand in candidates:
                    if clean_cedula in str(cand.order_number) or (cand.counterparty_name and clean_cedula in cand.counterparty_name):
                        return cand

        # Retornar el primer candidato compatible
        return candidates[0]


    def process_and_save_voucher(
        self,
        image_bytes: bytes,
        db: Session,
        mime_type: str = "image/jpeg",
    ) -> tuple[BankVoucher, Order | None]:
        """Extrae los datos por OCR, persiste el comprobante y auto-concilia con órdenes P2P."""
        extracted = self.extract_from_image(image_bytes, mime_type=mime_type)
        if not extracted.is_valid or float(extracted.amount_ves or 0.0) <= 0.0:
            raise ValueError(
                extracted.error_message
                or "No se pudo extraer un comprobante bancario válido con monto mayor a cero (Fail-closed)."
            )

        voucher_repo = BankVoucherRepository(db)
        order_repo = OrderRepository(db)

        # Excluir órdenes ya conciliadas con otro comprobante para evitar doble imputación
        already_matched: set[str] = {
            str(v.associated_order_number)
            for v in voucher_repo.list_all()
            if v.associated_order_number
        }
        orders = [o for o in order_repo.list_completed() if str(o.order_number) not in already_matched]
        matched_order = self.match_receipt_with_orders(extracted, orders)

        voucher_date = None
        if extracted.date_time:
            try:
                voucher_date = datetime.strptime(extracted.date_time[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            except ValueError:
                voucher_date = datetime.now(UTC)

        total_debited = (
            round(extracted.amount_ves + extracted.bank_fee_ves, 2)
            if extracted.movement_type == "DEBIT"
            else extracted.amount_ves
        )

        voucher = BankVoucher(
            bank_name=(extracted.bank_name or "Banco Desconocido")[:100],
            destination_bank=extracted.destination_bank[:100] if extracted.destination_bank else None,
            reference_number=(extracted.reference_number or f"REF-{int(datetime.now(UTC).timestamp())}")[:50],
            amount_ves=extracted.amount_ves,
            bank_fee_ves=extracted.bank_fee_ves,
            total_debited_ves=total_debited,
            sender_id=extracted.sender_cedula[:20] if extracted.sender_cedula else None,
            sender_name=extracted.sender_name[:255] if extracted.sender_name else None,
            sender_phone=extracted.sender_phone[:30] if extracted.sender_phone else None,
            concept=extracted.concept[:255] if extracted.concept else None,
            payment_method=(extracted.payment_method or "PAGO_MOVIL")[:30],
            movement_type=(extracted.movement_type or "DEBIT")[:20],
            associated_order_number=matched_order.order_number if matched_order else None,
            verification_status="MATCHED" if matched_order else "UNMATCHED",
            voucher_date=voucher_date or datetime.now(UTC),
        )

        saved_voucher = voucher_repo.create(voucher)

        # Auto-alimentar la base de datos de identidades con el titular verificado por el banco
        if extracted.sender_cedula and extracted.sender_name:
            try:
                from src.security.identity_service import IdentityService

                id_service = IdentityService(db=db)
                clean_cedula = re.sub(r"\D", "", extracted.sender_cedula)
                nat = "E" if extracted.sender_cedula.strip().upper().startswith("E") else "V"
                if clean_cedula and len(clean_cedula) >= 5:
                    id_service.save_to_cache(
                        nationality=nat,
                        cedula=clean_cedula,
                        full_name=extracted.sender_name,
                        source="BANK_RECEIPT_OCR",
                    )
            except (SQLAlchemyError, ValueError, KeyError) as e:
                logger.warning(f"No se pudo persistir identidad desde comprobante OCR: {e}")


        return saved_voucher, matched_order

    def reconcile_orphan_vouchers(
        self,
        db: Session,
        tolerance_hours: int = 48,
    ) -> int:
        """Busca comprobantes UNMATCHED y los empareja con órdenes existentes dentro de una ventana temporal."""
        voucher_repo = BankVoucherRepository(db)
        order_repo = OrderRepository(db)

        unmatched_vouchers = (
            db.query(BankVoucher)
            .filter(
                BankVoucher.verification_status == "UNMATCHED",
                BankVoucher.associated_order_number.is_(None),
            )
            .all()
        )

        if not unmatched_vouchers:
            return 0

        # Obtener todas las órdenes completadas aún no vinculadas
        already_matched: set[str] = {
            str(v.associated_order_number)
            for v in voucher_repo.list_all()
            if v.associated_order_number
        }
        completed_orders = [o for o in order_repo.list_completed() if str(o.order_number) not in already_matched]
        reconciled_count = 0

        from src.reporting.accounting_engine import AccountingEngine

        acct_engine = AccountingEngine(db=db)

        def _to_naive_utc(dt_val: datetime) -> datetime:
            return dt_val.astimezone(UTC).replace(tzinfo=None) if dt_val.tzinfo is not None else dt_val

        for v in unmatched_vouchers:
            v_date = _to_naive_utc(v.voucher_date or datetime.now(UTC))
            for o in completed_orders:
                if str(o.order_number) in already_matched:
                    continue
                # Comprobar monto idéntico en VES
                if abs(float(o.fiat_amount) - float(v.amount_ves)) < 0.05:
                    # Comprobar ventana de tiempo si la orden tiene fecha
                    if o.created_at:
                        o_date = _to_naive_utc(o.created_at)
                        diff = abs((v_date - o_date).total_seconds())
                        if diff > (tolerance_hours * 3600):
                            continue

                    # Conciliado
                    v.associated_order_number = o.order_number  # type: ignore[assignment]
                    v.verification_status = "MATCHED"  # type: ignore[assignment]
                    voucher_repo.update(v)
                    already_matched.add(str(o.order_number))

                    # Registrar en el Libro Diario formal
                    try:
                        acct_engine.record_p2p_trade(order=o, voucher=v)
                    except (SQLAlchemyError, ValueError, TypeError, KeyError) as e:
                        logger.warning(f"Error generando asiento contable al auto-conciliar huérfano: {e}")


                    reconciled_count += 1
                    break

        return reconciled_count




def process_and_save_voucher(
    image_bytes: bytes,
    db: Session,
    ocr_service: BankReceiptOCR | None = None,
    mime_type: str = "image/jpeg",
) -> tuple[BankVoucher, Order | None]:
    """Función helper para procesar un comprobante y guardarlo directamente en base de datos."""
    service = ocr_service or BankReceiptOCR()
    return service.process_and_save_voucher(image_bytes, db, mime_type=mime_type)

