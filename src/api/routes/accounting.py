"""Rutas de API REST para el Sistema Contable P2P y Reconciliación Bancaria (SPEC-017)."""

import calendar
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_trader
from src.data.models import AccountingPeriodBalance, BankVoucher, FiscalPeriodSnapshot, Order, User
from src.data.repositories import (
    BankVoucherRepository,
    JournalEntryRepository,
    OrderRepository,
)
from src.integrations.receipt_ocr import BankReceiptOCR
from src.integrations.statement_importer import (
    MAX_STATEMENT_BYTES,
    BankStatementImporter,
    StatementAction,
    StatementCommitRow,
)
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.pdf_reporter import PDFReporter
from src.reporting.tax_engine import FIFOCostMethod
from src.security.file_guards import (
    MAX_VOUCHER_UPLOAD_BYTES,
    image_to_clean_png_bytes,
    read_upload_bounded,
    sanitize_and_load_image,
    validate_pdf_safety,
)

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


class PeriodConfigResponse(BaseModel):
    period: str
    year: int
    month: int
    source: Literal["saved", "carried_over", "profile_default", "empty"]
    carried_from: str | None = None
    is_closed: bool = False
    is_historical_month: bool = False
    initial_usdt: float = 0.0
    initial_usdt_cost_ves: float = 0.0
    initial_banks: dict[str, float] = Field(default_factory=dict)
    actual_final_usdt: float | None = None
    actual_final_banks: dict[str, float] | None = None
    bcv_day1_rate: float = 0.0
    orders_count_in_period: int = 0


class PeriodConfigUpdateRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    initial_usdt: float = Field(default=0.0, ge=0.0)
    initial_usdt_cost_ves: float = Field(default=0.0, ge=0.0)
    initial_banks: dict[str, float] = Field(default_factory=dict)
    actual_final_usdt: float | None = Field(default=None, ge=0.0)
    actual_final_banks: dict[str, float] | None = Field(default=None)
    mark_closed: bool | None = Field(default=None)


def _prev_year_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _canonicalize_bank_map(raw_map: dict[str, float] | None) -> dict[str, float]:
    from src.core.spread_monitor import SpreadMonitor

    out: dict[str, float] = {}
    if not raw_map:
        return out
    for raw_k, raw_v in raw_map.items():
        canon = SpreadMonitor.canonical_user_bank_name(str(raw_k)) or str(raw_k).strip()
        if canon:
            out[canon] = round(max(0.0, float(raw_v or 0.0)), 2)
    return out


def _get_period_balance_row(db: Session, uid: int | None, period: str) -> AccountingPeriodBalance | None:
    q = db.query(AccountingPeriodBalance).filter(AccountingPeriodBalance.period == period)
    if uid is not None:
        q = q.filter(AccountingPeriodBalance.user_id == uid)
    return q.first()


