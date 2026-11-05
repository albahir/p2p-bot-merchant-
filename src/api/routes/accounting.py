"""Rutas de API REST para el Sistema Contable P2P y Reconciliación Bancaria (SPEC-017)."""

import os
import tempfile
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_trader
from src.data.models import User
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


@router.get("/journal", response_model=list[JournalEntryResponse])
def get_journal_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    start_date: Annotated[str | None, Query()] = None,
    end_date: Annotated[str | None, Query()] = None,
    account_code: Annotated[str | None, Query()] = None,
) -> list[JournalEntryResponse]:
    """Consulta cronológica de asientos del Libro Diario con partida doble inmutable."""
    repo = JournalEntryRepository(db)
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
    entries = repo.list_entries(start_date=dt_start, end_date=dt_end, account_code=clean_code)

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
    """Consolida el Libro Mayor mensual por cuenta contable."""
    engine = AccountingEngine(db=db)
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
    """Exporta el reporte contable integral en 4 pestañas (.xlsx)."""
    journal_repo = JournalEntryRepository(db)
    voucher_repo = BankVoucherRepository(db)
    engine = AccountingEngine(db=db)

    entries = journal_repo.list_entries()
    ledgers = engine.get_monthly_ledger_report(year=year, month=month)
    vouchers = voucher_repo.list_all()

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
    """Exporta el informe contable legal listo para impresión fiscal SENIAT (.pdf)."""
    journal_repo = JournalEntryRepository(db)
    voucher_repo = BankVoucherRepository(db)
    engine = AccountingEngine(db=db)

    entries = journal_repo.list_entries()
    ledgers = engine.get_monthly_ledger_report(year=year, month=month)
    vouchers = voucher_repo.list_all()

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
    voucher_repo = BankVoucherRepository(db)
    order_repo = OrderRepository(db)
    acct_engine = AccountingEngine(db=db)

    voucher = voucher_repo.get_by_id(voucher_id)
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comprobante con ID {voucher_id} no encontrado.",
        )

    order = order_repo.get_by_order_number(payload.order_number)
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

    ocr = BankReceiptOCR()
    voucher, matched_order = ocr.process_and_save_voucher(
        image_bytes=content,
        db=db,
        mime_type=file.content_type or "image/jpeg",
    )

    # Si se auto-concilió al 100%, asentar en el Libro Diario
    if matched_order and voucher.verification_status == "MATCHED":
        engine = AccountingEngine(db=db)
        engine.record_p2p_trade(order=matched_order, voucher=voucher)

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
