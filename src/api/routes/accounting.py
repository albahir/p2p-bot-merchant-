"""Rutas de API REST para el Sistema Contable P2P y Reconciliación Bancaria (SPEC-017)."""

import calendar
import os
import tempfile
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_trader
from src.data.models import BankVoucher, User
from src.data.repositories import (
    BankVoucherRepository,
    JournalEntryRepository,
    OrderRepository,
)
from src.integrations.receipt_ocr import BankReceiptOCR
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.pdf_reporter import PDFReporter

router = APIRouter(prefix="/api/accounting", tags=["Contabilidad y Libro Diario P2P"])


class JournalEntryResponse(BaseModel):
    id: int | None = None
    entry_number: int
    date_time: str
    account_code: str
    account_name: str
    debit: float
    credit: float
    reference: str
    description: str
    voucher_id: int | None = None
    order_number: str | None = None
    entry_hash: str


class LedgerSummaryResponse(BaseModel):
    account_code: str
    account_name: str
    year: int
    month: int
    initial_balance: float
    total_debit: float
    total_credit: float
    final_balance: float
    entries_count: int


class MatchVoucherRequest(BaseModel):
    order_number: str = Field(..., description="Número de orden P2P a vincular con el comprobante")


class ManualVoucherRequest(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=100, description="Banco origen o receptor")
    destination_bank: str | None = Field(default=None, max_length=100)
    reference_number: str = Field(..., min_length=3, max_length=50, description="Referencia bancaria")
    amount_ves: float = Field(..., gt=0.0, description="Monto en bolívares")
    bank_fee_ves: float | None = Field(default=None, ge=0.0, description="Comisión bancaria opcional")
    movement_type: str = Field(default="DEBIT", pattern="^(DEBIT|CREDIT)$")
    payment_method: str = Field(default="PAGO_MOVIL")
    sender_name: str | None = Field(default=None, max_length=255)
    sender_cedula: str | None = Field(default=None, max_length=20)
    concept: str | None = Field(default=None, max_length=255)
    order_number: str | None = Field(default=None, max_length=50, description="Orden P2P opcional a vincular")


class BankBalanceItemResponse(BaseModel):
    bank_name: str
    initial_ves: float
    inflows_ves: float
    outflows_ves: float
    theoretical_ves: float


class LiveBalanceResponse(BaseModel):
    year: int
    month: int
    initial_usdt: float
    inflow_usdt: float
    outflow_usdt: float
    theoretical_usdt: float
    total_initial_ves: float
    total_inflows_ves: float
    total_outflows_ves: float
    total_theoretical_ves: float
    bank_breakdown: list[BankBalanceItemResponse]



@router.get("/balances/live", response_model=LiveBalanceResponse)
def get_live_balance(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
    initial_usdt: Annotated[float, Query()] = 0.0,
    initial_ves: Annotated[float, Query()] = 0.0,
) -> LiveBalanceResponse:
    """Calcula el saldo teórico en tiempo real (Inflow - Outflow) aislado por usuario."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    engine = AccountingEngine(db=db, user_id=uid)
    summary = engine.get_live_theoretical_balance(
        year=year,
        month=month,
        initial_balances={
            "crypto_usdt": initial_usdt,
            "total_ves": initial_ves,
        },
    )

    return LiveBalanceResponse(
        year=summary.year,
        month=summary.month,
        initial_usdt=summary.initial_usdt,
        inflow_usdt=summary.inflow_usdt,
        outflow_usdt=summary.outflow_usdt,
        theoretical_usdt=summary.theoretical_usdt,
        total_initial_ves=summary.total_initial_ves,
        total_inflows_ves=summary.total_inflows_ves,
        total_outflows_ves=summary.total_outflows_ves,
        total_theoretical_ves=summary.total_theoretical_ves,
        bank_breakdown=[
            BankBalanceItemResponse(
                bank_name=b.bank_name,
                initial_ves=b.initial_ves,
                inflows_ves=b.inflows_ves,
                outflows_ves=b.outflows_ves,
                theoretical_ves=b.theoretical_ves,
            )
            for b in summary.bank_breakdown
        ],
    )


@router.get("/journal", response_model=list[JournalEntryResponse])

def get_journal_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    start_date: Annotated[str | None, Query()] = None,
    end_date: Annotated[str | None, Query()] = None,
    account_code: Annotated[str | None, Query()] = None,
) -> list[JournalEntryResponse]:
    """Consulta cronológica de asientos del Libro Diario del operador con partida doble inmutable."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    repo = JournalEntryRepository(db, user_id=uid)
    dt_start = None
    dt_end = None
    if start_date and isinstance(start_date, str):
        try:
            dt_start = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    if end_date and isinstance(end_date, str):
        try:
            dt_end = datetime.fromisoformat(end_date)
        except ValueError:
            pass

    clean_code = account_code if isinstance(account_code, str) else None
    entries = repo.list_entries(start_date=dt_start, end_date=dt_end, account_code=clean_code, user_id=uid)

    return [
        JournalEntryResponse(
            id=cast(int | None, e.id),
            entry_number=int(cast(int, e.entry_number)),
            date_time=e.date_time.strftime("%Y-%m-%d %H:%M:%S") if e.date_time else "-",
            account_code=str(e.account_code),
            account_name=str(e.account_name),
            debit=float(e.debit),
            credit=float(e.credit),
            reference=str(e.reference),
            description=str(e.description),
            voucher_id=cast(int | None, e.voucher_id),
            order_number=cast(str | None, e.order_number),
            entry_hash=str(e.entry_hash),
        )
        for e in entries
    ]