@router.get("/period-config", response_model=PeriodConfigResponse)
def get_period_config(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query(ge=2020, le=2100)] = 2026,
    month: Annotated[int, Query(ge=1, le=12)] = 11,
) -> PeriodConfigResponse:
    """Retorna apertura y arqueo final por período (YYYY-MM), con arrastre automático desde el mes anterior."""
    from datetime import date as date_cls

    from src.reporting.bcv_history_service import BCVHistoryService

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    period = f"{year}-{month:02d}"
    vet_tz = timezone(timedelta(hours=-4))
    now_vet = datetime.now(vet_tz)
    is_historical = (year, month) < (now_vet.year, now_vet.month)

    bcv_svc = BCVHistoryService(db)
    bcv_day1 = bcv_svc.get_rate_for_date(date_cls(year, month, 1))

    # Contar órdenes completadas del período en hora VET
    _, last_day = calendar.monthrange(year, month)
    start_utc = datetime(year, month, 1, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
    end_utc = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
    orders_q = db.query(Order).filter(
        Order.order_status == "COMPLETED",
        Order.created_at.between(start_utc, end_utc),
    )
    if uid is not None:
        orders_q = orders_q.filter(Order.user_id == uid)
    orders_count = orders_q.count()

    user_prefs = list(getattr(current_user, "preferred_banks", []) or [])
    base_banks: dict[str, float] = {b: 0.0 for b in user_prefs}

    row = _get_period_balance_row(db, uid, period)
    if row is not None:
        banks = {**base_banks, **row.initial_banks}
        return PeriodConfigResponse(
            period=period,
            year=year,
            month=month,
            source="saved",
            carried_from=None,
            is_closed=bool(row.is_closed),
            is_historical_month=is_historical,
            initial_usdt=round(float(row.initial_usdt or 0.0), 4),
            initial_usdt_cost_ves=round(float(row.initial_usdt_cost_ves or 0.0), 2),
            initial_banks=banks,
            actual_final_usdt=round(float(row.actual_final_usdt), 4) if row.actual_final_usdt is not None else None,
            actual_final_banks=row.actual_final_banks,
            bcv_day1_rate=round(float(bcv_day1 or 0.0), 4),
            orders_count_in_period=orders_count,
        )

    # Arrastre automático desde el mes inmediatamente anterior
    prev_y, prev_m = _prev_year_month(year, month)
    prev_period = f"{prev_y}-{prev_m:02d}"
    prev_row = _get_period_balance_row(db, uid, prev_period)
    if prev_row is not None and (prev_row.actual_final_usdt is not None or prev_row.actual_final_banks):
        carried_usdt = round(float(prev_row.actual_final_usdt or 0.0), 4)
        carried_banks = {**base_banks, **(prev_row.actual_final_banks or prev_row.initial_banks)}
        suggested_cost = round(carried_usdt * bcv_day1, 2) if (carried_usdt > 0 and bcv_day1 > 0) else 0.0
        return PeriodConfigResponse(
            period=period,
            year=year,
            month=month,
            source="carried_over",
            carried_from=prev_period,
            is_closed=False,
            is_historical_month=is_historical,
            initial_usdt=carried_usdt,
            initial_usdt_cost_ves=suggested_cost,
            initial_banks=carried_banks,
            actual_final_usdt=None,
            actual_final_banks=None,
            bcv_day1_rate=round(float(bcv_day1 or 0.0), 4),
            orders_count_in_period=orders_count,
        )

    prev_snap_q = db.query(FiscalPeriodSnapshot).filter(FiscalPeriodSnapshot.period == prev_period)
    if uid is not None:
        prev_snap_q = prev_snap_q.filter(FiscalPeriodSnapshot.user_id == uid)
    prev_snap = prev_snap_q.order_by(FiscalPeriodSnapshot.id.desc()).first()
    if prev_snap is not None:
        carried_usdt = round(float(prev_snap.actual_final_balance or 0.0), 4)
        profile_banks = _canonicalize_bank_map(getattr(current_user, "bank_initial_balances", {}) or {})
        suggested_cost = round(carried_usdt * bcv_day1, 2) if (carried_usdt > 0 and bcv_day1 > 0) else 0.0
        return PeriodConfigResponse(
            period=period,
            year=year,
            month=month,
            source="carried_over",
            carried_from=prev_period,
            is_closed=False,
            is_historical_month=is_historical,
            initial_usdt=carried_usdt,
            initial_usdt_cost_ves=suggested_cost,
            initial_banks={**base_banks, **profile_banks},
            actual_final_usdt=None,
            actual_final_banks=None,
            bcv_day1_rate=round(float(bcv_day1 or 0.0), 4),
            orders_count_in_period=orders_count,
        )

    # Mes 1: fallback al perfil de bancos del usuario
    profile_banks = _canonicalize_bank_map(getattr(current_user, "bank_initial_balances", {}) or {})
    merged_banks = {**base_banks, **profile_banks}
    return PeriodConfigResponse(
        period=period,
        year=year,
        month=month,
        source="profile_default" if profile_banks else "empty",
        carried_from=None,
        is_closed=False,
        is_historical_month=is_historical,
        initial_usdt=0.0,
        initial_usdt_cost_ves=0.0,
        initial_banks=merged_banks,
        actual_final_usdt=None,
        actual_final_banks=None,
        bcv_day1_rate=round(float(bcv_day1 or 0.0), 4),
        orders_count_in_period=orders_count,
    )


@router.put("/period-config", response_model=PeriodConfigResponse)
def save_period_config(
    payload: PeriodConfigUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> PeriodConfigResponse:
    """Guarda saldos de apertura y/o arqueo final real aislados para un período YYYY-MM."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    period = f"{payload.year}-{payload.month:02d}"
    clean_init_banks = _canonicalize_bank_map(payload.initial_banks)
    clean_final_banks = (
        _canonicalize_bank_map(payload.actual_final_banks)
        if payload.actual_final_banks is not None
        else None
    )

    row = _get_period_balance_row(db, uid, period)
    if row is None:
        row = AccountingPeriodBalance(
            user_id=uid,
            period=period,
            initial_usdt=round(float(payload.initial_usdt), 4),
            initial_usdt_cost_ves=round(float(payload.initial_usdt_cost_ves), 2),
            initial_banks_json=json.dumps(clean_init_banks, ensure_ascii=False),
            actual_final_usdt=(
                round(float(payload.actual_final_usdt), 4)
                if payload.actual_final_usdt is not None
                else None
            ),
            actual_final_banks_json=(
                json.dumps(clean_final_banks, ensure_ascii=False)
                if clean_final_banks is not None
                else None
            ),
            is_closed=bool(payload.mark_closed) if payload.mark_closed is not None else False,
        )
        db.add(row)
    else:
        row_obj: Any = row
        row_obj.initial_usdt = round(float(payload.initial_usdt), 4)
        row_obj.initial_usdt_cost_ves = round(float(payload.initial_usdt_cost_ves), 2)
        row_obj.initial_banks_json = json.dumps(clean_init_banks, ensure_ascii=False)
        if payload.actual_final_usdt is not None:
            row_obj.actual_final_usdt = round(float(payload.actual_final_usdt), 4)
        if clean_final_banks is not None:
            row_obj.actual_final_banks_json = json.dumps(clean_final_banks, ensure_ascii=False)
        if payload.mark_closed is not None:
            row_obj.is_closed = bool(payload.mark_closed)
    db.commit()

    return get_period_config(year=payload.year, month=payload.month, db=db, current_user=current_user)


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


class StatementPreviewRowResponse(BaseModel):
    row_index: int
    date_vet: str
    reference_number: str
    concept: str
    movement_type: Literal["DEBIT", "CREDIT"]
    amount_ves: float
    bank_fee_ves: float = 0.0
    balance_ves: float | None = None
    balance_ok: bool | None = None
    balance_discrepancy: float = 0.0
    payment_method: str
    suggested_action: StatementAction
    matched_order_number: str | None = None
    matched_order_type: str | None = None
    matched_order_crypto: float | None = None
    matched_order_fiat: float | None = None
    match_confidence: float = 0.0
    notes: str = ""


class StatementAvailableOrderResponse(BaseModel):
    order_number: str
    trade_type: str
    fiat_amount: float
    crypto_amount: float
    date_vet: str


class StatementPreviewResponse(BaseModel):
    bank_name: str
    file_type: str
    extraction_method: str
    detected_columns: list[str]
    needs_column_mapping: bool
    detected_order: str
    opening_balance: float | None = None
    closing_balance: float | None = None
    balance_verified: bool
    balance_mismatch_count: int
    total_rows: int
    p2p_matched_count: int
    bank_fee_count: int
    duplicate_count: int
    unmatched_count: int
    rows: list[StatementPreviewRowResponse]
    warnings: list[str]
    available_orders: list[StatementAvailableOrderResponse] = Field(default_factory=list)


class StatementCommitRowRequest(BaseModel):
    row_index: int
    date_vet: str = Field(..., min_length=8, max_length=20)
    reference_number: str = Field(default="S/R", max_length=50)
    concept: str = Field(default="", max_length=255)
    movement_type: Literal["DEBIT", "CREDIT"]
    amount_ves: float = Field(..., ge=0.0)
    payment_method: str = Field(default="TRANSFERENCIA", max_length=30)
    action: StatementAction
    order_number: str | None = Field(default=None, max_length=50)
    bank_fee_ves: float = Field(default=0.0, ge=0.0)


class StatementCommitRequest(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=100)
    rows: list[StatementCommitRowRequest] = Field(..., max_length=2500)


class StatementCommitResponse(BaseModel):
    status: str
    bank_name: str
    created_vouchers: int
    matched_orders: int
    bank_fees_recorded: int
    internal_transfers_recorded: int
    unmatched_recorded: int
    ignored_rows: int
    journal_entries_created: int
    periods_affected: list[str]



@router.get("/balances/live", response_model=LiveBalanceResponse)
def get_live_balance(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
    initial_usdt: Annotated[float, Query()] = 0.0,
    initial_ves: Annotated[float, Query()] = 0.0,
    bank_balances_json: Annotated[str | None, Query()] = None,
) -> LiveBalanceResponse:
    """Calcula el saldo teórico en tiempo real (Inflow - Outflow) aislado por usuario y desglosado por sus bancos."""
    from src.core.spread_monitor import SpreadMonitor

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    engine = AccountingEngine(db=db, user_id=uid)

    explicit_banks: dict[str, float] = {}
    if isinstance(bank_balances_json, str) and bank_balances_json.strip():
        try:
            parsed = json.loads(bank_balances_json)
            if isinstance(parsed, dict):
                for raw_k, raw_v in parsed.items():
                    canon = SpreadMonitor.canonical_user_bank_name(str(raw_k))
                    if canon:
                        explicit_banks[canon] = round(
                            explicit_banks.get(canon, 0.0) + max(0.0, float(raw_v or 0.0)),
                            2,
                        )
        except (ValueError, TypeError):
            explicit_banks = {}

    if not explicit_banks and current_user is not None:
        user_prefs = getattr(current_user, "preferred_banks", []) or []
        user_bals = getattr(current_user, "bank_initial_balances", {}) or {}
        for b_name in user_prefs:
            canon = SpreadMonitor.canonical_user_bank_name(b_name)
            if canon and canon not in explicit_banks:
                explicit_banks[canon] = 0.0
        for b_name, b_val in user_bals.items():
            canon = SpreadMonitor.canonical_user_bank_name(b_name)
            if canon:
                explicit_banks[canon] = round(float(b_val or 0.0), 2)
        if explicit_banks and initial_ves > 0.0 and sum(explicit_banks.values()) == 0.0:
            first_bank = next(iter(explicit_banks.keys()))
            explicit_banks[first_bank] = round(float(initial_ves), 2)

    init_cfg: dict[str, Any] = {
        "crypto_usdt": initial_usdt,
        "total_ves": initial_ves,
    }
    if explicit_banks:
        init_cfg["banks"] = explicit_banks

    summary = engine.get_live_theoretical_balance(
        year=year,
        month=month,
        initial_balances=init_cfg,
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


def _build_accounting_export_context(
    db: Session,
    current_user: User,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Recopila asientos, mayor, comprobantes y resultados fiscales PEPS del período en hora VET (UTC-4)."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    journal_repo = JournalEntryRepository(db, user_id=uid)
    voucher_repo = BankVoucherRepository(db, user_id=uid)
    order_repo = OrderRepository(db, user_id=uid)
    engine = AccountingEngine(db=db, user_id=uid)

    vet_tz = timezone(timedelta(hours=-4))
    _, last_day = calendar.monthrange(year, month)
    start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
    end_dt = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)

    entries = journal_repo.list_entries(start_date=start_dt, end_date=end_dt, user_id=uid)

    period_cfg = get_period_config(year=year, month=month, db=db, current_user=current_user)
    initial_ves = round(sum(float(v or 0.0) for v in period_cfg.initial_banks.values()), 2)
    initial_usdt = round(float(period_cfg.initial_usdt or 0.0), 4)
    initial_usdt_cost_ves = round(float(period_cfg.initial_usdt_cost_ves or 0.0), 2)
    actual_final_usdt = period_cfg.actual_final_usdt
    actual_final_ves = (
        round(sum(float(v or 0.0) for v in period_cfg.actual_final_banks.values()), 2)
        if period_cfg.actual_final_banks is not None
        else None
    )

    ledgers = engine.get_monthly_ledger_report(
        year=year,
        month=month,
        initial_balances={
            engine.ACCOUNT_BANCO_VES: initial_ves,
            engine.ACCOUNT_USDT_ASSET: initial_usdt_cost_ves,
        },
    )

    def _to_vet_ym(dt: datetime | None) -> tuple[int, int] | None:
        if not dt:
            return None
        aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        v = aware.astimezone(vet_tz)
        return (v.year, v.month)

    vouchers = [
        v
        for v in voucher_repo.list_all(user_id=uid)
        if v.voucher_date is None or _to_vet_ym(cast(datetime | None, v.voucher_date)) == (year, month)
    ]

    all_orders = order_repo.list_completed(user_id=uid)
    all_tax_results = FIFOCostMethod().process_orders(all_orders)
    period_orders = [o for o in all_orders if _to_vet_ym(cast(datetime | None, o.created_at)) == (year, month)]
    period_tax_results = [r for r in all_tax_results if _to_vet_ym(r.created_at) == (year, month)]

    bcv_vals = [float(o.bcv_rate) for o in period_orders if float(o.bcv_rate or 0.0) > 0]
    bcv_rate = bcv_vals[-1] if bcv_vals else None
    holder = str(getattr(current_user, "full_name", None) or current_user.username)
    tax_id = str(getattr(current_user, "tax_id", None) or "").strip() or None

    return {
        "entries": entries,
        "ledgers": ledgers,
        "vouchers": vouchers,
        "orders": period_orders,
        "tax_results": period_tax_results,
        "bcv_rate": bcv_rate or (period_cfg.bcv_day1_rate if period_cfg.bcv_day1_rate > 0 else None),
        "account_holder": holder,
        "tax_id": tax_id,
        "period": f"{year}-{month:02d}",
        "initial_usdt": initial_usdt,
        "initial_usdt_cost_ves": initial_usdt_cost_ves,
        "initial_ves": initial_ves,
        "actual_final_usdt": actual_final_usdt,
        "actual_final_ves": actual_final_ves,
    }


@router.get("/export/excel")
def export_accounting_excel(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    year: Annotated[int, Query()] = 2026,
    month: Annotated[int, Query()] = 11,
) -> FileResponse:
    """Exporta el reporte contable integral del operador en 7 pestañas conformes con SENIAT / VEN-NIF 12 (.xlsx)."""
    ctx = _build_accounting_export_context(db, current_user, year, month)
    tmp_dir = tempfile.gettempdir()
    file_path = os.path.join(tmp_dir, f"reporte_contable_p2p_{year}_{month:02d}.xlsx")

    ExcelReporter.generate_accounting_report(
        journal_entries=ctx["entries"],
        ledger_summaries=ctx["ledgers"],
        vouchers=ctx["vouchers"],
        output_path=file_path,
        tax_results=ctx["tax_results"],
        orders=ctx["orders"],
        account_holder=ctx["account_holder"],
        rif=ctx["tax_id"],
        period=ctx["period"],
        bcv_rate=ctx["bcv_rate"],
        initial_usdt=ctx["initial_usdt"],
        initial_usdt_cost_ves=ctx["initial_usdt_cost_ves"],
        initial_ves=ctx["initial_ves"],
        actual_final_usdt=ctx["actual_final_usdt"],
        actual_final_ves=ctx["actual_final_ves"],
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
    """Exporta el informe contable legal multipágina del operador en horario VET (.pdf)."""
    ctx = _build_accounting_export_context(db, current_user, year, month)
    tmp_dir = tempfile.gettempdir()
    file_path = os.path.join(tmp_dir, f"reporte_contable_{year}_{month:02d}.pdf")

    pdf_reporter = PDFReporter(
        company_name=ctx["account_holder"],
        rif=ctx["tax_id"] or "C.I. / RIF no registrado",
    )
    pdf_reporter.generate_accounting_pdf(
        journal_entries=ctx["entries"],
        ledger_summaries=ctx["ledgers"],
        vouchers=ctx["vouchers"],
        output_path=file_path,
        tax_results=ctx["tax_results"],
        orders=ctx["orders"],
        period=ctx["period"],
        initial_usdt=ctx["initial_usdt"],
        initial_usdt_cost_ves=ctx["initial_usdt_cost_ves"],
        initial_ves=ctx["initial_ves"],
        actual_final_usdt=ctx["actual_final_usdt"],
        actual_final_ves=ctx["actual_final_ves"],
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
def upload_voucher(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_trader)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Carga un capture de comprobante bancario, ejecuta OCR multimodal y auto-concilia."""
    content = read_upload_bounded(file, MAX_VOUCHER_UPLOAD_BYTES)

    raw_hint = (file.filename or file.content_type or "").lower()
    is_pdf = raw_hint.endswith(".pdf") or "pdf" in raw_hint or content[:64].lstrip().startswith(b"%PDF-")
    try:
        if is_pdf:
            validate_pdf_safety(content)
            clean_bytes = content
            clean_mime = "application/pdf"
        else:
            clean_img = sanitize_and_load_image(content, file.filename or (file.content_type or ""))
            clean_bytes = image_to_clean_png_bytes(clean_img)
            clean_mime = "image/png"
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    ocr = BankReceiptOCR()
    try:
        voucher, matched_order = ocr.process_and_save_voucher(
            image_bytes=clean_bytes,
            db=db,
            mime_type=clean_mime,
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


@router.post("/statements/preview", response_model=StatementPreviewResponse)
def preview_bank_statement(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
    bank_name: Annotated[str | None, Form()] = None,
    column_mapping_json: Annotated[str | None, Form()] = None,
    year_hint: Annotated[int | None, Form()] = None,
) -> StatementPreviewResponse:
    """Analiza un estado de cuenta bancario (PDF/PNG/JPG/WEBP/XLSX/XLS/CSV/TXT), verifica saldo y sugiere conciliación."""
    content = read_upload_bounded(file, MAX_STATEMENT_BYTES)

    col_map: dict[str, str] | None = None
    if column_mapping_json and column_mapping_json.strip():
        try:
            raw_map = json.loads(column_mapping_json)
            if isinstance(raw_map, dict):
                col_map = {str(k): str(v) for k, v in raw_map.items() if v}
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Formato inválido en mapeo de columnas JSON.",
            ) from exc

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    importer = BankStatementImporter()
    try:
        res = importer.preview_from_bytes(
            file_bytes=content,
            filename=file.filename or "estado_cuenta.pdf",
            db=db,
            user_id=uid,
            bank_name=bank_name,
            column_mapping=col_map,
            year_hint=year_hint,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return StatementPreviewResponse(
        bank_name=res.bank_name,
        file_type=res.file_type,
        extraction_method=res.extraction_method,
        detected_columns=res.detected_columns,
        needs_column_mapping=res.needs_column_mapping,
        detected_order=res.detected_order,
        opening_balance=res.opening_balance,
        closing_balance=res.closing_balance,
        balance_verified=res.balance_verified,
        balance_mismatch_count=res.balance_mismatch_count,
        total_rows=res.total_rows,
        p2p_matched_count=res.p2p_matched_count,
        bank_fee_count=res.bank_fee_count,
        duplicate_count=res.duplicate_count,
        unmatched_count=res.unmatched_count,
        rows=[
            StatementPreviewRowResponse(
                row_index=r.row_index,
                date_vet=r.date_vet,
                reference_number=r.reference_number,
                concept=r.concept,
                movement_type=r.movement_type,
                amount_ves=r.amount_ves,
                bank_fee_ves=r.bank_fee_ves,
                balance_ves=r.balance_ves,
                balance_ok=r.balance_ok,
                balance_discrepancy=r.balance_discrepancy,
                payment_method=r.payment_method,
                suggested_action=r.suggested_action,
                matched_order_number=r.matched_order_number,
                matched_order_type=r.matched_order_type,
                matched_order_crypto=r.matched_order_crypto,
                matched_order_fiat=r.matched_order_fiat,
                match_confidence=r.match_confidence,
                notes=r.notes,
            )
            for r in res.rows
        ],
        warnings=res.warnings,
        available_orders=[StatementAvailableOrderResponse(**o) for o in res.available_orders],
    )


@router.post("/statements/commit", response_model=StatementCommitResponse)
def commit_bank_statement(
    payload: StatementCommitRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_trader)],
) -> StatementCommitResponse:
    """Confirma y asienta en base de datos y Libro Diario las filas aprobadas del estado de cuenta."""
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    importer = BankStatementImporter()
    commit_items = [
        StatementCommitRow(
            row_index=r.row_index,
            date_vet=r.date_vet,
            reference_number=r.reference_number,
            concept=r.concept,
            movement_type=r.movement_type,
            amount_ves=r.amount_ves,
            payment_method=r.payment_method,
            action=r.action,
            order_number=r.order_number,
            bank_fee_ves=r.bank_fee_ves,
        )
        for r in payload.rows
    ]
    res = importer.commit_rows(
        db=db,
        user_id=uid,
        bank_name=payload.bank_name,
        rows=commit_items,
    )
    return StatementCommitResponse(
        status="SUCCESS",
        bank_name=res.bank_name,
        created_vouchers=res.created_vouchers,
        matched_orders=res.matched_orders,
        bank_fees_recorded=res.bank_fees_recorded,
        internal_transfers_recorded=res.internal_transfers_recorded,
        unmatched_recorded=res.unmatched_recorded,
        ignored_rows=res.ignored_rows,
        journal_entries_created=res.journal_entries_created,
        periods_affected=res.periods_affected,
    )