@router.get("/ledger", response_model=list[LedgerSummaryResponse])
def get_ledger_summaries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
    account_code: Annotated[str | None, Query()] = None,
    initial_balance: Annotated[float, Query()] = 0.0,
) -> list[LedgerSummaryResponse]:
    """Consolida el Libro Mayor mensual por cuenta contable del operador."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    engine = AccountingEngine(db=db, user_id=uid)
    clean_code = account_code if isinstance(account_code, str) else None
    y = int(year) if isinstance(year, int) else 2026
    m = int(month) if isinstance(month, int) else 11
    init_b = float(initial_balance) if isinstance(initial_balance, (int, float)) else 0.0
    if clean_code:
        summary = engine.calculate_ledger_for_account(
            account_code=clean_code,
            year=y,
            month=m,
            initial_balance=init_b,
        )
        return [
            LedgerSummaryResponse(
                account_code=summary.account_code,
                account_name=summary.account_name,
                year=summary.year,
                month=summary.month,
                initial_balance=summary.initial_balance,
                total_debit=summary.total_debit,
                total_credit=summary.total_credit,
                final_balance=summary.final_balance,
                entries_count=summary.entries_count,
            )
        ]

    summaries = engine.get_monthly_ledger_report(year=y, month=m)
    return [
        LedgerSummaryResponse(
            account_code=s.account_code,
            account_name=s.account_name,
            year=s.year,
            month=s.month,
            initial_balance=s.initial_balance,
            total_debit=s.total_debit,
            total_credit=s.total_credit,
            final_balance=s.final_balance,
            entries_count=s.entries_count,
        )
        for s in summaries
    ]


@router.get("/export/excel")
def export_accounting_excel(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
) -> FileResponse:
    """Exporta el reporte contable integral del operador en 4 pestañas (.xlsx)."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    journal_repo = JournalEntryRepository(db, user_id=uid)
    voucher_repo = BankVoucherRepository(db, user_id=uid)
    engine = AccountingEngine(db=db, user_id=uid)

    _, last_day = calendar.monthrange(year, month)
    start_dt = datetime(year, month, 1, 0, 0, 0)
    end_dt = datetime(year, month, last_day, 23, 59, 59, 999999)

    entries = journal_repo.list_entries(start_date=start_dt, end_date=end_dt, user_id=uid)
    ledgers = engine.get_monthly_ledger_report(year=year, month=month)
    vouchers = [
        v
        for v in voucher_repo.list_all(user_id=uid)
        if v.voucher_date is None
        or (v.voucher_date.year == year and v.voucher_date.month == month)
    ]

    tmp_dir = tempfile.gettempdir()
    file_path = os.path.join(tmp_dir, f"reporte_contable_p2p_{year}_{month:02d}.xlsx")

    ExcelReporter.generate_accounting_report(
        journal_entries=entries,
        ledger_summaries=ledgers,
        vouchers=vouchers,
        output_path=file_path,
    )

    return FileResponse(
        path=file_path,
        filename=f"reporte_contable_p2p_{year}_{month:02d}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/export/pdf")
def export_accounting_pdf(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
) -> FileResponse:
    """Exporta el informe contable legal del operador listo para impresión fiscal SENIAT (.pdf)."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    journal_repo = JournalEntryRepository(db, user_id=uid)
    voucher_repo = BankVoucherRepository(db, user_id=uid)
    engine = AccountingEngine(db=db, user_id=uid)

    _, last_day = calendar.monthrange(year, month)
    start_dt = datetime(year, month, 1, 0, 0, 0)
    end_dt = datetime(year, month, last_day, 23, 59, 59, 999999)

    entries = journal_repo.list_entries(start_date=start_dt, end_date=end_dt, user_id=uid)
    ledgers = engine.get_monthly_ledger_report(year=year, month=month)
    vouchers = [
        v
        for v in voucher_repo.list_all(user_id=uid)
        if v.voucher_date is None
        or (v.voucher_date.year == year and v.voucher_date.month == month)
    ]

    tmp_dir = tempfile.gettempdir()
    file_path = os.path.join(tmp_dir, f"reporte_contable_{year}_{month:02d}.pdf")

    pdf_reporter = PDFReporter()
    pdf_reporter.generate_accounting_pdf(
        journal_entries=entries,
        ledger_summaries=ledgers,
        vouchers=vouchers,
        output_path=file_path,
    )

    return FileResponse(
        path=file_path,
        filename=f"reporte_contable_{year}_{month:02d}.pdf",
        media_type="application/pdf",
    )


@router.post("/vouchers/{voucher_id}/match")
def match_voucher_with_order(
    voucher_id: int,
    payload: MatchVoucherRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> dict[str, Any]:
    """Vincula manualmente un comprobante con una orden y genera los asientos de partida doble."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    voucher_repo = BankVoucherRepository(db, user_id=uid)
    order_repo = OrderRepository(db, user_id=uid)
    acct_engine = AccountingEngine(db=db, user_id=uid)

    voucher = voucher_repo.get_by_id(voucher_id, user_id=uid)
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comprobante con ID {voucher_id} no encontrado.",
        )

    order = order_repo.get_by_order_number(payload.order_number, user_id=uid)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden P2P '{payload.order_number}' no encontrada.",
        )

    # Actualizar comprobante
    voucher.associated_order_number = order.order_number  # type: ignore[assignment]
    voucher.verification_status = "MATCHED"  # type: ignore[assignment]
    voucher_repo.update(voucher)

    # Registrar partida doble contable
    entries = acct_engine.record_p2p_trade(order=order, voucher=voucher)

    return {
        "voucher_id": voucher.id,
        "status": voucher.verification_status,
        "associated_order_number": voucher.associated_order_number,
        "journal_entries_created": len(entries),
        "message": "Comprobante vinculado y asientos contables asentados exitosamente.",
    }


@router.post("/vouchers/reconcile-orphans")
def reconcile_orphan_vouchers_endpoint(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    tolerance_hours: Annotated[int, Query()] = 48,
) -> dict[str, Any]:
    """Auto-concilia en lote comprobantes rezagados o huérfanos con órdenes de Binance del operador."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    ocr = BankReceiptOCR()
    count = ocr.reconcile_orphan_vouchers(db=db, tolerance_hours=tolerance_hours, user_id=uid)
    return {
        "status": "SUCCESS",
        "reconciled_count": count,
        "message": f"Se auto-conciliaron {count} comprobantes huérfanos exitosamente.",
    }


@router.post("/vouchers/manual")
def create_manual_voucher(
    payload: ManualVoucherRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> dict[str, Any]:
    """Registra y concilia de forma manual ultrarrápida (<5s sin OCR) un comprobante bancario."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    voucher_repo = BankVoucherRepository(db, user_id=uid)
    order_repo = OrderRepository(db, user_id=uid)
    acct_engine = AccountingEngine(db=db, user_id=uid)

    mov_type = payload.movement_type.strip().upper()
    pay_method = payload.payment_method.strip().upper() or "PAGO_MOVIL"
    amount = round(float(payload.amount_ves), 2)

    if payload.bank_fee_ves is not None:
        fee_ves = round(float(payload.bank_fee_ves), 2)
    elif mov_type == "DEBIT" and (
        pay_method == "PAGO_MOVIL"
        or (payload.destination_bank and payload.destination_bank.strip().lower() != payload.bank_name.strip().lower())
    ):
        fee_ves = round(amount * 0.003, 2)
    else:
        fee_ves = 0.0

    total_debited = round(amount + fee_ves, 2) if mov_type == "DEBIT" else amount

    matched_order = None
    if payload.order_number and payload.order_number.strip():
        matched_order = order_repo.get_by_order_number(payload.order_number.strip(), user_id=uid)
    else:
        already_matched: set[str] = {
            str(v.associated_order_number)
            for v in voucher_repo.list_all(user_id=uid)
            if v.associated_order_number
        }
        for cand in order_repo.list_completed(user_id=uid):
            if str(cand.order_number) not in already_matched and abs(float(cand.fiat_amount) - amount) <= 0.05:
                matched_order = cand
                break

    voucher = BankVoucher(
        user_id=uid,
        bank_name=payload.bank_name.strip()[:100],
        destination_bank=payload.destination_bank.strip()[:100] if payload.destination_bank else None,
        reference_number=payload.reference_number.strip()[:50],
        amount_ves=amount,
        bank_fee_ves=fee_ves,
        total_debited_ves=total_debited,
        sender_id=payload.sender_cedula.strip()[:20] if payload.sender_cedula else None,
        sender_name=payload.sender_name.strip()[:255] if payload.sender_name else None,
        concept=payload.concept.strip()[:255] if payload.concept else "Registro manual rápido",
        payment_method=pay_method[:30],
        movement_type=mov_type[:20],
        associated_order_number=matched_order.order_number if matched_order else None,
        verification_status="MATCHED" if matched_order else "UNMATCHED",
        reconciliation_score=100.0 if matched_order else 0.0,
        voucher_date=datetime.now(UTC),
    )
    saved_voucher = voucher_repo.create(voucher)

    if matched_order:
        entries = acct_engine.record_p2p_trade(order=matched_order, voucher=saved_voucher)
    else:
        entries = acct_engine.record_unmatched_voucher(voucher=saved_voucher)

    return {
        "voucher_id": saved_voucher.id,
        "bank_name": saved_voucher.bank_name,
        "reference_number": saved_voucher.reference_number,
        "amount_ves": saved_voucher.amount_ves,
        "bank_fee_ves": saved_voucher.bank_fee_ves,
        "payment_method": saved_voucher.payment_method,
        "verification_status": saved_voucher.verification_status,
        "matched_order_number": matched_order.order_number if matched_order else None,
        "journal_entries_created": len(entries),
    }


@router.post("/vouchers/upload")

async def upload_voucher(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_trader)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Carga un capture de comprobante bancario, ejecuta OCR multimodal y auto-concilia."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo de comprobante vacío.",
        )

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    ocr = BankReceiptOCR()
    try:
        voucher, matched_order = ocr.process_and_save_voucher(
            image_bytes=content,
            db=db,
            mime_type=file.content_type or "image/jpeg",
            user_id=uid,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Si se auto-concilió al 100%, asentar en el Libro Diario
    if matched_order and voucher.verification_status == "MATCHED":
        engine = AccountingEngine(db=db, user_id=uid)
        engine.record_p2p_trade(order=matched_order, voucher=voucher)


    # Si el usuario tiene una hoja personal de Google Sheets vinculada, registrar la fila
    user_sheet_id = getattr(current_user, "google_sheet_id", None)
    if user_sheet_id:
        try:
            from config.settings import Settings
            from src.api.routes.settings import build_user_sheets_exporter

            app_settings = Settings()
            exporter = build_user_sheets_exporter(current_user, app_settings, db)
            dt_str = voucher.voucher_date.strftime("%Y-%m-%d %H:%M:%S") if voucher.voucher_date else ""
            exporter.append_voucher_entry(
                sheet_id=str(user_sheet_id),
                date_time_str=dt_str,
                bank_name=str(voucher.bank_name),
                reference_number=str(voucher.reference_number),
                amount_ves=float(cast(float, voucher.amount_ves) or 0.0),
                sender_id=str(voucher.sender_id) if voucher.sender_id else None,
                sender_name=str(voucher.sender_name) if voucher.sender_name else None,
                payment_method=str(voucher.payment_method),
                order_number=str(matched_order.order_number) if matched_order and matched_order.order_number else None,
                status=str(voucher.verification_status),
                bank_fee_ves=float(cast(float, voucher.bank_fee_ves) or 0.0),
                concept=str(voucher.concept) if voucher.concept else None,
            )
        except (OSError, ValueError, TypeError, KeyError) as e:
            # Comportamiento fail-safe: no tumbar la subida si Google Sheets falla
            import logging
            logging.getLogger("accounting_route").warning(f"Error sincronizando comprobante a Google Sheet de usuario: {e}")


    return {

        "voucher_id": voucher.id,
        "bank_name": voucher.bank_name,
        "reference_number": voucher.reference_number,
        "amount_ves": voucher.amount_ves,
        "bank_fee_ves": voucher.bank_fee_ves,
        "payment_method": voucher.payment_method,
        "verification_status": voucher.verification_status,
        "matched_order_number": matched_order.order_number if matched_order else None,
    }
