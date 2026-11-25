"""Importador Universal de Estados de Cuenta Bancarios (PDF, Excel, CSV, TXT) — SPEC-024.

Diseñado de forma agnóstica al banco para operar con cualquier entidad financiera venezolana
(Banesco, BDV, Mercantil, Provincial, Bancamiga, BNC, Exterior, Tesoro, Banplus, etc.)
o internacional, combinando extracción tabular local, alineación espacial PDF (pypdf layout),
verificación matemática Fail-Closed de saldo acumulado, deduplicación, cruce horario VET (UTC-4)
y respaldo opcional con IA multimodal para PDFs escaneados.
"""

from __future__ import annotations

import base64
import copy
import csv
import gc
import io
import json
import logging
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Literal, cast

import httpx
import pandas as pd
import pdfplumber
from fastapi import HTTPException, status
from pdfplumber.utils.exceptions import PdfminerException
from PIL import Image, ImageFilter, ImageOps
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from sqlalchemy.orm import Session

from src.data.models import BankVoucher, FiscalPeriodSnapshot, Order
from src.data.repositories import BankVoucherRepository, OrderRepository, _apply_user_scope
from src.integrations.ai_assistant import AIKeyPool
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.normalizers import (
    detect_bank_from_text,
    normalize_bank_name,
    normalize_reference,
    normalize_text,
    parse_monetary_amount,
)
from src.security.file_guards import (
    MAX_OCR_IMAGE_PIXELS,
    MAX_STATEMENT_UPLOAD_BYTES,
    assert_not_executable_payload,
    build_clean_ocr_env,
    compute_safe_pdf_render_scale,
    image_to_clean_png_bytes,
    parse_html_table_rows,
    sanitize_and_load_image,
    validate_image_magic_bytes,
    validate_pdf_safety,
    validate_xls_safety,
    validate_xlsx_zip_safety,
)

logger = logging.getLogger("statement_importer")

VET_TZ = timezone(timedelta(hours=-4))

MAX_STATEMENT_BYTES = MAX_STATEMENT_UPLOAD_BYTES  # 50 MB anti-DoS para extractos mensuales extensos
MAX_STATEMENT_ROWS = 25000
MAX_PDF_PAGES = 500
PDF_AI_CHUNK_PAGES = 2
_OCR_CONCURRENCY_SEMAPHORE = threading.BoundedSemaphore(2)
MAX_OCR_IMAGE_WIDTH = 3600
MAX_OCR_IMAGE_HEIGHT = 14000
MAX_OCR_IMAGE_DIMENSION = MAX_OCR_IMAGE_HEIGHT
IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")

StatementAction = Literal[
    "P2P_MATCH",
    "P2P_UNMATCHED",
    "BANK_FEE",
    "DUPLICATE_EXISTING",
    "INTERNAL_TRANSFER",
    "IGNORE",
]

_HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "date": (
        "fecha",
        "fec",
        "date",
        "f. valor",
        "f valor",
        "fecha valor",
        "fecha oper",
        "fecha operacion",
        "fecha movimiento",
        "diaoper",
        "dia",
        "tx date",
        "transaction date",
    ),
    "reference": (
        "referencia",
        "ref",
        "nro referencia",
        "numero de referencia",
        "numero",
        "nro. ref",
        "nro.",
        "nro doc",
        "documento",
        "comprobante",
        "serial",
        "operacion",
        "lote",
        "codigotx",
        "codigo tx",
        "trace",
        "nro",
    ),
    "concept": (
        "concepto",
        "descripcion",
        "descripcion movimiento",
        "descripcion de la operacion",
        "detalle",
        "glosa",
        "movimiento",
        "description",
        "narrative",
        "particulars",
        "observacion",
        "motivo",
    ),
    "debit": (
        "debito",
        "debitos",
        "debe",
        "cargo",
        "cargos",
        "retiro",
        "retiros",
        "egreso",
        "egresos",
        "salida",
        "salidas",
        "debit",
        "debits",
        "withdrawal",
    ),
    "credit": (
        "credito",
        "creditos",
        "haber",
        "abono",
        "abonos",
        "deposito",
        "depositos",
        "ingreso",
        "ingresos",
        "entrada",
        "entradas",
        "credit",
        "credits",
        "deposit",
    ),
    "amount": (
        "monto",
        "importe",
        "valor",
        "amount",
        "impconsigno",
        "monto movimiento",
    ),
    "type": (
        "tipo",
        "naturaleza",
        "signo",
        "dc",
        "mov",
        "tipo movimiento",
    ),
    "balance": (
        "saldo",
        "saldos",
        "balance",
        "saldo disponible",
        "saldo contable",
        "saldo final",
        "restofinal",
        "saldo actual",
    ),
}

_BANK_FEE_KEYWORDS: tuple[str, ...] = (
    "COMISION",
    "COM.",
    "COM,",
    "COM ",
    "MANTENIMIENTO",
    "ITF",
    "I.D.B",
    "IDB",
    "IGTF",
    "MENSAJERIA",
    "TARIFA PAGO",
    "CARGO POR SERVICIO",
    "IVA COMISION",
    "PORTES",
    "EMISION EDO",
)
_COMIS_ABBREV_RE = re.compile(r"\bCOMIS[.,]?\b")

_PAGO_MOVIL_KEYWORDS: tuple[str, ...] = (
    "PAGO MOVIL",
    "PAGOMOVIL",
    "T-PAGO",
    "TPAGO",
    "CREDITO INMEDIATO",
    "PAPM",
    "P.NAT",
    "P.JUR",
    "C2P",
    "P2C",
    "P2P MOVIL",
)

_NOISE_LINE_KEYWORDS: tuple[str, ...] = (
    "SALDO ANTERIOR",
    "SALDO MES ANTERIOR",
    "SALDO INICIAL",
    "SALDO AL INICIO",
    "SALDO FINAL",
    "SALDO AL FINAL",
    "SALDO PROMEDIO",
    "SALDO DE CIERRE",
    "TOTAL DEBITOS",
    "TOTAL CREDITOS",
    "TOTAL CARGOS",
    "TOTAL ABONOS",
    "TOTAL TRANSACCIONES",
    "INTERESES PAGADOS",
    "INTERESES COBRADOS",
    "ISLR COBRADOS",
    "IMPUESTOS RETENIDOS",
    "RESUMEN DE MOVIMIENTOS",
    "RESUMEN DE SALDOS",
    "RESUMEN DE CUENTA",
    "RESUMEN ESTADO DE CUENTA",
    "MOVIMIENTOS DE CUENTA",
    "DETALLE DE MOVIMIENTOS",
    "CODIGO CUENTA CLIENTE",
    "PAGINA ",
    "PAGE ",
    "ESTADO DE CUENTA",
    "EL BANCO DE VENEZUELA",
    "BANCO UNIVERSAL CERTIFICA",
    "GOBIERNO BOLIVARIANO",
    "MINISTERIO DEL PODER",
    "BATALLA NAVAL",
)

_MONTH_ES: dict[str, int] = {
    "ENE": 1,
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "AUG": 8,
    "SEP": 9,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
    "DEC": 12,
}

_DATE_START_RE = re.compile(
    r"^\s*(\d{1,2}[\/\.-]\d{1,2}(?:[\/\.-]\d{2,4})?|\d{4}[\/\.-]\d{1,2}[\/\.-]\d{1,2})"
    r"(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?(?=\s|$)"
)

_DATE_ANY_RE = re.compile(
    r"(?<![A-Za-z0-9/.,-])("
    r"\d{4}[\/\.-]\d{1,2}[\/\.-]\d{1,2}"
    r"|\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}"
    r"|\d{1,2}[\/\-]\d{1,2}"
    r"|\d{1,2}[\s\/\-](?:ENE|JAN|FEB|MAR|ABR|APR|MAY|JUN|JUL|AGO|AUG|SEP|SET|OCT|NOV|DIC|DEC)(?:[\s\/\-]\d{2,4})?"
    r")(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?(?![A-Za-z0-9/.,-])",
    re.IGNORECASE,
)

_MOV_FLAG_DEBIT_RE = re.compile(r"^(?:ND|DB|DR|D|DEBITO|CARGO|RETIRO|EGRESO)$", re.IGNORECASE)
_MOV_FLAG_CREDIT_RE = re.compile(r"^(?:NC|CR|C|CREDITO|ABONO|DEPOSITO|INGRESO)$", re.IGNORECASE)

_MONEY_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9/.-])((?:[+-]\s*)?(?:\d{1,3}(?:[.,]\d{3})+|\d+)[.,]\d{2})(?:\s*(CR|DB|DR))?(?![A-Za-z0-9.,])",
    re.IGNORECASE,
)


@dataclass
class ParsedStatementRow:
    row_index: int
    date_vet: str
    voucher_datetime_utc: datetime
    reference_number: str
    concept: str
    movement_type: Literal["DEBIT", "CREDIT"]
    amount_ves: float
    bank_fee_ves: float = 0.0
    balance_ves: float | None = None
    balance_ok: bool | None = None
    balance_discrepancy: float = 0.0
    payment_method: str = "TRANSFERENCIA"
    suggested_action: StatementAction = "P2P_UNMATCHED"
    matched_order_number: str | None = None
    matched_order_type: str | None = None
    matched_order_crypto: float | None = None
    matched_order_fiat: float | None = None
    match_confidence: float = 0.0
    notes: str = ""
    amount_uncertain: bool = False
    counterparty_name: str | None = None
    sender_id: str | None = None
    destination_bank: str | None = None
    tx_time_vet: str | None = None
    source_page_idx: int | None = None


@dataclass
class StatementPreviewResult:
    bank_name: str
    file_type: str
    extraction_method: str
    detected_columns: list[str]
    needs_column_mapping: bool
    detected_order: str
    opening_balance: float | None
    closing_balance: float | None
    balance_verified: bool
    balance_mismatch_count: int
    total_rows: int
    p2p_matched_count: int
    bank_fee_count: int
    duplicate_count: int
    unmatched_count: int
    rows: list[ParsedStatementRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    available_orders: list[dict[str, Any]] = field(default_factory=list)
    cover_summary: dict[str, float | int | None] = field(default_factory=dict)


@dataclass
class StatementCommitRow:
    row_index: int
    date_vet: str
    reference_number: str
    concept: str
    movement_type: Literal["DEBIT", "CREDIT"]
    amount_ves: float
    payment_method: str = "TRANSFERENCIA"
    action: StatementAction = "P2P_UNMATCHED"
    order_number: str | None = None
    bank_fee_ves: float = 0.0


@dataclass
class StatementCommitResult:
    bank_name: str
    created_vouchers: int
    matched_orders: int
    bank_fees_recorded: int
    internal_transfers_recorded: int
    unmatched_recorded: int
    ignored_rows: int
    journal_entries_created: int
    periods_affected: list[str]


def _sanitize_cell_text(raw: Any, max_len: int = 255) -> str:
    """Limpia saltos de línea, caracteres de control y prefijos de fórmulas peligrosas en CSV/Excel."""
    if raw is None:
        return ""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(raw)).strip()
    s = re.sub(r"\s+", " ", s)
    if s.startswith(("=", "+", "-", "@")) and not re.match(r"^[-+]\d", s):
        s = "'" + s
    return s[:max_len]


def _parse_signed_amount(raw_val: Any) -> tuple[float, Literal["DEBIT", "CREDIT"] | None]:
    """Extrae magnitud positiva y signo explícito si viene indicado (+/-/CR/DB)."""
    if raw_val is None:
        return 0.0, None
    if isinstance(raw_val, (int, float)):
        val = float(raw_val)
        if pd.isna(val):
            return 0.0, None
        sign: Literal["DEBIT", "CREDIT"] | None = "DEBIT" if val < 0 else ("CREDIT" if val > 0 else None)
        return round(abs(val), 2), sign

    s = str(raw_val).strip().upper()
    if not s or s in ("NAN", "NONE", "-", "--"):
        return 0.0, None

    explicit_dir: Literal["DEBIT", "CREDIT"] | None = None
    if s.startswith("-") or re.search(r"\b(DB|DR|DEBITO|CARGO|D)\b", s):
        explicit_dir = "DEBIT"
    elif s.startswith("+") or re.search(r"\b(CR|CREDITO|ABONO|C)\b", s):
        explicit_dir = "CREDIT"

    mag = parse_monetary_amount(s)
    return mag, explicit_dir


def _parse_signed_balance(raw_val: Any) -> float:
    """Extrae el saldo contable preservando signo negativo para sobregiros o retenciones."""
    mag, explicit_dir = _parse_signed_amount(raw_val)
    return -mag if explicit_dir == "DEBIT" and mag > 0.0 else mag


_FULL_MONTH_NAMES: dict[str, int] = {
    "ENERO": 1,
    "JANUARY": 1,
    "FEBRERO": 2,
    "FEBRUARY": 2,
    "MARZO": 3,
    "MARCH": 3,
    "ABRIL": 4,
    "APRIL": 4,
    "MAYO": 5,
    "MAY": 5,
    "JUNIO": 6,
    "JUNE": 6,
    "JULIO": 7,
    "JULY": 7,
    "AGOSTO": 8,
    "AUGUST": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "SEPTEMBER": 9,
    "OCTUBRE": 10,
    "OCTOBER": 10,
    "NOVIEMBRE": 11,
    "NOVEMBER": 11,
    "DICIEMBRE": 12,
    "DECEMBER": 12,
}


def _extract_period_year_month(text: str, fallback_year: int) -> tuple[int, int | None]:
    """Infiere (año, mes) del período del documento a partir de formatos MM-YYYY, fechas o meses escritos."""
    upper = normalize_text(text)
    year = fallback_year
    month: int | None = None

    m_my = re.search(
        r"(?:PERIODO|MES|DESDE|DEL|HASTA|AL)?\s*:?\s*(0?[1-9]|1[0-2])[\/\-](20\d{2})\b",
        upper,
    )
    if m_my:
        month = int(m_my.group(1))
        year = int(m_my.group(2))
        return year, month

    for name, m_num in _FULL_MONTH_NAMES.items():
        m_txt = re.search(rf"\b{name}\b(?:\s+DE)?\s+(20\d{{2}})\b", upper)
        if m_txt:
            return int(m_txt.group(1)), m_num

    m_dmy = re.search(r"\b\d{1,2}[\/\-](0?[1-9]|1[0-2])[\/\-](20\d{2})\b", upper)
    if m_dmy:
        month = int(m_dmy.group(1))
        year = int(m_dmy.group(2))
        return year, month

    m_yr = re.search(r"\b(20\d{2})\b", upper)
    if m_yr:
        year = int(m_yr.group(1))
        return year, month

    # Soporte para fechas con año de 2 dígitos (ej. Mercantil portada: 01-10-26 / 31-10-26)
    m_dmy2 = re.search(r"\b(?:0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[0-2])[\/\-](\d{2})\b", upper)
    if m_dmy2:
        month = int(m_dmy2.group(1))
        y2 = int(m_dmy2.group(2))
        year = (2000 + y2) if y2 < 80 else (1900 + y2)
    return year, month


def _parse_flexible_summary_amount(raw: str | None) -> float | None:
    """Parsea montos de resúmenes de portada tolerando comas repetidas (ej. Mercantil 230,379,425,24 o 232.388,079,66)."""
    if not raw:
        return None
    s = re.sub(r"[^0-9,.\-]", "", str(raw).strip())
    if not s or s in ("-", ".", ","):
        return None
    neg = s.startswith("-")
    s = s.lstrip("-")
    m_dec = re.match(r"^([0-9.,]+)[.,](\d{2})$", s)
    if m_dec:
        int_part = re.sub(r"[.,]", "", m_dec.group(1))
        if not int_part:
            return None
        try:
            val = float(f"{int_part}.{m_dec.group(2)}")
            return round(-val if neg else val, 2)
        except ValueError:
            return None
    val = parse_monetary_amount(s)
    return round(-val if neg else val, 2)


def _extract_cover_summary(meta_text: str) -> dict[str, float | int | None]:
    """Extrae saldos y totales declarados en la portada/resumen (Banesco, Mercantil, BDV)."""
    upper = normalize_text(meta_text)
    if not upper:
        return {}
    summary: dict[str, float | int | None] = {}

    m_open = re.search(
        r"(?:SALDO\s+(?:AL\s+)?INICIO(?:\s+DEL\s+PERIODO)?|SALDO\s+INICIAL|SALDO\s+MES\s+ANTERIOR|\bINICIAL\b)\s*:?\s*([+-]?\d[\d.,]*[.,]\d{2})",
        upper,
    )
    if m_open:
        summary["opening_balance"] = _parse_flexible_summary_amount(m_open.group(1))

    m_close = re.search(
        r"(?:SALDO\s+(?:AL\s+)?FINAL(?:\s+DEL\s+PERIODO)?|\bFINAL\b)\s*:?\s*(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s+)?([+-]?\d[\d.,]*[.,]\d{2})",
        upper,
    )
    if m_close:
        summary["closing_balance"] = _parse_flexible_summary_amount(m_close.group(1))

    # Mercantil: "327 OTROS CREDITOS A SU CUENTA 230,379,425,24" | Banesco: "OTROS CREDITOS 648 516.533.772,77"
    m_cred_m = re.search(r"\b(\d+)\s+OTROS\s+CREDITOS(?:\s+A\s+SU\s+CUENTA)?\s+(\d[\d.,]*[.,]\d{2})", upper)
    m_cred_b = re.search(r"OTROS\s+CREDITOS\s+(\d+)\s+(\d[\d.,]*[.,]\d{2})", upper)
    if m_cred_m:
        summary["declared_credits_count"] = int(m_cred_m.group(1))
        summary["declared_credits_total"] = _parse_flexible_summary_amount(m_cred_m.group(2))
    elif m_cred_b:
        summary["declared_credits_count"] = int(m_cred_b.group(1))
        summary["declared_credits_total"] = _parse_flexible_summary_amount(m_cred_b.group(2))

    # Mercantil: "6387 OTROS DEBITOS A SU CUENTA 232.388,079,66" | Banesco: "OTROS DEBITOS 5349 516.516.305,66"
    m_deb_m = re.search(r"\b(\d+)\s+OTROS\s+DEBITOS(?:\s+A\s+SU\s+CUENTA)?\s+(\d[\d.,]*[.,]\d{2})", upper)
    m_deb_b = re.search(r"OTROS\s+DEBITOS\s+(\d+)\s+(\d[\d.,]*[.,]\d{2})", upper)
    if m_deb_m:
        summary["declared_debits_count"] = int(m_deb_m.group(1))
        summary["declared_debits_total"] = _parse_flexible_summary_amount(m_deb_m.group(2))
    elif m_deb_b:
        summary["declared_debits_count"] = int(m_deb_b.group(1))
        summary["declared_debits_total"] = _parse_flexible_summary_amount(m_deb_b.group(2))

    return summary


def _enrich_row_metadata(row: ParsedStatementRow, full_desc: str) -> None:
    """Extrae hora exacta VET, cédula/RIF, beneficiario/contraparte y banco destino desde descripciones ricas (Mercantil/BDV)."""
    upper = normalize_text(full_desc)
    if not upper:
        return

    # 1. Hora exacta VET: "EL 01-10-26 A LAS 19:19:41 HORAS"
    m_time = re.search(r"\bA\s+LAS\s+(\d{1,2}:\d{2}:\d{2})\s+HORAS?\b", upper)
    if m_time:
        t_str = m_time.group(1)
        try:
            hh, mm, ss = (int(p) for p in t_str.split(":"))
            if 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59:
                row.tx_time_vet = f"{hh:02d}:{mm:02d}:{ss:02d}"
                y, m, d = (int(p) for p in row.date_vet.split("-"))
                row.voucher_datetime_utc = datetime(y, m, d, hh, mm, ss, tzinfo=VET_TZ).astimezone(UTC)
        except ValueError:
            pass

    # 2. Cédula o RIF del beneficiario/contraparte (ej. "A V90026775", "V-19456789")
    m_cid = re.search(r"(?<![A-Z0-9])([VEJGP])[\-\s]?(\d{6,10})(?!\d)", upper)
    if m_cid:
        row.sender_id = f"{m_cid.group(1)}-{m_cid.group(2)}"

    # 3. Nombre de contraparte / beneficiario en transferencias Mercantil ("A LA CU ENTA DE JESUS FAJARDO ***8921")
    m_cp = re.search(
        r"(?:A\s+LA|DESDE(?:\s+LA)?)\s+CU\s*ENTA\s+DE\s+([A-Z][A-Z\s]{2,55}?)(?=\s*(?:\*{2,}|\d{3,}|POR\s+BS|REALIZADA|EL\s+\d{2}|$))",
        upper,
    )
    if m_cp:
        cand_name = re.sub(r"\s+", " ", m_cp.group(1)).strip()
        if len(cand_name) >= 3 and cand_name not in ("TERCEROS", "TERCERO"):
            row.counterparty_name = cand_name[:120]

    # 4. Banco destino en T-Pago / Crédito Inmediato ("EN BANCAMIGA BANCO UNIVERSAL", "EN BANCO NACIONAL DE CREDITO")
    m_dbank = re.search(r"\bEN\s+([A-Z0-9\s.,]{3,45}?)(?=\s*(?:POR\s+BS|POR\s+CONCEPTO|EL\s+\d{2}|$))", upper)
    if m_dbank:
        detected_dest = detect_bank_from_text(m_dbank.group(1))
        if detected_dest:
            row.destination_bank = detected_dest


def _parse_vet_date(raw_date: str, default_year: int) -> tuple[str, datetime] | None:
    """Convierte fecha bancaria a fecha VET (YYYY-MM-DD) y datetime UTC equivalente."""
    s = str(raw_date or "").strip()
    if not s:
        return None

    time_part: str | None = None
    m_time = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", s)
    if m_time:
        time_part = m_time.group(1)

    date_only = re.split(r"[\sT]+", s)[0].strip()

    year = default_year
    month = 0
    day = 0

    m_iso = re.match(r"^(\d{4})[\/\.-](\d{1,2})[\/\.-](\d{1,2})$", date_only)
    m_dmy = re.match(r"^(\d{1,2})[\/\.-](\d{1,2})(?:[\/\.-](\d{2,4}))?$", date_only)
    m_txt = re.match(r"^(\d{1,2})[\s\/\-]([A-Za-z]{3})(?:[\s\/\-](\d{2,4}))?$", s.upper())

    if m_iso:
        year = int(m_iso.group(1))
        month = int(m_iso.group(2))
        day = int(m_iso.group(3))
    elif m_dmy:
        day = int(m_dmy.group(1))
        month = int(m_dmy.group(2))
        if month > 12 and 1 <= day <= 12:
            # Tolerancia automática para formato estadounidense MM/DD/YYYY (Payoneer, Mercury, etc.)
            day, month = month, day
        if m_dmy.group(3):
            y_val = int(m_dmy.group(3))
            year = (2000 + y_val) if y_val < 80 else ((1900 + y_val) if y_val < 100 else y_val)
    elif m_txt:
        day = int(m_txt.group(1))
        month = _MONTH_ES.get(m_txt.group(2)[:3], 0)
        if m_txt.group(3):
            y_val = int(m_txt.group(3))
            year = (2000 + y_val) if y_val < 80 else ((1900 + y_val) if y_val < 100 else y_val)
    else:
        return None

    try:
        if time_part:
            parts = [int(p) for p in time_part.split(":")]
            hh, mm = parts[0], parts[1]
            ss = parts[2] if len(parts) > 2 else 0
        else:
            # Mediodía VET (16:00 UTC) preserva el día calendario tanto en UTC-4 como en UTC
            hh, mm, ss = 12, 0, 0
        dt_vet = datetime(year, month, day, hh, mm, ss, tzinfo=VET_TZ)
    except ValueError:
        return None

    return dt_vet.strftime("%Y-%m-%d"), dt_vet.astimezone(UTC)


def _infer_payment_method(concept: str) -> str:
    upper = normalize_text(concept)
    if any(k in upper for k in _PAGO_MOVIL_KEYWORDS):
        return "PAGO_MOVIL"
    return "TRANSFERENCIA"


def _is_bank_fee_concept(concept: str) -> bool:
    upper = normalize_text(concept)
    if any(k in upper for k in _BANK_FEE_KEYWORDS):
        return True
    return bool(_COMIS_ABBREV_RE.search(upper))


def _extract_reference(text: str, explicit_ref: str | None = None) -> tuple[str, str]:
    """Extrae número de referencia bancaria limpio y devuelve (referencia, concepto_restante)."""
    if explicit_ref:
        ref_clean = normalize_reference(explicit_ref)
        if ref_clean != "S/R":
            return ref_clean[:50], _sanitize_cell_text(text)

    m_explicit = re.search(
        r"(?:REF(?:ERENCIA)?\.?|NRO\.?|DOC\.?|SERIAL|#)\s*[:#-]?\s*([A-Za-z0-9]{4,20})",
        text,
        re.IGNORECASE,
    )
    if m_explicit:
        ref_val = m_explicit.group(1).strip()
        cleaned = (text[: m_explicit.start()] + " " + text[m_explicit.end() :]).strip()
        return ref_val[:50], _sanitize_cell_text(cleaned or text)

    # Evitar confundir fechas ("EL 01-10-26"), cédulas ("V90026775") o horas ("19:19:41") con números de referencia
    scrubbed = re.sub(r"\bEL\s+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b", " ", text, flags=re.IGNORECASE)
    scrubbed = re.sub(r"\b\d{1,2}:\d{2}:\d{2}\b", " ", scrubbed)
    scrubbed = re.sub(r"\b[VEJGP]-?\d{6,10}\b", " ", scrubbed, flags=re.IGNORECASE)
    m_digits = re.search(r"(?<![\/\.-])\b(\d{5,16})\b(?![\/\.-])", scrubbed)
    if m_digits:
        ref_val = m_digits.group(1)
        cleaned = re.sub(rf"\b{re.escape(ref_val)}\b", "", text, count=1).strip()
        return ref_val[:50], _sanitize_cell_text(cleaned or text)

    return "S/R", _sanitize_cell_text(text)


def _match_header_role(col_name: str) -> str | None:
    norm = normalize_text(col_name).lower()
    norm_alpha = re.sub(r"[^a-z0-9 ]", " ", norm).strip()
    for role, aliases in _HEADER_SYNONYMS.items():
        for alias in aliases:
            alias_clean = re.sub(r"[^a-z0-9 ]", " ", alias).strip()
            if norm_alpha == alias_clean or alias_clean in norm_alpha.split():
                return role
        # Fallback por inclusión para cabeceras compuestas
        for alias in aliases:
            alias_clean = re.sub(r"[^a-z0-9 ]", " ", alias).strip()
            if len(alias_clean) >= 5 and alias_clean in norm_alpha:
                return role

    # Tolerancia controlada a errores tipográficos leves de OCR en cabeceras (ej. "CARGS", "hgresos", "sSaldo", "Desctipeion")
    compact = re.sub(r"\s+", "", norm_alpha)
    if compact and not re.search(r"\d{2}", compact):
        ocr_header_map: dict[str, str] = {
            "ree": "reference",
            "ref": "reference",
            "cargs": "debit",
            "egres0s": "debit",
            "hgresos": "credit",
            "ingres0s": "credit",
            "ssaldo": "balance",
            "sald0": "balance",
            "sald0s": "balance",
        }
        if compact in ocr_header_map:
            return ocr_header_map[compact]
        if len(compact) >= 5:
            best_role: str | None = None
            best_ratio = 0.0
            for role, aliases in _HEADER_SYNONYMS.items():
                for alias in aliases:
                    alias_c = re.sub(r"[^a-z0-9]", "", alias)
                    if len(alias_c) < 5:
                        continue
                    ratio = SequenceMatcher(None, compact, alias_c).ratio()
                    if ratio >= 0.80 and ratio > best_ratio:
                        best_ratio = ratio
                        best_role = role
            if best_role is not None:
                return best_role
    return None


@dataclass
class _PdfWordLine:
    """Línea visual reconstruida a partir de palabras con coordenadas PDF (x0, top, x1, bottom)."""

    words: list[dict[str, Any]]
    top: float
    bottom: float
    y_mid: float
    text: str


@dataclass
class _PdfColAnchor:
    """Columna detectada en cabecera PDF con banda horizontal calibrada [left, right]."""

    role: str
    hdr_x0: float
    hdr_x1: float
    left: float
    right: float
    anchor_x1: float
    anchor_xc: float


def _is_noise_or_footer_line(text: str) -> bool:
    """Detecta cabeceras repetidas, resúmenes y pies de página que no son movimientos ni descripciones."""
    upper = normalize_text(text)
    if not upper:
        return True
    if any(upper.startswith(nk) or f" {nk}" in upper for nk in _NOISE_LINE_KEYWORDS):
        return True
    if re.match(r"^(?:PAGINA|PAGE|HOJA)\s*:?\s*\d+\s*(?:/|DE|OF)?\s*\d*$", upper):
        return True
    return bool(
        re.match(
            r"^(?:CLIENTE|DIRECCION|CUENTA|PERIODO)\s*(?::|\d{4}[*X-]+|[VEJGP]-?\d{5,}|$)",
            upper,
        )
    )


def _group_words_into_lines(words: list[dict[str, Any]], y_tol: float = 2.6) -> list[_PdfWordLine]:
    """Agrupa palabras de pdfplumber por coordenada vertical respetando renglones multilínea cercanos."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))
    groups: list[list[dict[str, Any]]] = []
    anchor_top = float(ordered[0]["top"])
    current: list[dict[str, Any]] = []

    for w in ordered:
        w_top = float(w["top"])
        if not current or abs(w_top - anchor_top) <= y_tol:
            if not current:
                anchor_top = w_top
            current.append(w)
        else:
            groups.append(current)
            current = [w]
            anchor_top = w_top
    if current:
        groups.append(current)

    lines: list[_PdfWordLine] = []
    for grp in groups:
        grp_sorted = sorted(grp, key=lambda w: float(w["x0"]))
        # Fusionar montos con decimales separados por OCR (ej. "3.938.263," + "48" o "-" + "1.234,56")
        merged_grp: list[dict[str, Any]] = []
        idx = 0
        while idx < len(grp_sorted):
            cur = grp_sorted[idx]
            cur_txt = str(cur.get("text", "")).strip()
            if idx + 1 < len(grp_sorted):
                nxt = grp_sorted[idx + 1]
                nxt_txt = str(nxt.get("text", "")).strip()
                gap = float(nxt["x0"]) - float(cur["x1"])
                if (
                    gap <= 10.0
                    and (
                        (re.fullmatch(r"[-+]?\d[\d.,]*[.,]", cur_txt) and re.fullmatch(r"\d{2}", nxt_txt))
                        or (cur_txt == "-" and _MONEY_TOKEN_RE.fullmatch(nxt_txt))
                    )
                ):
                    merged_grp.append(
                        {
                            "text": f"{cur_txt}{nxt_txt}",
                            "x0": float(cur["x0"]),
                            "x1": float(nxt["x1"]),
                            "top": min(float(cur["top"]), float(nxt["top"])),
                            "bottom": max(float(cur["bottom"]), float(nxt["bottom"])),
                        }
                    )
                    idx += 2
                    continue
            merged_grp.append(cur)
            idx += 1

        top_v = min(float(w["top"]) for w in merged_grp)
        bot_v = max(float(w["bottom"]) for w in merged_grp)
        txt = " ".join(str(w["text"]).strip() for w in merged_grp if str(w["text"]).strip())
        if txt:
            lines.append(
                _PdfWordLine(
                    words=merged_grp,
                    top=top_v,
                    bottom=bot_v,
                    y_mid=(top_v + bot_v) / 2.0,
                    text=txt,
                )
            )
    return lines


def _cluster_header_words(words: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    """Combina etiquetas apiladas verticalmente o compuestas en la misma columna de cabecera."""
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: (float(w["x0"]), float(w["top"])))
    clusters: list[dict[str, Any]] = []

    for w in sorted_w:
        wx0 = float(w["x0"])
        wx1 = float(w["x1"])
        wtop = float(w["top"])
        wtxt = str(w["text"]).strip()
        placed = False
        for cl in clusters:
            # Solapamiento horizontal (palabras apiladas verticalmente: "Fecha" / "Oper")
            if wx0 <= cl["x1"] + 3.5 and wx1 >= cl["x0"] - 3.5 and abs(wtop - cl["last_top"]) > 2.5:
                cl["items"].append((wtop, wx0, wtxt))
                cl["x0"] = min(cl["x0"], wx0)
                cl["x1"] = max(cl["x1"], wx1)
                cl["last_top"] = wtop
                placed = True
                break
        if not placed:
            clusters.append({"x0": wx0, "x1": wx1, "last_top": wtop, "items": [(wtop, wx0, wtxt)]})

    clusters.sort(key=lambda c: float(c["x0"]))

    # Combinar etiquetas compuestas en el mismo renglón si su unión coincide con una columna conocida
    merged: list[dict[str, Any]] = []
    for cl in clusters:
        cl_txt = " ".join(it[2] for it in sorted(cl["items"], key=lambda it: (it[0], it[1])))
        if merged:
            prev = merged[-1]
            prev_txt = " ".join(it[2] for it in sorted(prev["items"], key=lambda it: (it[0], it[1])))
            gap = float(cl["x0"]) - float(prev["x1"])
            if gap <= 8.0 and abs(float(cl["last_top"]) - float(prev["last_top"])) <= 3.0:
                combo = f"{prev_txt} {cl_txt}"
                if _match_header_role(combo) is not None and _match_header_role(cl_txt) is None:
                    prev["items"].extend(cl["items"])
                    prev["x1"] = max(float(prev["x1"]), float(cl["x1"]))
                    continue
        merged.append(cl)

    result: list[tuple[str, float, float]] = []
    for cl in merged:
        txt = " ".join(it[2] for it in sorted(cl["items"], key=lambda it: (it[0], it[1])))
        result.append((txt, float(cl["x0"]), float(cl["x1"])))
    return result


def _header_quality_score(anchors: list[_PdfColAnchor]) -> int:
    """Puntúa candidatos de cabecera priorizando tablas principales completas frente a subtablas auxiliares."""
    roles = [a.role for a in anchors]
    distinct = set(roles)
    score = len(distinct) * 10
    if "concept" in distinct:
        score += 15
    if "balance" in distinct:
        score += 15
    if "debit" in distinct and "credit" in distinct:
        score += 10
    if len(roles) > len(distinct) + 1:
        score -= 10
    return score


def _detect_pdf_word_header(
    wlines: list[_PdfWordLine],
) -> tuple[int, int, list[_PdfColAnchor]] | None:
    """Detecta la cabecera principal de tabla (1–3 renglones apilados) ignorando paneles paralelos y mini-tablas."""
    numeric_roles = {"debit", "credit", "amount", "balance"}

    def _evaluate_window(win_lines: list[_PdfWordLine]) -> list[_PdfColAnchor] | None:
        words = [w for ln in win_lines for w in ln.words]
        clusters = _cluster_header_words(words)
        if len(clusters) < 3:
            return None

        anchors: list[_PdfColAnchor] = []
        has_date = False
        has_numeric = False
        for txt, cx0, cx1 in clusters:
            role = _match_header_role(txt)
            if not role:
                continue
            if role == "date":
                has_date = True
                if any(a.role == "date" for a in anchors):
                    role = "date_alt"
            if role in numeric_roles:
                has_numeric = True
            anchors.append(
                _PdfColAnchor(
                    role=role,
                    hdr_x0=cx0,
                    hdr_x1=cx1,
                    left=cx0,
                    right=cx1,
                    anchor_x1=cx1,
                    anchor_xc=(cx0 + cx1) / 2.0,
                )
            )
        if not (has_date and has_numeric and len(anchors) >= 3):
            return None
        anchors.sort(key=lambda a: a.hdr_x0)
        span_left = anchors[0].hdr_x0 - 10.0
        span_right = anchors[-1].hdr_x1 + 15.0
        table_hdr_text = " ".join(
            str(w["text"]).strip()
            for w in sorted(words, key=lambda it: (float(it["top"]), float(it["x0"])))
            if span_left <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= span_right
        )
        if _DATE_ANY_RE.search(table_hdr_text) or _MONEY_TOKEN_RE.search(table_hdr_text):
            return None
        return anchors

    def _overlaps_existing_cols(line_obj: _PdfWordLine, cols: list[_PdfColAnchor]) -> bool:
        return any(
            float(w["x0"]) <= c.hdr_x1 + 3.0 and float(w["x1"]) >= c.hdr_x0 - 3.0
            for w in line_obj.words
            for c in cols
        )

    n = len(wlines)
    scan_limit = min(n, 45)
    best_overall: tuple[int, int, int, list[_PdfColAnchor]] | None = None

    for i in range(scan_limit):
        single = _evaluate_window([wlines[i]])
        best_end = i + 1
        best_cols = single

        end_j = i + 1
        while end_j < n and end_j - i < 3 and (wlines[end_j].top - wlines[i].top) <= 16.0:
            cand = _evaluate_window(wlines[i : end_j + 1])
            if cand is None:
                break
            if best_cols is None:
                best_cols = cand
                best_end = end_j + 1
            else:
                cand_roles = {a.role for a in cand}
                best_roles = {a.role for a in best_cols}
                if len(cand_roles) > len(best_roles) or (
                    len(cand) >= len(best_cols) and _overlaps_existing_cols(wlines[end_j], best_cols)
                ):
                    best_cols = cand
                    best_end = end_j + 1
            end_j += 1

        if best_cols is not None:
            sc = _header_quality_score(best_cols)
            if best_overall is None or sc > best_overall[0]:
                best_overall = (sc, i, best_end, best_cols)

    if best_overall is None:
        return None
    return best_overall[1], best_overall[2], best_overall[3]


def _split_page_words_into_panels(
    words: list[dict[str, Any]],
    page_w: float,
    y_tol: float,
    prev_split_x: float | None = None,
) -> tuple[list[tuple[list[dict[str, Any]], float]], float | None]:
    """Detecta páginas apaisadas con 2 tablas paralelas (Banesco/Mercantil págs. 2+) y las divide izquierda -> derecha."""
    if not words or page_w <= 0.0:
        return [(words, page_w)], prev_split_x

    wlines = _group_words_into_lines(words, y_tol=y_tol)
    if not wlines:
        return [(words, page_w)], prev_split_x

    scan_limit = min(len(wlines), 45)
    detected_split_x: float | None = None

    for i in range(scan_limit):
        for span in (1, 2):
            if i + span > len(wlines):
                break
            win = wlines[i : i + span]
            if span == 2 and (win[1].top - win[0].top) > 14.0:
                continue
            win_words = [w for ln in win for w in ln.words]
            clusters = _cluster_header_words(win_words)
            date_clusters = [c for c in clusters if _match_header_role(c[0]) == "date"]
            if len(date_clusters) < 2:
                continue

            # Buscar par (cabecera fecha izquierda, cabecera fecha derecha) suficientemente separado
            for d_left in date_clusters:
                if d_left[1] >= page_w * 0.35:
                    continue
                for d_right in date_clusters:
                    if d_right[1] <= page_w * 0.42:
                        continue
                    if (d_right[1] - d_left[2]) < page_w * 0.25:
                        continue

                    # Calcular línea de corte X limpia entre el borde derecho del panel izquierdo y d_right.x0
                    left_side_clusters = [c for c in clusters if c[2] <= d_right[1] + 2.0]
                    left_edge = max((c[2] for c in left_side_clusters), default=d_right[1] - 12.0)
                    cand_split_x = (
                        (left_edge + d_right[1]) / 2.0
                        if left_edge < d_right[1]
                        else (d_right[1] - 4.0)
                    )
                    cand_split_x = min(d_right[1] - 2.0, max(page_w * 0.35, cand_split_x))

                    lw = [w for w in win_words if ((float(w["x0"]) + float(w["x1"])) / 2.0) < cand_split_x]
                    rw = [
                        {**w, "x0": float(w["x0"]) - cand_split_x, "x1": float(w["x1"]) - cand_split_x}
                        for w in win_words
                        if ((float(w["x0"]) + float(w["x1"])) / 2.0) >= cand_split_x
                    ]
                    l_hdr = _detect_pdf_word_header(_group_words_into_lines(lw, y_tol=y_tol))
                    r_hdr = _detect_pdf_word_header(_group_words_into_lines(rw, y_tol=y_tol))
                    if l_hdr is not None and r_hdr is not None:
                        detected_split_x = cand_split_x
                        break
                if detected_split_x is not None:
                    break
            if detected_split_x is not None:
                break
        if detected_split_x is not None:
            break

    eff_split_x = detected_split_x
    if eff_split_x is None and prev_split_x is not None and _detect_pdf_word_header(wlines) is None:
        # Si la página no repite cabecera pero continúa un diseño de 2 paneles, reutilizar el corte vertical
        eff_split_x = prev_split_x

    if eff_split_x is None:
        return [(words, page_w)], None

    left_panel_words = [
        w for w in words if ((float(w["x0"]) + float(w["x1"])) / 2.0) < eff_split_x
    ]
    right_panel_words = [
        {**w, "x0": max(0.0, float(w["x0"]) - eff_split_x), "x1": max(0.5, float(w["x1"]) - eff_split_x)}
        for w in words
        if ((float(w["x0"]) + float(w["x1"])) / 2.0) >= eff_split_x
    ]
    panels: list[tuple[list[dict[str, Any]], float]] = []
    if left_panel_words:
        panels.append((left_panel_words, eff_split_x))
    if right_panel_words:
        panels.append((right_panel_words, max(1.0, page_w - eff_split_x)))
    return (panels or [(words, page_w)]), eff_split_x


def _calibrate_pdf_column_bands(
    anchors: list[_PdfColAnchor],
    body_lines: list[_PdfWordLine],
    page_width: float,
    allow_day_only: bool = False,
) -> list[_PdfColAnchor]:
    """Calibra fronteras horizontales [left, right] reales usando datos de fecha y montos de la página."""
    cols = [
        _PdfColAnchor(
            role=a.role,
            hdr_x0=a.hdr_x0,
            hdr_x1=a.hdr_x1,
            left=a.hdr_x0,
            right=a.hdr_x1,
            anchor_x1=a.anchor_x1,
            anchor_xc=a.anchor_xc,
        )
        for a in sorted(anchors, key=lambda x: x.hdr_x0)
    ]

    emp_x0: dict[int, list[float]] = {idx: [] for idx in range(len(cols))}
    emp_x1: dict[int, list[float]] = {idx: [] for idx in range(len(cols))}
    num_indices = [i for i, c in enumerate(cols) if c.role in ("debit", "credit", "amount", "balance")]
    date_indices = [i for i, c in enumerate(cols) if c.role in ("date", "date_alt")]
    ref_indices = [i for i, c in enumerate(cols) if c.role == "reference"]

    for wl in body_lines:
        if _is_noise_or_footer_line(wl.text):
            continue
        has_money = bool(_MONEY_TOKEN_RE.search(wl.text))
        has_date = bool(_DATE_ANY_RE.search(wl.text))
        if not has_date and allow_day_only and date_indices:
            dc0 = cols[date_indices[0]]
            has_date = any(
                abs(((float(w["x0"]) + float(w["x1"])) / 2.0) - dc0.anchor_xc) <= 35.0
                and re.fullmatch(r"0?[1-9]|[12]\d|3[01]", str(w["text"]).strip())
                for w in wl.words
            )
        if not (has_date and has_money):
            continue

        for d_idx in date_indices:
            dc = cols[d_idx]
            near_words = [
                w
                for w in wl.words
                if abs(((float(w["x0"]) + float(w["x1"])) / 2.0) - dc.anchor_xc) <= 55.0
            ]
            # Buscar tokens fecha contiguos cerca del centro de columna fecha
            joined_near = " ".join(str(w["text"]) for w in near_words)
            if _DATE_ANY_RE.search(joined_near) or (
                allow_day_only and any(re.fullmatch(r"0?[1-9]|[12]\d|3[01]", str(w["text"]).strip()) for w in near_words)
            ):
                d_tokens = [
                    w
                    for w in near_words
                    if _DATE_ANY_RE.search(str(w["text"]))
                    or re.fullmatch(r"\d{1,4}|[A-Za-z]{3}", str(w["text"]))
                ]
                if d_tokens:
                    emp_x0[d_idx].append(min(float(w["x0"]) for w in d_tokens))
                    emp_x1[d_idx].append(max(float(w["x1"]) for w in d_tokens))

        for r_idx in ref_indices:
            rc = cols[r_idx]
            for w in wl.words:
                wxc = (float(w["x0"]) + float(w["x1"])) / 2.0
                if abs(wxc - rc.anchor_xc) <= 45.0 and re.search(r"\d{3,}", str(w["text"])):
                    emp_x0[r_idx].append(float(w["x0"]))
                    emp_x1[r_idx].append(float(w["x1"]))
                    break

        money_words = [w for w in wl.words if _MONEY_TOKEN_RE.fullmatch(str(w["text"]).strip())]
        if money_words and num_indices:
            rem_words = list(money_words)
            bal_i = next((i for i in num_indices if cols[i].role == "balance"), None)
            if bal_i is not None and len(rem_words) >= 2:
                bw = rem_words.pop(-1)
                emp_x0[bal_i].append(float(bw["x0"]))
                emp_x1[bal_i].append(float(bw["x1"]))
            tx_nums = [i for i in num_indices if i != bal_i] or num_indices
            used_cols: set[int] = set()
            for mw in rem_words:
                mx1 = float(mw["x1"])
                mxc = (float(mw["x0"]) + mx1) / 2.0
                cand_cols = [i for i in tx_nums if i not in used_cols] or tx_nums
                best_i = min(
                    cand_cols,
                    key=lambda ci: min(abs(mx1 - cols[ci].hdr_x1), abs(mxc - cols[ci].anchor_xc)),
                )
                used_cols.add(best_i)
                emp_x0[best_i].append(float(mw["x0"]))
                emp_x1[best_i].append(float(mw["x1"]))

    eff_x0: list[float] = []
    eff_x1: list[float] = []
    for idx, c in enumerate(cols):
        x0_val = min([c.hdr_x0, *emp_x0[idx]]) if emp_x0[idx] else c.hdr_x0
        x1_val = max([c.hdr_x1, *emp_x1[idx]]) if emp_x1[idx] else c.hdr_x1
        eff_x0.append(x0_val)
        eff_x1.append(x1_val)
        if c.role in ("debit", "credit", "amount", "balance") and emp_x1[idx]:
            sorted_r = sorted(emp_x1[idx])
            c.anchor_x1 = sorted_r[len(sorted_r) // 2]
            sorted_xc = sorted((a + b) / 2.0 for a, b in zip(emp_x0[idx], emp_x1[idx], strict=False))
            c.anchor_xc = sorted_xc[len(sorted_xc) // 2]

    # Ajustar fronteras [left, right] dejando que 'concept' aproveche todo el espacio hasta columnas adyacentes
    for idx, c in enumerate(cols):
        if idx == 0:
            c.left = max(0.0, c.hdr_x0 - 20.0) if c.hdr_x0 >= 120.0 else 0.0
        else:
            prev_c = cols[idx - 1]
            if c.role == "concept":
                c.left = min(eff_x0[idx] - 3.0, (eff_x1[idx - 1] + eff_x0[idx]) / 2.0)
            elif prev_c.role == "concept":
                c.left = eff_x0[idx] - 4.0
            else:
                c.left = (eff_x1[idx - 1] + eff_x0[idx]) / 2.0

        if idx == len(cols) - 1:
            c.right = max(page_width, eff_x1[idx] + 40.0)
        else:
            next_c = cols[idx + 1]
            if c.role == "concept":
                c.right = eff_x0[idx + 1] - 4.0
            elif next_c.role == "concept":
                c.right = max(eff_x1[idx] + 3.0, (eff_x1[idx] + eff_x0[idx + 1]) / 2.0)
            else:
                c.right = (eff_x1[idx] + eff_x0[idx + 1]) / 2.0

        if c.right < c.left:
            c.right = c.left + 1.0

    return cols


_OCR_GLUED_MONEY_RE = re.compile(
    r"^([+-]?\s*(?:\d{1,3}(?:[.,]\d{3})+|\d+)[.,]\d{2})([+-]?\s*(?:\d{1,3}(?:[.,]\d{3})+|\d+)[.,]\d{2})$"
)
_OCR_GLUED_DATE_REF_RE = re.compile(r"^(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})(\d{5,})$")
_OCR_GLUED_REF_DESC_RE = re.compile(r"^([A-Za-z]?\d{8,16})(N[DC]\s*[-–].*|[A-Z]{2,}.*)$")

_RAPIDOCR_ENGINE: Any = None
_RAPIDOCR_LOCK = threading.Lock()


def _get_rapidocr_engine() -> Any:
    """Inicializa de forma perezosa y thread-safe el motor local RapidOCR (ONNX)."""
    global _RAPIDOCR_ENGINE
    if _RAPIDOCR_ENGINE is not None:
        return _RAPIDOCR_ENGINE
    with _RAPIDOCR_LOCK:
        if _RAPIDOCR_ENGINE is None:
            try:
                from rapidocr_onnxruntime import RapidOCR

                _RAPIDOCR_ENGINE = RapidOCR()
            except (ImportError, OSError, RuntimeError):
                return None
    return _RAPIDOCR_ENGINE


def _find_tesseract_cmd() -> str | None:
    """Localiza el ejecutable nativo de Tesseract 5 en Linux o Windows."""
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    for win_path in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.isfile(win_path):
            return win_path
    return None


def _preprocess_image_for_ocr(img: Image.Image) -> tuple[Image.Image, float]:
    """Convierte a RGB sobre fondo blanco, reescala capturas pequeñas 2x y devuelve escala a ancho 612pt."""
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(bg, rgba).convert("RGB")
    elif img.mode != "RGB":
        rgb = img.convert("RGB")
    else:
        rgb = img

    w, h = rgb.size
    if w <= 0 or h <= 0:
        raise ValueError("La imagen del estado de cuenta tiene dimensiones inválidas.")

    if w < 1800 and h <= MAX_OCR_IMAGE_HEIGHT:
        factor = min(2.0, MAX_OCR_IMAGE_WIDTH / float(w), MAX_OCR_IMAGE_HEIGHT / float(h))
        if factor > 1.01:
            new_w = max(1, round(w * factor))
            new_h = max(1, round(h * factor))
            rgb = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
    elif w > MAX_OCR_IMAGE_WIDTH or h > MAX_OCR_IMAGE_HEIGHT:
        ratio = min(MAX_OCR_IMAGE_WIDTH / float(w), MAX_OCR_IMAGE_HEIGHT / float(h))
        new_w = max(1, round(w * ratio))
        new_h = max(1, round(h * ratio))
        rgb = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)

    norm_scale = 612.0 / float(rgb.width)
    return rgb, norm_scale


def _split_ocr_text_into_subwords(
    raw_text: str,
    x0: float,
    top: float,
    x1: float,
    bottom: float,
) -> list[dict[str, Any]]:
    """Separa bloques OCR con columnas pegadas y distribuye proporcionalmente sus coordenadas X."""
    cleaned = re.sub(r"\s+", " ", raw_text or "").strip()
    if not cleaned:
        return []
    # Reparar decimales o signos separados por OCR ("3.938.263, 48" -> "3.938.263,48")
    cleaned = re.sub(r"(\d[.,])\s+(\d{2})(?=\s|$)", r"\1\2", cleaned)
    cleaned = re.sub(r"(?<!\S)-\s+(\d[\d.,]*[.,]\d{2})(?=\s|$)", r"-\1", cleaned)

    parts: list[str] = []
    for tok in cleaned.split(" "):
        if not tok:
            continue
        if _MONEY_TOKEN_RE.fullmatch(tok):
            parts.append(tok)
            continue
        m_gm = _OCR_GLUED_MONEY_RE.fullmatch(tok)
        if m_gm:
            parts.extend([m_gm.group(1).strip(), m_gm.group(2).strip()])
            continue
        m_dr = _OCR_GLUED_DATE_REF_RE.match(tok)
        if m_dr:
            parts.extend([m_dr.group(1), m_dr.group(2)])
            continue
        m_rd = _OCR_GLUED_REF_DESC_RE.match(tok)
        if m_rd:
            parts.extend([m_rd.group(1), m_rd.group(2)])
            continue
        parts.append(tok)

    if len(parts) == 1:
        return [{"text": parts[0], "x0": x0, "x1": x1, "top": top, "bottom": bottom}]

    width = max(1.0, x1 - x0)
    total_chars = max(1, sum(len(p) for p in parts) + (len(parts) - 1))
    words: list[dict[str, Any]] = []
    cursor = 0
    for part in parts:
        p_len = len(part)
        sub_x0 = x0 + (cursor / total_chars) * width
        sub_x1 = x0 + ((cursor + p_len) / total_chars) * width
        words.append(
            {
                "text": part,
                "x0": sub_x0,
                "x1": max(sub_x0 + 1.0, sub_x1),
                "top": top,
                "bottom": bottom,
            }
        )
        cursor += p_len + 1
    return words


def _run_rapidocr_on_image(img: Image.Image) -> tuple[list[dict[str, Any]], float]:
    """Ejecuta RapidOCR (ONNX CPU) localmente devolviendo palabras normalizadas a espacio 612pt."""
    engine = _get_rapidocr_engine()
    if engine is None:
        return [], 0.0
    try:
        import numpy as np

        rgb_img, scale = _preprocess_image_for_ocr(img)
        raw_res, _ = engine(np.asarray(rgb_img))
    except (ImportError, OSError, RuntimeError, ValueError, TypeError):
        return [], 0.0

    if not raw_res:
        return [], 0.0

    words: list[dict[str, Any]] = []
    scores: list[float] = []
    for item in raw_res:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        box, txt = item[0], str(item[1] or "").strip()
        sc_raw = item[2] if len(item) >= 3 else 0.85
        try:
            conf = float(sc_raw)
        except (ValueError, TypeError):
            conf = 0.85
        if conf < 0.25 or not txt:
            continue
        try:
            xs = [float(pt[0]) * scale for pt in box]
            ys = [float(pt[1]) * scale for pt in box]
        except (TypeError, ValueError, IndexError):
            continue
        x0, x1 = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        sub = _split_ocr_text_into_subwords(txt, x0, top, x1, bottom)
        if sub:
            words.extend(sub)
            scores.append(conf)

    mean_conf = (sum(scores) / len(scores)) if scores else 0.0
    return words, round(mean_conf, 4)


def _run_tesseract_on_image(img: Image.Image) -> tuple[list[dict[str, Any]], float]:
    """Ejecuta Tesseract 5 (`tesseract-ocr-spa`) aislado sin env ni secretos, devolviendo cajas 612pt."""
    tess_cmd = _find_tesseract_cmd()
    if not tess_cmd:
        return [], 0.0

    try:
        rgb_img, scale = _preprocess_image_for_ocr(img)
        gray = ImageOps.autocontrast(rgb_img.convert("L"), cutoff=1).filter(ImageFilter.SHARPEN)
        png_bytes = image_to_clean_png_bytes(gray)
        clean_env = build_clean_ocr_env()

        tsv_text = ""
        for lang in ("spa+eng", "spa", "eng"):
            try:
                proc = subprocess.run(
                    [tess_cmd, "stdin", "stdout", "-l", lang, "--psm", "6", "tsv"],
                    input=png_bytes,
                    env=clean_env,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
            except (subprocess.SubprocessError, OSError, TimeoutError):
                return [], 0.0
            if proc.returncode == 0 and proc.stdout:
                tsv_text = proc.stdout.decode("utf-8", errors="replace")
                break
        if not tsv_text:
            return [], 0.0
    except (OSError, RuntimeError, ValueError, TypeError):
        return [], 0.0

    words: list[dict[str, Any]] = []
    scores: list[float] = []
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    for row in reader:
        txt = str(row.get("text") or "").strip()
        if not txt:
            continue
        try:
            conf_pct = float(row.get("conf") or -1.0)
            x_px = float(row.get("left") or 0.0)
            y_px = float(row.get("top") or 0.0)
            w_px = float(row.get("width") or 0.0)
            h_px = float(row.get("height") or 0.0)
        except (ValueError, TypeError):
            continue
        if conf_pct < 20.0:
            continue
        x0 = x_px * scale
        top = y_px * scale
        x1 = (x_px + w_px) * scale
        bottom = (y_px + h_px) * scale
        sub = _split_ocr_text_into_subwords(txt, x0, top, x1, bottom)
        if sub:
            words.extend(sub)
            scores.append(min(1.0, max(0.0, conf_pct / 100.0)))

    mean_conf = (sum(scores) / len(scores)) if scores else 0.0
    return words, round(mean_conf, 4)


def _render_single_pdf_page(pdf_doc: Any, page_idx: int) -> Image.Image | None:
    """Renderiza una única página PDFium a imagen RGB limpia y libera los recursos de la página inmediatamente."""
    page = pdf_doc[page_idx]
    try:
        w_pt, h_pt = page.get_size()
        safe_scale = compute_safe_pdf_render_scale(float(w_pt), float(h_pt), target_scale=2.2)
        if safe_scale is None:
            return None
        bitmap = page.render(scale=safe_scale)
        raw_pil = bitmap.to_pil().convert("RGB")
        if (raw_pil.width * raw_pil.height) > MAX_OCR_IMAGE_PIXELS:
            return None
        return Image.frombytes("RGB", raw_pil.size, raw_pil.tobytes())
    finally:
        page.close()


def _render_pdf_pages_as_images(file_bytes: bytes, max_pages: int = MAX_PDF_PAGES) -> list[Image.Image]:
    """Renderiza páginas de PDF escaneado a imágenes RGB limpias acotando dimensiones de salida."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []

    rendered: list[Image.Image] = []
    try:
        pdf_doc = pdfium.PdfDocument(file_bytes)
    except Exception:  # noqa: BLE001 - fallo de driver PDFium aislado fail-closed
        return []

    try:
        count = min(len(pdf_doc), max_pages)
        for idx in range(count):
            clean_pil = _render_single_pdf_page(pdf_doc, idx)
            if clean_pil is not None:
                rendered.append(clean_pil)
    finally:
        pdf_doc.close()
    return rendered


class BankStatementImporter:
    """Extractor, verificador matemático y conciliador universal de estados de cuenta bancarios."""

    GEMINI_MODELS: tuple[str, ...] = ("gemini-2.0-flash", "gemini-flash-lite-latest")

    def __init__(
        self,
        key_pool: AIKeyPool | None = None,
        http_client: httpx.Client | None = None,
        ocr_engines: dict[str, Any] | None = None,
    ) -> None:
        if key_pool is None:
            raw_keys = (
                os.getenv("GEMINI_API_KEYS")
                or os.getenv("AI_API_KEYS")
                or os.getenv("AI_API_KEY")
                or ""
            )
            keys = [k.strip() for k in re.split(r"[,;]", raw_keys) if k.strip()]
            self.key_pool = AIKeyPool(keys or ["dummy_key"])
        else:
            self.key_pool = key_pool
        self._client = http_client
        self._ocr_engines: dict[str, Any] | None = ocr_engines

    def _has_real_ai_key(self) -> bool:
        keys = getattr(self.key_pool, "keys", [])
        return any(k and k != "dummy_key" for k in keys)

    def _validate_upload(self, file_bytes: bytes, filename: str) -> str:
        """Valida tamaño, extensión, magic bytes y estructura anti-backdoor/DoS (Fail-Closed)."""
        if not file_bytes:
            raise ValueError("El archivo de estado de cuenta está vacío.")
        if len(file_bytes) > MAX_STATEMENT_BYTES:
            max_mb = MAX_STATEMENT_BYTES // (1024 * 1024)
            raise ValueError(f"El archivo supera el límite máximo permitido de {max_mb} MB.")

        ext = os.path.splitext((filename or "").lower())[1]
        if ext == ".pdf":
            validate_pdf_safety(file_bytes)
            return "PDF"
        if ext in IMAGE_EXTENSIONS:
            validate_image_magic_bytes(file_bytes, ext)
            return "IMAGE"
        if ext == ".xlsx":
            validate_xlsx_zip_safety(file_bytes)
            return "XLSX"
        if ext == ".xls":
            xls_kind = validate_xls_safety(file_bytes)
            if xls_kind == "XLSX":
                return "XLSX"
            if xls_kind == "HTML":
                return "XLS_HTML"
            return "XLS"
        if ext in (".csv", ".txt"):
            assert_not_executable_payload(file_bytes)
            if b"\x00" in file_bytes[:4096]:
                raise ValueError("El archivo de texto/CSV contiene bytes binarios inválidos.")
            return "CSV"

        raise ValueError(
            f"Formato '{ext or 'desconocido'}' no soportado. "
            "Usa PDF, PNG, JPG, WEBP, XLSX, XLS, CSV o TXT."
        )

    def parse_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
        year_hint: int | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> StatementPreviewResult:
        """Extrae movimientos bancarios desde PDF, Imagen, Excel o CSV y valida su cuadre matemático."""
        file_type = self._validate_upload(file_bytes, filename)
        default_year = year_hint or datetime.now(VET_TZ).year

        if file_type == "IMAGE":
            return self._parse_image_bytes(
                file_bytes=file_bytes,
                filename=filename,
                bank_name_override=bank_name,
                default_year=default_year,
            )

        if file_type in ("CSV", "XLSX", "XLS", "XLS_HTML"):
            result = self._parse_tabular_bytes(
                file_bytes=file_bytes,
                file_type=file_type,
                filename=filename,
                bank_name_override=bank_name,
                column_mapping=column_mapping,
                default_year=default_year,
            )
        else:
            result = self._parse_pdf_bytes(
                file_bytes=file_bytes,
                filename=filename,
                bank_name_override=bank_name,
                default_year=default_year,
                progress_callback=progress_callback,
            )

        if not result.extraction_method.startswith(("PDF_OCR_", "IMAGE_OCR_")):
            self._verify_and_classify_rows(result)
        return result

    def _decode_csv_rows(self, file_bytes: bytes) -> list[list[str]]:
        decoded = ""
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                decoded = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not decoded:
            decoded = file_bytes.decode("latin-1", errors="replace")

        sample = "\n".join(decoded.splitlines()[:15])
        counts = {sep: sample.count(sep) for sep in (";", ",", "\t", "|")}
        sep = max(counts, key=lambda k: counts[k]) if max(counts.values()) > 0 else ","

        reader = csv.reader(io.StringIO(decoded), delimiter=sep)
        rows: list[list[str]] = []
        for idx, row in enumerate(reader):
            if idx >= MAX_STATEMENT_ROWS + 50:
                break
            rows.append([str(c or "").strip() for c in row])
        return rows

    def _read_excel_rows(self, file_bytes: bytes, file_type: str = "XLSX") -> list[list[str]]:
        if file_type == "XLS_HTML":
            return parse_html_table_rows(file_bytes, max_rows=MAX_STATEMENT_ROWS + 50)
        if file_type == "XLSX":
            df_raw = pd.read_excel(
                io.BytesIO(file_bytes),
                header=None,
                nrows=MAX_STATEMENT_ROWS + 50,
                engine="openpyxl",
                engine_kwargs={"read_only": True, "data_only": True},
            )
        else:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=MAX_STATEMENT_ROWS + 50)
        rows: list[list[str]] = []
        for _, row in df_raw.iterrows():
            rows.append([("" if pd.isna(v) else str(v).strip()) for v in row.tolist()])
        return rows

    def _parse_tabular_bytes(
        self,
        file_bytes: bytes,
        file_type: str,
        filename: str,
        bank_name_override: str | None,
        column_mapping: dict[str, str] | None,
        default_year: int,
    ) -> StatementPreviewResult:
        raw_rows = (
            self._decode_csv_rows(file_bytes)
            if file_type == "CSV"
            else self._read_excel_rows(file_bytes, file_type=file_type)
        )
        normalized_file_type = "XLS" if file_type == "XLS_HTML" else file_type
        if not raw_rows:
            raise ValueError("El archivo tabular no contiene filas legibles.")

        # Localizar fila de cabeceras antes de inferir banco para no confundir bancos de contrapartes en movimientos
        header_idx: int | None = None
        role_map: dict[str, int] = {}
        headers: list[str] = []

        if column_mapping:
            wanted = {str(v).strip().lower(): k for k, v in column_mapping.items() if v}
            for i, row in enumerate(raw_rows[:30]):
                matched: dict[str, int] = {}
                for c_idx, cell in enumerate(row):
                    role = wanted.get(cell.strip().lower())
                    if role and role not in matched:
                        matched[role] = c_idx
                if "date" in matched and (
                    "amount" in matched or "debit" in matched or "credit" in matched
                ):
                    header_idx = i
                    role_map = matched
                    headers = row
                    break
        else:
            best_score = 0
            for i, row in enumerate(raw_rows[:30]):
                matched = {}
                for c_idx, cell in enumerate(row):
                    if not cell:
                        continue
                    role = _match_header_role(cell)
                    if role and role not in matched:
                        matched[role] = c_idx
                score = len(matched)
                has_core = "date" in matched and (
                    "debit" in matched or "credit" in matched or "amount" in matched
                )
                if has_core and score > best_score:
                    best_score = score
                    header_idx = i
                    role_map = matched
                    headers = row

        header_end = header_idx if header_idx and header_idx > 0 else min(5, len(raw_rows))
        preamble = " ".join(" ".join(r) for r in raw_rows[:header_end]) + f" {filename}"
        detected_bank = (
            normalize_bank_name(bank_name_override)
            if bank_name_override and bank_name_override.strip()
            else (detect_bank_from_text(preamble) or "BANCO DESCONOCIDO")
        )
        m_year = re.search(r"\b(20\d{2})\b", preamble)
        eff_year = int(m_year.group(1)) if m_year and default_year == datetime.now(VET_TZ).year else default_year

        warnings: list[str] = []
        if header_idx is None:
            # Buscar primera fila con >= 2 celdas no vacías como sugerencia de cabeceras
            candidate_cols = next((r for r in raw_rows[:15] if sum(1 for c in r if c) >= 2), [])
            return StatementPreviewResult(
                bank_name=detected_bank,
                file_type=normalized_file_type,
                extraction_method="TABULAR_NEEDS_MAPPING",
                detected_columns=[c for c in candidate_cols if c],
                needs_column_mapping=True,
                detected_order="UNKNOWN",
                opening_balance=None,
                closing_balance=None,
                balance_verified=False,
                balance_mismatch_count=0,
                total_rows=0,
                p2p_matched_count=0,
                bank_fee_count=0,
                duplicate_count=0,
                unmatched_count=0,
                warnings=[
                    (
                        "No se identificaron automáticamente las columnas del banco. "
                        "Asigna las columnas en la vista previa para continuar."
                    )
                ],
            )

        parsed_rows: list[ParsedStatementRow] = []
        for r_idx in range(header_idx + 1, len(raw_rows)):
            row = raw_rows[r_idx]
            if not any(row):
                continue

            joined = " ".join(row).upper()
            if any(k in joined for k in ("TOTAL DEBITO", "TOTAL CREDITO", "TOTAL CARGO", "TOTAL ABONO")):
                continue

            raw_date = row[role_map["date"]] if role_map["date"] < len(row) else ""
            parsed_dt = _parse_vet_date(raw_date, eff_year)
            if not parsed_dt:
                continue
            date_vet, dt_utc = parsed_dt

            raw_ref = (
                row[role_map["reference"]]
                if "reference" in role_map and role_map["reference"] < len(row)
                else ""
            )
            raw_concept = (
                row[role_map["concept"]]
                if "concept" in role_map and role_map["concept"] < len(row)
                else ""
            )
            ref_num, clean_concept = _extract_reference(raw_concept or joined, explicit_ref=raw_ref)

            debit_val = 0.0
            credit_val = 0.0
            amt_uncertain = False

            if "debit" in role_map or "credit" in role_map:
                if "debit" in role_map and role_map["debit"] < len(row):
                    debit_val, _ = _parse_signed_amount(row[role_map["debit"]])
                if "credit" in role_map and role_map["credit"] < len(row):
                    credit_val, _ = _parse_signed_amount(row[role_map["credit"]])

            if debit_val == 0.0 and credit_val == 0.0 and "amount" in role_map and role_map["amount"] < len(row):
                mag, explicit_dir = _parse_signed_amount(row[role_map["amount"]])
                if mag > 0.0:
                    type_hint = (
                        row[role_map["type"]].upper()
                        if "type" in role_map and role_map["type"] < len(row)
                        else ""
                    )
                    if "CR" in type_hint or "ABONO" in type_hint or explicit_dir == "CREDIT":
                        credit_val = mag
                    elif "DB" in type_hint or "DEBIT" in type_hint or "CARGO" in type_hint or explicit_dir == "DEBIT":
                        debit_val = mag
                    else:
                        credit_val = mag
                        amt_uncertain = True

            if debit_val <= 0.0 and credit_val <= 0.0:
                continue

            mov_type: Literal["DEBIT", "CREDIT"] = "DEBIT" if debit_val > 0.0 else "CREDIT"
            amount_ves = debit_val if debit_val > 0.0 else credit_val

            bal_val: float | None = None
            if "balance" in role_map and role_map["balance"] < len(row) and row[role_map["balance"]]:
                bal_val = _parse_signed_balance(row[role_map["balance"]])

            parsed_rows.append(
                ParsedStatementRow(
                    row_index=len(parsed_rows),
                    date_vet=date_vet,
                    voucher_datetime_utc=dt_utc,
                    reference_number=ref_num,
                    concept=clean_concept or "Movimiento bancario",
                    movement_type=mov_type,
                    amount_ves=round(amount_ves, 2),
                    balance_ves=bal_val,
                    payment_method=_infer_payment_method(clean_concept),
                    amount_uncertain=amt_uncertain,
                )
            )
            if len(parsed_rows) >= MAX_STATEMENT_ROWS:
                warnings.append(f"Se alcanzó el límite de seguridad de {MAX_STATEMENT_ROWS} filas por archivo.")
                break

        return StatementPreviewResult(
            bank_name=detected_bank,
            file_type=normalized_file_type,
            extraction_method="TABULAR_AUTO" if not column_mapping else "TABULAR_MAPPED",
            detected_columns=[h for h in headers if h],
            needs_column_mapping=False,
            detected_order="UNKNOWN",
            opening_balance=None,
            closing_balance=None,
            balance_verified=False,
            balance_mismatch_count=0,
            total_rows=len(parsed_rows),
            p2p_matched_count=0,
            bank_fee_count=0,
            duplicate_count=0,
            unmatched_count=len(parsed_rows),
            rows=parsed_rows,
            warnings=warnings,
        )

    @staticmethod
    def _pdf_reader_has_fonts(reader: PdfReader, max_check_pages: int = 5) -> bool:
        """Detecta en <5 ms si el PDF declara alguna fuente nativa; evita perder minutos en PDFs escaneados o vectorizados."""
        for page in reader.pages[:max_check_pages]:
            try:
                res = page.get("/Resources")
                if res is None:
                    continue
                if hasattr(res, "get_object"):
                    res = res.get_object()
                if not isinstance(res, dict):
                    continue
                fonts = res.get("/Font")
                if fonts:
                    if hasattr(fonts, "get_object"):
                        fonts = fonts.get_object()
                    if isinstance(fonts, dict) and len(fonts) > 0:
                        return True
                xobjs = res.get("/XObject")
                if xobjs:
                    if hasattr(xobjs, "get_object"):
                        xobjs = xobjs.get_object()
                    if isinstance(xobjs, dict):
                        for xo in xobjs.values():
                            xo_obj = xo.get_object() if hasattr(xo, "get_object") else xo
                            if isinstance(xo_obj, dict) and str(xo_obj.get("/Subtype", "")) == "/Form":
                                xo_res = xo_obj.get("/Resources")
                                if xo_res is not None and hasattr(xo_res, "get_object"):
                                    xo_res = xo_res.get_object()
                                if isinstance(xo_res, dict) and xo_res.get("/Font"):
                                    return True
            except (PdfReadError, AttributeError, KeyError, TypeError, ValueError):
                return True
        return False

    def _parse_pdf_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> StatementPreviewResult:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except (PdfReadError, OSError, ValueError) as exc:
            raise ValueError(f"No se pudo abrir el PDF del estado de cuenta: {exc}") from exc

        if reader.is_encrypted:
            try:
                res = reader.decrypt("")
                if res == 0:
                    raise ValueError(
                        "El PDF está protegido con contraseña. Descárgalo sin clave para importarlo."
                    )
            except (PdfReadError, ValueError) as exc:
                raise ValueError("El PDF está protegido con contraseña.") from exc

        total_pages = len(reader.pages)
        warnings: list[str] = []
        if total_pages > MAX_PDF_PAGES:
            warnings.append(f"Se procesaron únicamente las primeras {MAX_PDF_PAGES} páginas del PDF.")

        # Atajo crítico para PDFs escaneados o con texto trazado en curvas (ej. Banesco/Mercantil sin /Font):
        # evita recorrer miles de curvas Bezier en pdfplumber antes de saltar al OCR local.
        has_native_fonts = self._pdf_reader_has_fonts(reader)
        if has_native_fonts:
            # 1. Extractor geométrico universal con pdfplumber (coordenadas reales X/Y por palabra, RAM acotada)
            (
                rows,
                detected_bank,
                eff_year,
                has_text_layer,
                extra_warnings,
                cover_summary,
            ) = self._extract_pdf_with_pdfplumber(
                file_bytes=file_bytes,
                filename=filename,
                bank_name_override=bank_name_override,
                default_year=default_year,
                progress_callback=progress_callback,
            )
            warnings.extend(extra_warnings)
            extraction_method = "PDF_PLUMBER_GEOMETRIC"
        else:
            rows = []
            detected_bank = (
                normalize_bank_name(bank_name_override)
                if bank_name_override and bank_name_override.strip()
                else (detect_bank_from_text(filename) or "BANCO DESCONOCIDO")
            )
            eff_year = default_year
            has_text_layer = False
            cover_summary = {}
            extraction_method = "PDF_PLUMBER_GEOMETRIC"

        # 2. Respaldo pypdf por líneas si el PDF tiene texto pero sin cabeceras estándar detectadas
        if not rows and has_text_layer:
            all_lines: list[str] = []
            for page in reader.pages[:MAX_PDF_PAGES]:
                try:
                    layout_txt = page.extract_text(extraction_mode="layout") or ""
                except (PdfReadError, ValueError, KeyError, AttributeError, TypeError):
                    layout_txt = page.extract_text() or ""
                if layout_txt.strip():
                    all_lines.extend(layout_txt.splitlines())
            if all_lines:
                rows = self._extract_rows_from_layout_lines(all_lines, eff_year)
                if rows:
                    extraction_method = "PDF_LAYOUT_UNIVERSAL"

        # Liberar árbol pypdf antes de pasar a OCR si aplica
        del reader

        # 3. OCR local gratuito y privado en streaming página-por-página (RAM constante + Tesseract quirúrgico)
        if not rows and not has_text_layer:
            ocr_res = self._extract_pdf_with_streaming_dual_ocr(
                file_bytes=file_bytes,
                filename=filename,
                bank_name_override=bank_name_override,
                default_year=eff_year,
                extra_warnings=warnings,
                progress_callback=progress_callback,
            )
            if ocr_res is not None and ocr_res.rows:
                return ocr_res

        # 4. Último respaldo IA multimodal (solo si falla OCR local o no hay librerías OCR y existe clave Gemini)
        if not rows and self._has_real_ai_key():
            ai_rows = self._fallback_extract_pdf_with_ai(file_bytes, eff_year, detected_bank)
            if ai_rows:
                rows = ai_rows
                extraction_method = "PDF_AI_FALLBACK"
            else:
                warnings.append(
                    "No se detectaron movimientos legibles en el PDF (ni por texto, OCR local ni IA)."
                )
        elif not rows:
            warnings.append(
                "No se encontraron filas tabulares con fechas y montos en el PDF "
                "(ni en texto nativo ni mediante OCR local)."
            )

        return StatementPreviewResult(
            bank_name=detected_bank,
            file_type="PDF",
            extraction_method=extraction_method,
            detected_columns=[],
            needs_column_mapping=False,
            detected_order="UNKNOWN",
            opening_balance=None,
            closing_balance=None,
            balance_verified=False,
            balance_mismatch_count=0,
            total_rows=len(rows),
            p2p_matched_count=0,
            bank_fee_count=0,
            duplicate_count=0,
            unmatched_count=len(rows),
            rows=rows,
            warnings=warnings,
            cover_summary=cover_summary,
        )

    def _parse_image_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
    ) -> StatementPreviewResult:
        """Extrae y concilia movimientos desde una captura de pantalla o foto (.png/.jpg/.webp) sin salir del VPS."""
        res = self._extract_with_dual_ocr(
            images=[sanitize_and_load_image(file_bytes, filename)],
            file_type="IMAGE",
            method_prefix="IMAGE_OCR",
            filename=filename,
            bank_name_override=bank_name_override,
            default_year=default_year,
            extra_warnings=[],
        )
        if not res.rows:
            res.warnings.append(
                "No se identificaron movimientos tabulares legibles en la imagen con RapidOCR/Tesseract."
            )
        return res

    def _run_ocr_engine_on_image(
        self,
        engine_name: Literal["rapidocr", "tesseract"],
        img: Image.Image,
    ) -> tuple[list[dict[str, Any]], float]:
        """Ejecuta un motor OCR sobre una sola imagen bajo el semáforo de concurrencia VPS."""
        custom_fn = self._ocr_engines.get(engine_name) if self._ocr_engines is not None else None
        if self._ocr_engines is not None and engine_name not in self._ocr_engines:
            return [], 0.0
        with _OCR_CONCURRENCY_SEMAPHORE:
            if custom_fn is not None:
                return custom_fn(img)
            if engine_name == "rapidocr":
                return _run_rapidocr_on_image(img)
            return _run_tesseract_on_image(img)

    def _build_ocr_preview_from_pages(
        self,
        pages_words: list[tuple[list[dict[str, Any]], float]],
        page_confs: list[float],
        engine_label: str,
        file_type: str,
        method_prefix: str,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
    ) -> tuple[StatementPreviewResult | None, float]:
        if not any(pw[0] for pw in pages_words):
            return None, 0.0

        valid_confs = [c for c, pw in zip(page_confs, pages_words, strict=False) if pw[0]]
        mean_conf = (sum(valid_confs) / len(valid_confs)) if valid_confs else 0.0
        rows, bank_name, _eff_year, extract_warnings, cover_summary = self._extract_rows_from_word_pages(
            pages_words=pages_words,
            filename=filename,
            bank_name_override=bank_name_override,
            default_year=default_year,
            y_tol=None,
        )
        res = StatementPreviewResult(
            bank_name=bank_name,
            file_type=file_type,
            extraction_method=f"{method_prefix}_{engine_label.upper()}",
            detected_columns=[],
            needs_column_mapping=False,
            detected_order="UNKNOWN",
            opening_balance=None,
            closing_balance=None,
            balance_verified=False,
            balance_mismatch_count=0,
            total_rows=len(rows),
            p2p_matched_count=0,
            bank_fee_count=0,
            duplicate_count=0,
            unmatched_count=len(rows),
            rows=rows,
            warnings=list(extract_warnings),
            cover_summary=cover_summary,
        )
        self._verify_and_classify_rows(res)
        return res, round(mean_conf, 4)

    @staticmethod
    def _identify_problematic_ocr_pages(
        res: StatementPreviewResult | None,
        page_confs: list[float],
        total_pages: int,
    ) -> list[int]:
        """Identifica únicamente los índices de página con descuadres, dudas o baja confianza para Tesseract quirúrgico."""
        if total_pages <= 1:
            return list(range(total_pages))
        if res is None or res.total_rows == 0:
            return list(range(total_pages))

        flagged: set[int] = set()
        for idx, conf in enumerate(page_confs):
            if conf < 0.78:
                flagged.add(idx)

        for r in res.rows:
            p_idx = r.source_page_idx
            if p_idx is None:
                continue
            if r.balance_ok is False:
                flagged.add(p_idx)
                # Un descuadre en la primera fila de la página N puede originarse en la página N-1
                if p_idx > 0:
                    flagged.add(p_idx - 1)
            elif r.amount_uncertain or r.reference_number == "S/R":
                flagged.add(p_idx)

        if not flagged and res.bank_name == "BANCO DESCONOCIDO":
            flagged.add(0)

        return sorted(p for p in flagged if 0 <= p < total_pages)

    def _extract_pdf_with_streaming_dual_ocr(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
        extra_warnings: list[str],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> StatementPreviewResult | None:
        """Ejecuta OCR local en streaming página-por-página (RAM constante) con respaldo Tesseract quirúrgico."""
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return None

        try:
            pdf_doc = pdfium.PdfDocument(file_bytes)
        except Exception:  # noqa: BLE001 - fallo de driver PDFium aislado fail-closed
            return None

        try:
            total_pages = min(len(pdf_doc), MAX_PDF_PAGES)
            if total_pages <= 0:
                return None

            rapid_pages: list[tuple[list[dict[str, Any]], float]] = []
            rapid_confs: list[float] = []
            for p_idx in range(total_pages):
                if progress_callback is not None:
                    progress_callback(p_idx + 1, total_pages, "OCR local")
                img = _render_single_pdf_page(pdf_doc, p_idx)
                if img is None:
                    rapid_pages.append(([], 612.0))
                    rapid_confs.append(0.0)
                    continue
                try:
                    words, conf = self._run_ocr_engine_on_image("rapidocr", img)
                finally:
                    img.close()
                rapid_pages.append((words, 612.0))
                rapid_confs.append(float(conf))
                if (p_idx + 1) % 10 == 0:
                    gc.collect()

            rapid_res, rapid_conf = self._build_ocr_preview_from_pages(
                pages_words=rapid_pages,
                page_confs=rapid_confs,
                engine_label="rapidocr",
                file_type="PDF",
                method_prefix="PDF_OCR",
                filename=filename,
                bank_name_override=bank_name_override,
                default_year=default_year,
            )

            tess_res: StatementPreviewResult | None = None
            tess_conf = 0.0
            if self._needs_second_ocr_opinion(rapid_res, rapid_conf):
                target_pages = self._identify_problematic_ocr_pages(rapid_res, rapid_confs, total_pages)
                hybrid_pages = list(rapid_pages)
                hybrid_confs = list(rapid_confs)
                ran_any = False
                for p_idx in target_pages:
                    img = _render_single_pdf_page(pdf_doc, p_idx)
                    if img is None:
                        continue
                    try:
                        t_words, t_conf = self._run_ocr_engine_on_image("tesseract", img)
                    finally:
                        img.close()
                    if t_words:
                        hybrid_pages[p_idx] = (t_words, 612.0)
                        hybrid_confs[p_idx] = float(t_conf)
                        ran_any = True
                if ran_any:
                    tess_res, tess_conf = self._build_ocr_preview_from_pages(
                        pages_words=hybrid_pages,
                        page_confs=hybrid_confs,
                        engine_label="tesseract",
                        file_type="PDF",
                        method_prefix="PDF_OCR",
                        filename=filename,
                        bank_name_override=bank_name_override,
                        default_year=default_year,
                    )

            return self._select_best_dual_ocr_result(
                rapid_res=rapid_res,
                rapid_conf=rapid_conf,
                tess_res=tess_res,
                tess_conf=tess_conf,
                file_type="PDF",
                method_prefix="PDF_OCR",
                filename=filename,
                bank_name_override=bank_name_override,
                extra_warnings=extra_warnings,
            )
        finally:
            pdf_doc.close()

    def _evaluate_ocr_candidate(
        self,
        engine_name: Literal["rapidocr", "tesseract"],
        images: list[Image.Image],
        file_type: str,
        method_prefix: str,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
    ) -> tuple[StatementPreviewResult | None, float]:
        """Ejecuta un motor OCR específico sobre las páginas y devuelve resultado verificado y confianza."""
        if self._ocr_engines is not None and engine_name not in self._ocr_engines:
            return None, 0.0

        pages_words: list[tuple[list[dict[str, Any]], float]] = []
        confs: list[float] = []
        for img in images:
            words, conf = self._run_ocr_engine_on_image(engine_name, img)
            pages_words.append((words, 612.0))
            confs.append(float(conf) if words else 0.0)

        return self._build_ocr_preview_from_pages(
            pages_words=pages_words,
            page_confs=confs,
            engine_label=engine_name,
            file_type=file_type,
            method_prefix=method_prefix,
            filename=filename,
            bank_name_override=bank_name_override,
            default_year=default_year,
        )

    @staticmethod
    def _needs_second_ocr_opinion(res: StatementPreviewResult | None, mean_conf: float) -> bool:
        """Determina si existen dudas que justifican invocar al segundo motor OCR para arbitraje."""
        if res is None or res.total_rows == 0:
            return True
        if res.balance_mismatch_count > 0:
            return True
        with_bal = sum(1 for r in res.rows if r.balance_ves is not None)
        if with_bal >= 2 and not res.balance_verified:
            return True
        if any(r.amount_uncertain or r.reference_number == "S/R" for r in res.rows):
            return True
        if res.bank_name == "BANCO DESCONOCIDO":
            return True
        return mean_conf < 0.78

    @staticmethod
    def _score_ocr_result(res: StatementPreviewResult | None, mean_conf: float) -> float:
        """Puntúa la calidad matemática y estructural de un candidato OCR."""
        if res is None or res.total_rows == 0:
            return -1000.0
        score = float(res.total_rows) * 40.0
        if res.balance_verified:
            score += 10000.0
        score -= float(res.balance_mismatch_count) * 1500.0
        uncertain_cnt = sum(1 for r in res.rows if r.amount_uncertain)
        sr_cnt = sum(1 for r in res.rows if r.reference_number == "S/R")
        score -= float(uncertain_cnt) * 25.0
        score -= float(sr_cnt) * 10.0
        if res.bank_name != "BANCO DESCONOCIDO":
            score += 200.0
        score += float(mean_conf) * 100.0
        return round(score, 2)

    def _attempt_row_level_ocr_consensus(
        self,
        primary: StatementPreviewResult,
        secondary: StatementPreviewResult,
        method_prefix: str,
    ) -> StatementPreviewResult | None:
        """Concilia filas puntuales con error en el ganador usando filas matemáticamente válidas del otro motor."""
        if not primary.rows or not secondary.rows:
            return None

        cand = copy.deepcopy(primary)
        p_chron = cand.rows if cand.detected_order == "ASC" else list(reversed(cand.rows))
        s_chron = secondary.rows if secondary.detected_order == "ASC" else list(reversed(secondary.rows))

        repaired_any = False
        for idx, pr in enumerate(p_chron):
            has_bal_issue = pr.balance_ok is False or pr.amount_uncertain
            if not has_bal_issue:
                continue

            prev_bal = p_chron[idx - 1].balance_ves if idx > 0 else None
            next_bal = p_chron[idx + 1].balance_ves if idx + 1 < len(p_chron) else None
            next_net = (
                (p_chron[idx + 1].amount_ves if p_chron[idx + 1].movement_type == "CREDIT" else -p_chron[idx + 1].amount_ves)
                if idx + 1 < len(p_chron)
                else None
            )

            matched_sec: ParsedStatementRow | None = None
            for sr in s_chron:
                same_date = sr.date_vet == pr.date_vet
                same_ref = (
                    pr.reference_number != "S/R"
                    and sr.reference_number != "S/R"
                    and sr.reference_number == pr.reference_number
                )
                if not (same_date and (same_ref or sr.movement_type == pr.movement_type)):
                    continue

                sr_net = sr.amount_ves if sr.movement_type == "CREDIT" else -sr.amount_ves
                fits_prev = True
                if prev_bal is not None and sr.balance_ves is not None:
                    fits_prev = abs((prev_bal + sr_net) - sr.balance_ves) <= 0.02
                fits_next = True
                if next_bal is not None and next_net is not None and sr.balance_ves is not None:
                    fits_next = abs((sr.balance_ves + next_net) - next_bal) <= 0.02

                if fits_prev and fits_next and sr.balance_ves is not None:
                    matched_sec = sr
                    break

            if matched_sec is not None:
                pr.amount_ves = matched_sec.amount_ves
                pr.movement_type = matched_sec.movement_type
                pr.balance_ves = matched_sec.balance_ves
                pr.amount_uncertain = False
                if pr.reference_number == "S/R" and matched_sec.reference_number != "S/R":
                    pr.reference_number = matched_sec.reference_number
                repaired_any = True

        if not repaired_any:
            return None

        cand.extraction_method = f"{method_prefix}_CONSENSUS"
        self._verify_and_classify_rows(cand)
        return cand

    def _select_best_dual_ocr_result(
        self,
        rapid_res: StatementPreviewResult | None,
        rapid_conf: float,
        tess_res: StatementPreviewResult | None,
        tess_conf: float,
        file_type: str,
        method_prefix: str,
        filename: str,
        bank_name_override: str | None,
        extra_warnings: list[str],
    ) -> StatementPreviewResult:
        """Elige el ganador matemático entre RapidOCR y Tesseract e intenta consenso fila-a-fila."""
        candidates: list[tuple[str, StatementPreviewResult, float]] = []
        if rapid_res is not None and rapid_res.total_rows > 0:
            candidates.append(("RapidOCR", rapid_res, self._score_ocr_result(rapid_res, rapid_conf)))
        if tess_res is not None and tess_res.total_rows > 0:
            candidates.append(("Tesseract", tess_res, self._score_ocr_result(tess_res, tess_conf)))

        if not candidates:
            fallback_bank = (
                normalize_bank_name(bank_name_override)
                if bank_name_override and bank_name_override.strip()
                else (detect_bank_from_text(filename) or "BANCO DESCONOCIDO")
            )
            return StatementPreviewResult(
                bank_name=fallback_bank,
                file_type=file_type,
                extraction_method=f"{method_prefix}_NONE",
                detected_columns=[],
                needs_column_mapping=False,
                detected_order="UNKNOWN",
                opening_balance=None,
                closing_balance=None,
                balance_verified=False,
                balance_mismatch_count=0,
                total_rows=0,
                p2p_matched_count=0,
                bank_fee_count=0,
                duplicate_count=0,
                unmatched_count=0,
                rows=[],
                warnings=list(extra_warnings),
            )

        candidates.sort(key=lambda it: it[2], reverse=True)
        winner_label, winner_res, winner_score = candidates[0]

        # Intentar consenso fila-a-fila si ambos motores extrajeron filas y aún queda duda o diferencias de cobertura
        if rapid_res is not None and tess_res is not None and rapid_res.total_rows > 0 and tess_res.total_rows > 0:
            other_res = tess_res if winner_res is rapid_res else rapid_res
            needs_consensus = (not winner_res.balance_verified) or (winner_res.total_rows < other_res.total_rows)
            if needs_consensus:
                best_cons: StatementPreviewResult | None = None
                best_cons_score = winner_score
                for base_res, helper_res in ((rapid_res, tess_res), (tess_res, rapid_res)):
                    cand_cons = self._attempt_row_level_ocr_consensus(base_res, helper_res, method_prefix)
                    if cand_cons is not None:
                        cand_sc = self._score_ocr_result(cand_cons, max(rapid_conf, tess_conf))
                        if cand_sc > best_cons_score:
                            best_cons_score = cand_sc
                            best_cons = cand_cons
                if best_cons is not None:
                    winner_label = "Consenso Dual-OCR"
                    winner_res = best_cons

            r_desc = f"RapidOCR ({rapid_res.total_rows} filas, {rapid_res.balance_mismatch_count} descuadres, {int(rapid_conf * 100)}% conf.)"
            t_desc = f"Tesseract ({tess_res.total_rows} filas, {tess_res.balance_mismatch_count} descuadres, {int(tess_conf * 100)}% conf.)"
            winner_res.warnings.append(
                f"Arbitraje OCR local: {r_desc} vs {t_desc} -> Seleccionado {winner_label}."
            )

        if extra_warnings:
            winner_res.warnings = [*extra_warnings, *winner_res.warnings]
        return winner_res

    def _extract_with_dual_ocr(
        self,
        images: list[Image.Image],
        file_type: str,
        method_prefix: str,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
        extra_warnings: list[str],
    ) -> StatementPreviewResult:
        """Orquesta RapidOCR + Tesseract 5 local con árbitro matemático y Tesseract quirúrgico multipágina."""
        rapid_pages: list[tuple[list[dict[str, Any]], float]] = []
        rapid_confs: list[float] = []
        if self._ocr_engines is None or "rapidocr" in self._ocr_engines:
            for img in images:
                words, conf = self._run_ocr_engine_on_image("rapidocr", img)
                rapid_pages.append((words, 612.0))
                rapid_confs.append(float(conf) if words else 0.0)
        rapid_res, rapid_conf = self._build_ocr_preview_from_pages(
            pages_words=rapid_pages,
            page_confs=rapid_confs,
            engine_label="rapidocr",
            file_type=file_type,
            method_prefix=method_prefix,
            filename=filename,
            bank_name_override=bank_name_override,
            default_year=default_year,
        )

        tess_res: StatementPreviewResult | None = None
        tess_conf = 0.0
        if self._needs_second_ocr_opinion(rapid_res, rapid_conf) and (
            self._ocr_engines is None or "tesseract" in self._ocr_engines
        ):
            if len(images) <= 1 or rapid_res is None or rapid_res.total_rows == 0:
                tess_res, tess_conf = self._evaluate_ocr_candidate(
                    engine_name="tesseract",
                    images=images,
                    file_type=file_type,
                    method_prefix=method_prefix,
                    filename=filename,
                    bank_name_override=bank_name_override,
                    default_year=default_year,
                )
            else:
                target_pages = self._identify_problematic_ocr_pages(rapid_res, rapid_confs, len(images))
                hybrid_pages = list(rapid_pages)
                hybrid_confs = list(rapid_confs)
                ran_any = False
                for p_idx in target_pages:
                    t_words, t_conf = self._run_ocr_engine_on_image("tesseract", images[p_idx])
                    if t_words:
                        hybrid_pages[p_idx] = (t_words, 612.0)
                        hybrid_confs[p_idx] = float(t_conf)
                        ran_any = True
                if ran_any:
                    tess_res, tess_conf = self._build_ocr_preview_from_pages(
                        pages_words=hybrid_pages,
                        page_confs=hybrid_confs,
                        engine_label="tesseract",
                        file_type=file_type,
                        method_prefix=method_prefix,
                        filename=filename,
                        bank_name_override=bank_name_override,
                        default_year=default_year,
                    )

        return self._select_best_dual_ocr_result(
            rapid_res=rapid_res,
            rapid_conf=rapid_conf,
            tess_res=tess_res,
            tess_conf=tess_conf,
            file_type=file_type,
            method_prefix=method_prefix,
            filename=filename,
            bank_name_override=bank_name_override,
            extra_warnings=extra_warnings,
        )

    @staticmethod
    def _infer_bank_from_concepts(rows: list[ParsedStatementRow]) -> str | None:
        """Identifica el banco emisor cuando el logo es una imagen pero los conceptos mencionan el riel propio."""
        issuer_signatures: tuple[tuple[tuple[str, ...], str], ...] = (
            (("PAGO MOVIL BNC", "PAGOMOVIL BNC", "PAGOMOVILBNC"), "BNC"),
            (("BANESCO PAGO MOVIL", "PAGOMOVIL BANESCO"), "BANESCO"),
            (("PAGOMOVIL BDV", "PAGOMOVILBDV", "BDVAPP", "BANCA MOVIL BDV"), "BANCO DE VENEZUELA"),
            (("TPAGO", "T-PAGO", "PAGO MOVIL MERCANTIL"), "MERCANTIL"),
            (("DINERO RAPIDO", "PROVINCIAL PAGO MOVIL"), "PROVINCIAL"),
            (("PAGO MOVIL BANCAMIGA", "PAGOMOVIL BANCAMIGA"), "BANCAMIGA"),
        )
        counts: dict[str, int] = {}
        for r in rows[:80]:
            upper = normalize_text(r.concept)
            for kws, official in issuer_signatures:
                if any(kw in upper for kw in kws):
                    counts[official] = counts.get(official, 0) + 1
        if not counts:
            return None
        return max(counts, key=lambda b: counts[b])

    def _extract_rows_from_word_pages(
        self,
        pages_words: list[tuple[list[dict[str, Any]], float]],
        filename: str,
        bank_name_override: str | None,
        default_year: int,
        y_tol: float | None = 2.6,
    ) -> tuple[list[ParsedStatementRow], str, int, list[str], dict[str, float | int | None]]:
        """Motor geométrico compartido por pdfplumber (PDF nativo) y RapidOCR/Tesseract (escaneados/imágenes).
        Soporta tanto tablas de 1 columna (BDV, BNC, Provincial) como PDFs apaisados de 2 paneles paralelos (Banesco, Mercantil).
        """
        warnings: list[str] = []
        rows: list[ParsedStatementRow] = []
        last_global_row: ParsedStatementRow | None = None
        last_global_full_desc: str = ""
        active_bands: list[_PdfColAnchor] | None = None
        active_table_x_min = 0.0
        active_split_x: float | None = None
        meta_lines: list[str] = []

        eff_year = default_year
        eff_month: int | None = None
        year_explicit = default_year != datetime.now(VET_TZ).year

        for p_idx, (raw_words, raw_page_w) in enumerate(pages_words[:MAX_PDF_PAGES]):
            if not raw_words:
                continue
            if y_tol is None:
                heights = sorted(
                    max(2.0, float(w["bottom"]) - float(w["top"]))
                    for w in raw_words
                )
                med_h = heights[len(heights) // 2] if heights else 8.0
                eff_y_tol = max(3.6, min(9.5, med_h * 0.55))
            else:
                eff_y_tol = y_tol

            page_w_full = float(raw_page_w or 612.0)
            panels, detected_split_x = _split_page_words_into_panels(
                words=raw_words,
                page_w=page_w_full,
                y_tol=eff_y_tol,
                prev_split_x=active_split_x,
            )
            if detected_split_x is not None:
                active_split_x = detected_split_x
            elif (
                len(panels) == 1
                and p_idx > 0
                and _detect_pdf_word_header(_group_words_into_lines(raw_words, y_tol=eff_y_tol)) is not None
            ):
                # Si una página posterior ya no es 2 columnas y tiene cabecera propia, reiniciar split
                active_split_x = None

            for panel_idx, (words, panel_w) in enumerate(panels):
                if not words:
                    continue
                wlines = _group_words_into_lines(words, y_tol=eff_y_tol)
                if not wlines:
                    continue

                hdr = _detect_pdf_word_header(wlines)
                if hdr is not None:
                    hdr_start, hdr_end, anchors = hdr
                    # Solo recortar panel izquierdo si estamos en página single-panel con tabla desplazada a la derecha (Banesco pág. 1)
                    table_x_min = (
                        max(0.0, anchors[0].hdr_x0 - 20.0)
                        if (len(panels) == 1 and anchors[0].hdr_x0 >= 120.0)
                        else 0.0
                    )
                    active_table_x_min = table_x_min
                    if p_idx == 0 and panel_idx == 0:
                        meta_lines.extend(ln.text for ln in wlines[:hdr_start])
                        if table_x_min > 0.0:
                            left_words = [w for w in words if float(w["x1"]) <= table_x_min]
                            meta_lines.extend(
                                ln.text for ln in _group_words_into_lines(left_words, y_tol=eff_y_tol)
                            )

                    if table_x_min > 0.0:
                        hdr_word_ids = {id(w) for ln in wlines[hdr_start:hdr_end] for w in ln.words}
                        hdr_bottom_v = wlines[hdr_end - 1].bottom
                        right_words = [
                            w
                            for w in words
                            if float(w["x0"]) >= table_x_min - 2.0
                            and float(w["top"]) > hdr_bottom_v - 1.5
                            and id(w) not in hdr_word_ids
                        ]
                        body_lines = _group_words_into_lines(right_words, y_tol=eff_y_tol)
                    else:
                        body_lines = wlines[hdr_end:]
                elif active_bands is not None and (p_idx > 0 or panel_idx > 0):
                    anchors = active_bands
                    if len(panels) == 1 and active_table_x_min > 0.0:
                        right_words = [w for w in words if float(w["x0"]) >= active_table_x_min - 2.0]
                        body_lines = _group_words_into_lines(right_words, y_tol=eff_y_tol)
                    else:
                        body_lines = wlines
                else:
                    # Portada sin tabla de movimientos (ej. Mercantil página 1): capturar todas las líneas de resumen
                    if p_idx == 0:
                        meta_lines.extend(ln.text for ln in wlines)
                    continue

                if p_idx == 0 and panel_idx == 0:
                    for wl in wlines[-5:]:
                        if _is_noise_or_footer_line(wl.text):
                            meta_lines.append(wl.text)
                    meta_sample = "\n".join(meta_lines) + f"\n{filename}"
                    parsed_yr, parsed_mo = _extract_period_year_month(meta_sample, eff_year)
                    if not year_explicit:
                        eff_year = parsed_yr
                    if parsed_mo is not None:
                        eff_month = parsed_mo
                elif p_idx == 1 and panel_idx == 0 and eff_month is None and meta_lines:
                    # Si la portada en pág. 1 no tenía tabla, recalcular año/mes con toda la portada acumulada
                    meta_sample = "\n".join(meta_lines) + f"\n{filename}"
                    parsed_yr, parsed_mo = _extract_period_year_month(meta_sample, eff_year)
                    if not year_explicit:
                        eff_year = parsed_yr
                    if parsed_mo is not None:
                        eff_month = parsed_mo

                bands = _calibrate_pdf_column_bands(
                    anchors,
                    body_lines,
                    panel_w,
                    allow_day_only=(eff_month is not None),
                )
                active_bands = bands

                page_anchors: list[dict[str, Any]] = []
                cont_candidates: list[dict[str, Any]] = []
                panel_last_date_vet: str | None = last_global_row.date_vet if last_global_row is not None else None

                for b_idx, wl in enumerate(body_lines):
                    if _is_noise_or_footer_line(wl.text):
                        continue
                    parsed = self._parse_pdf_word_line(
                        wl,
                        bands,
                        eff_year,
                        default_month=eff_month,
                        fallback_date_vet=panel_last_date_vet,
                    )
                    if parsed is not None:
                        panel_last_date_vet = str(parsed["row"].date_vet)
                        page_anchors.append(
                            {
                                "line_idx": b_idx,
                                "y_mid": wl.y_mid,
                                "row": parsed["row"],
                                "inline_concept": parsed["inline_concept"],
                                "has_inline": parsed["has_inline_concept"],
                                "top_parts": [],
                                "bottom_parts": [],
                            }
                        )
                    else:
                        cont_txt = self._extract_continuation_text(wl, bands)
                        if cont_txt:
                            cont_candidates.append(
                                {
                                    "line_idx": b_idx,
                                    "y_mid": wl.y_mid,
                                    "text": cont_txt,
                                }
                            )

                cross_page_parts: list[str] = []
                for cand in cont_candidates:
                    c_idx = int(cand["line_idx"])
                    c_y = float(cand["y_mid"])
                    c_txt = str(cand["text"])

                    prev_a = next(
                        (a for a in reversed(page_anchors) if int(a["line_idx"]) < c_idx),
                        None,
                    )
                    next_a = next((a for a in page_anchors if int(a["line_idx"]) > c_idx), None)

                    d_prev = (c_y - float(prev_a["y_mid"])) if prev_a is not None else 9999.0
                    d_next = (float(next_a["y_mid"]) - c_y) if next_a is not None else 9999.0

                    if (
                        next_a is not None
                        and not next_a["has_inline"]
                        and d_next <= 12.0
                        and d_next < d_prev
                    ):
                        next_a["top_parts"].append(c_txt)
                    elif prev_a is not None:
                        prev_a["bottom_parts"].append(c_txt)
                    elif last_global_row is not None:
                        cross_page_parts.append(c_txt)

                if cross_page_parts and last_global_row is not None:
                    full_prev_desc = f"{last_global_full_desc or last_global_row.concept} {' '.join(cross_page_parts)}"
                    last_global_full_desc = full_prev_desc
                    _enrich_row_metadata(last_global_row, full_prev_desc)
                    merged_prev = _sanitize_cell_text(full_prev_desc)
                    if merged_prev:
                        last_global_row.concept = merged_prev
                        last_global_row.payment_method = _infer_payment_method(full_prev_desc)

                for anch in page_anchors:
                    row_obj: ParsedStatementRow = anch["row"]
                    parts = [
                        *anch["top_parts"],
                        *([anch["inline_concept"]] if anch["inline_concept"] else []),
                        *anch["bottom_parts"],
                    ]
                    full_desc = re.sub(r"\s+", " ", " ".join(parts)).strip()
                    assembled = _sanitize_cell_text(full_desc)
                    if assembled:
                        if row_obj.reference_number == "S/R":
                            new_ref, new_conc = _extract_reference(assembled)
                            row_obj.reference_number = new_ref
                            row_obj.concept = new_conc or assembled
                        else:
                            row_obj.concept = assembled
                    _enrich_row_metadata(row_obj, full_desc or row_obj.concept)
                    row_obj.payment_method = _infer_payment_method(full_desc or row_obj.concept)
                    row_obj.source_page_idx = p_idx
                    row_obj.row_index = len(rows)
                    rows.append(row_obj)
                    last_global_row = row_obj
                    last_global_full_desc = full_desc or row_obj.concept
                    if len(rows) >= MAX_STATEMENT_ROWS:
                        warnings.append(
                            f"Se alcanzó el límite de seguridad de {MAX_STATEMENT_ROWS} movimientos."
                        )
                        break

                if len(rows) >= MAX_STATEMENT_ROWS:
                    break

            if len(rows) >= MAX_STATEMENT_ROWS:
                break

        meta_sample_all = "\n".join(meta_lines) + f"\n{filename}"
        cover_summary = _extract_cover_summary(meta_sample_all)
        detected_bank = (
            normalize_bank_name(bank_name_override)
            if bank_name_override and bank_name_override.strip()
            else (detect_bank_from_text(meta_sample_all) or "BANCO DESCONOCIDO")
        )
        if detected_bank == "BANCO DESCONOCIDO" and rows and not (bank_name_override and bank_name_override.strip()):
            inferred = self._infer_bank_from_concepts(rows)
            if inferred:
                detected_bank = inferred
        return rows, detected_bank, eff_year, warnings, cover_summary

    def _extract_pdf_with_pdfplumber(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> tuple[list[ParsedStatementRow], str, int, bool, list[str], dict[str, float | int | None]]:
        """Extrae palabras vectoriales con pdfplumber liberando caché por página (evita OOM en PDFs de 250+ págs.)."""
        try:
            pdf_doc = pdfplumber.open(io.BytesIO(file_bytes))
        except (PdfminerException, OSError, ValueError, TypeError, KeyError, AttributeError):
            fallback_bank = (
                normalize_bank_name(bank_name_override)
                if bank_name_override and bank_name_override.strip()
                else (detect_bank_from_text(filename) or "BANCO DESCONOCIDO")
            )
            return [], fallback_bank, default_year, False, [], {}

        pages_words: list[tuple[list[dict[str, Any]], float]] = []
        has_any_text = False
        with pdf_doc:
            page_slice = pdf_doc.pages[:MAX_PDF_PAGES]
            total_pages = len(page_slice)
            for p_idx, page in enumerate(page_slice):
                if progress_callback is not None:
                    progress_callback(p_idx + 1, total_pages, "Leyendo PDF")
                raw_words = (
                    page.extract_words(
                        keep_blank_chars=False,
                        use_text_flow=False,
                        x_tolerance=1.8,
                        y_tolerance=2.5,
                    )
                    or []
                )
                page_w = float(page.width or 612.0)
                # Conservar únicamente las 5 coordenadas necesarias y purgar caché interna de pdfplumber/pdfminer
                compact_words = [
                    {
                        "text": str(w.get("text", "")),
                        "x0": float(w.get("x0", 0.0)),
                        "x1": float(w.get("x1", 0.0)),
                        "top": float(w.get("top", 0.0)),
                        "bottom": float(w.get("bottom", 0.0)),
                    }
                    for w in raw_words
                ]
                if hasattr(page, "flush_cache"):
                    page.flush_cache()
                if hasattr(page, "get_textmap") and hasattr(page.get_textmap, "cache_clear"):
                    page.get_textmap.cache_clear()
                if compact_words:
                    has_any_text = True
                pages_words.append((compact_words, page_w))
                if (p_idx + 1) % 20 == 0:
                    gc.collect()
                # Corte temprano si las primeras 5 páginas de un PDF largo no tienen capa de texto
                if not has_any_text and p_idx >= 4 and total_pages > 10:
                    break

        if not has_any_text:
            fallback_bank = (
                normalize_bank_name(bank_name_override)
                if bank_name_override and bank_name_override.strip()
                else (detect_bank_from_text(filename) or "BANCO DESCONOCIDO")
            )
            return [], fallback_bank, default_year, False, [], {}

        rows, detected_bank, eff_year, warnings, cover_summary = self._extract_rows_from_word_pages(
            pages_words=pages_words,
            filename=filename,
            bank_name_override=bank_name_override,
            default_year=default_year,
            y_tol=2.6,
        )
        return rows, detected_bank, eff_year, True, warnings, cover_summary

    def _extract_continuation_text(self, wl: _PdfWordLine, bands: list[_PdfColAnchor]) -> str:
        """Extrae texto limpio de continuación permitiendo montos dentro de la descripción (Mercantil) pero nunca en columnas numéricas."""
        concept_bands = [b for b in bands if b.role == "concept"]
        num_bands = [b for b in bands if b.role in ("debit", "credit", "amount", "balance")]

        # Descartar líneas con montos en las columnas numéricas (son totales/saldos, no texto descriptivo)
        if num_bands:
            num_left = min(b.left for b in num_bands) - 8.0
            num_right = max(b.right for b in num_bands) + 12.0
            for w in wl.words:
                wtxt = str(w["text"]).strip()
                if not _MONEY_TOKEN_RE.fullmatch(wtxt):
                    continue
                wxc = (float(w["x0"]) + float(w["x1"])) / 2.0
                in_concept = any(cb.left - 2.0 <= wxc <= cb.right + 2.0 for cb in concept_bands)
                if not in_concept and num_left <= wxc <= num_right:
                    return ""
        elif _MONEY_TOKEN_RE.search(wl.text):
            return ""

        words_in = [
            str(w["text"]).strip()
            for w in wl.words
            if any(
                b.left - 4.0 <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= b.right + 4.0
                for b in concept_bands
            )
        ]
        if concept_bands and not words_in:
            return ""
        raw_txt = " ".join(words_in) if words_in else wl.text
        return _sanitize_cell_text(raw_txt, max_len=220)

    def _parse_pdf_word_line(
        self,
        wl: _PdfWordLine,
        bands: list[_PdfColAnchor],
        default_year: int,
        default_month: int | None = None,
        fallback_date_vet: str | None = None,
    ) -> dict[str, Any] | None:
        """Evalúa una línea visual contra las columnas calibradas y construye ParsedStatementRow si es ancla."""
        date_bands = [b for b in bands if b.role in ("date", "date_alt")]
        if not date_bands:
            return None

        num_bands = [b for b in bands if b.role in ("debit", "credit", "amount", "balance")]
        if not num_bands:
            return None

        num_left = min(b.left for b in num_bands) - 12.0
        num_right = max(b.right for b in num_bands) + 12.0
        concept_bands = [b for b in bands if b.role == "concept"]
        ref_bands = [b for b in bands if b.role == "reference"]
        type_bands = [b for b in bands if b.role == "type"]

        # Palabras monetarias dentro de las columnas numéricas (sin capturar montos en la descripción)
        money_words: list[dict[str, Any]] = []
        for w in wl.words:
            wtxt = str(w["text"]).strip()
            if not _MONEY_TOKEN_RE.fullmatch(wtxt):
                continue
            wxc = (float(w["x0"]) + float(w["x1"])) / 2.0
            in_concept = any(cb.left <= wxc <= cb.right for cb in concept_bands)
            if not in_concept and num_left <= wxc <= num_right:
                money_words.append(w)

        if not money_words:
            return None

        ref_words = [
            str(w["text"]).strip()
            for w in wl.words
            if any(rb.left - 4.0 <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= rb.right + 3.0 for rb in ref_bands)
            and re.search(r"\d", str(w["text"]))
        ]
        explicit_ref = " ".join(ref_words).strip() or None

        parsed_dt: tuple[str, datetime] | None = None
        for dband in date_bands:
            d_words = [
                str(w["text"]).strip()
                for w in wl.words
                if dband.left - 5.0 <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= dband.right + 5.0
            ]
            d_str = " ".join(d_words).strip()
            m_d = _DATE_ANY_RE.search(d_str)
            if not m_d and d_str and not re.search(r"[A-Za-z]{3}", d_str):
                # Normalizar confusiones OCR frecuentes solo en fechas numéricas cortas ("0l" -> "01", "O5" -> "05")
                d_ocr = d_str.translate(str.maketrans("OoIl|", "00111"))
                m_d = _DATE_ANY_RE.search(d_ocr) or re.search(
                    r"(?<![0-9/.,-])(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})",
                    d_ocr,
                )
            else:
                d_ocr = d_str
            if not m_d and d_str:
                # Rescate si una letra de Descripción quedó pegada sin espacio al inicio de la fecha
                m_d = re.search(
                    r"(?<![0-9/.,-])(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})",
                    d_str,
                )
            if m_d:
                cand_dt = _parse_vet_date(m_d.group(0).strip(), default_year)
                if cand_dt is not None:
                    parsed_dt = cand_dt
                    break
            elif default_month is not None and re.fullmatch(r"0?[1-9]|[12]\d|3[01]", d_ocr):
                cand_dt = _parse_vet_date(
                    f"{int(d_ocr):02d}/{default_month:02d}/{default_year}",
                    default_year,
                )
                if cand_dt is not None:
                    parsed_dt = cand_dt
                    break

        # Rescate seguro para tablas densas de 2 columnas (ej. Banesco OCR) donde se omitió el dígito DIA
        # pero la fila trae una referencia bancaria numérica explícita (>=6 dígitos) y monto + saldo.
        if (
            parsed_dt is None
            and default_month is not None
            and fallback_date_vet is not None
            and explicit_ref is not None
            and re.search(r"\d{6,}", explicit_ref)
            and len(money_words) >= 2
        ):
            parsed_dt = _parse_vet_date(fallback_date_vet, default_year)

        if parsed_dt is None:
            return None
        date_vet, dt_utc = parsed_dt

        assigned: dict[str, tuple[float, Literal["DEBIT", "CREDIT"] | None]] = {}
        bal_val: float | None = None
        rem_money = list(money_words)
        ordered_nums = sorted(num_bands, key=lambda b: b.anchor_xc)
        if ordered_nums[-1].role == "balance" and len(rem_money) >= 2:
            bw = rem_money.pop(-1)
            bal_val = _parse_signed_balance(str(bw["text"]))

        tx_num_bands = [b for b in ordered_nums if b.role != "balance"] or ordered_nums
        for mw in rem_money:
            mx1 = float(mw["x1"])
            mxc = (float(mw["x0"]) + mx1) / 2.0
            avail = [b for b in tx_num_bands if b.role not in assigned] or tx_num_bands
            best_b = min(
                avail,
                key=lambda b: min(abs(mx1 - b.anchor_x1), abs(mxc - b.anchor_xc)),
            )
            assigned[best_b.role] = _parse_signed_amount(str(mw["text"]))

        type_tokens = [
            str(w["text"]).strip()
            for w in wl.words
            if any(tb.left - 3.0 <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= tb.right + 3.0 for tb in type_bands)
        ]
        type_str = " ".join(type_tokens).strip()
        type_dir: Literal["DEBIT", "CREDIT"] | None = None
        if type_str:
            if _MOV_FLAG_DEBIT_RE.match(type_str):
                type_dir = "DEBIT"
            elif _MOV_FLAG_CREDIT_RE.match(type_str):
                type_dir = "CREDIT"

        debit_val = assigned["debit"][0] if "debit" in assigned else 0.0
        credit_val = assigned["credit"][0] if "credit" in assigned else 0.0
        if bal_val is None and "balance" in assigned:
            bal_val = assigned["balance"][0]
        amt_uncertain = False

        if debit_val == 0.0 and credit_val == 0.0 and "amount" in assigned:
            mag, sdir = assigned["amount"]
            eff_dir = type_dir or sdir
            if eff_dir == "DEBIT":
                debit_val = mag
            elif eff_dir == "CREDIT":
                credit_val = mag
            else:
                credit_val = mag
                amt_uncertain = True

        if debit_val <= 0.0 and credit_val <= 0.0:
            return None

        mov_type: Literal["DEBIT", "CREDIT"] = "DEBIT" if debit_val > 0.0 else "CREDIT"
        amt_val = debit_val if debit_val > 0.0 else credit_val

        concept_words = [
            str(w["text"]).strip()
            for w in wl.words
            if any(cb.left - 2.0 <= ((float(w["x0"]) + float(w["x1"])) / 2.0) <= cb.right + 2.0 for cb in concept_bands)
        ]
        inline_raw = " ".join(concept_words).strip()
        has_inline_concept = bool(inline_raw)

        ref_num, concept_clean = _extract_reference(inline_raw, explicit_ref=explicit_ref)
        row_obj = ParsedStatementRow(
            row_index=0,
            date_vet=date_vet,
            voucher_datetime_utc=dt_utc,
            reference_number=ref_num,
            concept=concept_clean or "Movimiento bancario",
            movement_type=mov_type,
            amount_ves=round(amt_val, 2),
            balance_ves=bal_val,
            payment_method=_infer_payment_method(concept_clean),
            amount_uncertain=amt_uncertain,
        )
        return {
            "row": row_obj,
            "inline_concept": concept_clean if has_inline_concept else "",
            "has_inline_concept": has_inline_concept,
        }

    @staticmethod
    def _strip_accents_preserve_len(text: str) -> str:
        """Elimina tildes en minúsculas preservando exactamente los índices horizontales de columna."""
        import unicodedata

        nfc = unicodedata.normalize("NFC", text)
        trans = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")
        return nfc.translate(trans).lower()

    def _detect_pdf_header_spans(self, line: str) -> dict[str, tuple[int, int]] | None:
        """Detecta posiciones horizontales (start, end) preservando espacios exactos en cabecera PDF."""
        lower = self._strip_accents_preserve_len(line)
        has_date = any(re.search(rf"(?<!\w){w}(?!\w)", lower) for w in ("fecha", "fec", "date", "dia"))
        has_amount = any(
            re.search(rf"(?<!\w){w}(?!\w)", lower)
            for w in (
                "cargos",
                "cargo",
                "debitos",
                "debito",
                "debe",
                "retiros",
                "retiro",
                "egresos",
                "egreso",
                "abonos",
                "abono",
                "creditos",
                "credito",
                "haber",
                "depositos",
                "deposito",
                "ingresos",
                "ingreso",
                "monto",
                "importe",
                "saldos",
                "saldo",
                "balance",
            )
        )
        if not (has_date and has_amount):
            return None

        spans: dict[str, tuple[int, int]] = {}
        token_roles: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("date", ("fecha oper", "fecha valor", "fecha", "fec", "date", "dia")),
            ("reference", ("referencia", "ref.", "ref", "comprobante", "serial", "documento", "movimiento")),
            ("type", ("mov", "tipo", "dc", "naturaleza", "signo")),
            ("debit", ("debitos", "debito", "debe", "cargos", "cargo", "retiros", "retiro", "egresos", "egreso", "salidas")),
            ("credit", ("creditos", "credito", "haber", "abonos", "abono", "depositos", "deposito", "ingresos", "ingreso", "entradas")),
            ("amount", ("monto", "importe", "valor", "amount")),
            ("balance", ("saldo disponible", "saldo actual", "saldo final", "saldos", "saldo", "balance")),
        )
        for role, kws in token_roles:
            for kw in kws:
                m = re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", lower)
                if m:
                    spans[role] = (m.start(), m.end())
                    break
        return spans if any(k in spans for k in ("debit", "credit", "amount", "balance")) else None

    def _extract_rows_from_layout_lines(self, lines: list[str], default_year: int) -> list[ParsedStatementRow]:
        """Fallback agnóstico al orden de columnas usando pypdf layout (cuando la fecha está en cualquier posición)."""
        col_spans: dict[str, tuple[int, int]] = {}
        rows: list[ParsedStatementRow] = []
        current_row: ParsedStatementRow | None = None

        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            if not stripped or re.fullmatch(r"[-=_*.\s]{3,}", stripped):
                continue

            detected_spans = self._detect_pdf_header_spans(line)
            if detected_spans:
                col_spans = detected_spans
                current_row = None
                continue

            if _is_noise_or_footer_line(stripped):
                current_row = None
                continue

            date_matches = list(_DATE_ANY_RE.finditer(line))
            m_date = None
            if date_matches:
                if "date" in col_spans:
                    ds, de = col_spans["date"]
                    d_center = (ds + de) / 2.0
                    m_date = min(
                        date_matches,
                        key=lambda m: abs(((m.start() + m.end()) / 2.0) - d_center),
                    )
                else:
                    m_date = date_matches[0]

            if m_date is not None:
                parsed_dt = _parse_vet_date(m_date.group(0).strip(), default_year)
                if not parsed_dt:
                    continue
                date_vet, dt_utc = parsed_dt

                money_matches = list(_MONEY_TOKEN_RE.finditer(line))
                if not money_matches:
                    continue

                first_money_start = money_matches[0].start()
                non_date_text = (line[: m_date.start()] + " " + line[m_date.end() : first_money_start]).strip()

                explicit_ref: str | None = None
                if "reference" in col_spans:
                    rs, re_end = col_spans["reference"]
                    for word_m in re.finditer(r"\S+", line[:first_money_start]):
                        if word_m.start() >= m_date.start() and word_m.end() <= m_date.end():
                            continue
                        if word_m.end() >= rs - 3 and word_m.start() <= re_end + 10:
                            cand = word_m.group(0)
                            if re.search(r"\d{4,}", cand):
                                explicit_ref = cand
                                non_date_text = (
                                    line[: word_m.start()]
                                    + " "
                                    + line[word_m.end() : first_money_start]
                                )
                                non_date_text = (
                                    non_date_text[: m_date.start()] + " " + non_date_text[m_date.end() :]
                                    if word_m.start() > m_date.end()
                                    else non_date_text
                                ).strip()
                                break

                ref_num, concept = _extract_reference(non_date_text, explicit_ref=explicit_ref)

                debit_val = 0.0
                credit_val = 0.0
                bal_val: float | None = None
                amt_uncertain = False

                if col_spans and any(k in col_spans for k in ("debit", "credit", "amount", "balance")):
                    numeric_cols: dict[str, tuple[int, int]] = {
                        k: col_spans[k] for k in ("debit", "credit", "amount", "balance") if k in col_spans
                    }
                    assigned: dict[str, tuple[float, Literal["DEBIT", "CREDIT"] | None]] = {}
                    remaining_matches = list(money_matches)

                    if "balance" in numeric_cols and len(remaining_matches) >= 2:
                        bal_mm = remaining_matches.pop(-1)
                        assigned["balance"] = (_parse_signed_balance(bal_mm.group(0)), None)

                    tx_cols: dict[str, tuple[int, int]] = {
                        k: v for k, v in numeric_cols.items() if k != "balance"
                    }
                    if not tx_cols:
                        tx_cols = numeric_cols

                    for mm in remaining_matches:
                        tok_start = mm.start(1)
                        tok_end = mm.end(1)
                        tok_center = (tok_start + tok_end) / 2.0
                        avail_roles = [r for r in tx_cols if r not in assigned] or list(tx_cols.keys())
                        best_role = min(
                            avail_roles,
                            key=lambda r: min(
                                abs(tok_end - tx_cols[r][1]),
                                abs(tok_center - (tx_cols[r][0] + tx_cols[r][1]) / 2.0),
                            ),
                        )
                        assigned[best_role] = _parse_signed_amount(mm.group(0))

                    if "debit" in assigned:
                        debit_val = assigned["debit"][0]
                    if "credit" in assigned:
                        credit_val = assigned["credit"][0]
                    if "balance" in assigned:
                        bal_val = assigned["balance"][0]
                    if debit_val == 0.0 and credit_val == 0.0 and "amount" in assigned:
                        mag, sdir = assigned["amount"]
                        if sdir == "DEBIT":
                            debit_val = mag
                        elif sdir == "CREDIT":
                            credit_val = mag
                        else:
                            credit_val = mag
                            amt_uncertain = True
                else:
                    parsed_moneys = [_parse_signed_amount(mm.group(0)) for mm in money_matches]
                    if len(parsed_moneys) >= 3:
                        debit_val = parsed_moneys[-3][0]
                        credit_val = parsed_moneys[-2][0]
                        bal_val = _parse_signed_balance(money_matches[-1].group(0))
                    elif len(parsed_moneys) == 2:
                        mag, sdir = parsed_moneys[0]
                        bal_val = _parse_signed_balance(money_matches[1].group(0))
                        if sdir == "DEBIT":
                            debit_val = mag
                        elif sdir == "CREDIT":
                            credit_val = mag
                        else:
                            credit_val = mag
                            amt_uncertain = True
                    else:
                        mag, sdir = parsed_moneys[0]
                        if sdir == "DEBIT":
                            debit_val = mag
                        else:
                            credit_val = mag
                            if sdir is None:
                                amt_uncertain = True

                if debit_val <= 0.0 and credit_val <= 0.0:
                    current_row = None
                    continue

                mov_type: Literal["DEBIT", "CREDIT"] = "DEBIT" if debit_val > 0.0 else "CREDIT"
                amt_val = debit_val if debit_val > 0.0 else credit_val

                new_row = ParsedStatementRow(
                    row_index=len(rows),
                    date_vet=date_vet,
                    voucher_datetime_utc=dt_utc,
                    reference_number=ref_num,
                    concept=concept or "Movimiento bancario",
                    movement_type=mov_type,
                    amount_ves=round(amt_val, 2),
                    balance_ves=bal_val,
                    payment_method=_infer_payment_method(concept),
                    amount_uncertain=amt_uncertain,
                )
                rows.append(new_row)
                current_row = new_row
                if len(rows) >= MAX_STATEMENT_ROWS:
                    break
            elif current_row is not None and not _MONEY_TOKEN_RE.search(line):
                extra = _sanitize_cell_text(stripped, max_len=120)
                if extra and len(current_row.concept) < 220:
                    merged = _sanitize_cell_text(f"{current_row.concept} {extra}")
                    current_row.concept = merged
                    current_row.payment_method = _infer_payment_method(merged)

        return rows

    def _call_gemini_for_pdf_chunk(
        self,
        chunk_bytes: bytes,
        default_year: int,
        bank_name: str,
        client: httpx.Client,
    ) -> list[ParsedStatementRow]:
        """Solicita a Gemini la extracción JSON estructurada de un bloque acotado de páginas PDF."""
        if len(chunk_bytes) > 6 * 1024 * 1024:
            return []
        prompt = (
            "Extrae TODAS las transacciones del estado de cuenta bancario adjunto. "
            "Responde UNICAMENTE con un arreglo JSON válido sin markdown ni texto adicional. "
            'Cada elemento debe tener: {"date": "YYYY-MM-DD", "reference": "...", '
            '"concept": "...", "debit": 0.0, "credit": 0.0, "balance": 0.0}.'
        )
        encoded = base64.b64encode(chunk_bytes).decode("ascii")
        for _ in range(min(3, len(self.key_pool.keys))):
            api_key = self.key_pool.get_next_key()
            for model in self.GEMINI_MODELS:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={api_key}"
                )
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "application/pdf", "data": encoded}},
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 16384},
                }
                try:
                    resp = client.post(url, json=payload)
                    if resp.status_code != 200:
                        continue
                    raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    m_arr = re.search(r"\[.*\]", raw_text, re.DOTALL)
                    if not m_arr:
                        continue
                    items = json.loads(m_arr.group(0))
                    if not isinstance(items, list):
                        continue
                    extracted: list[ParsedStatementRow] = []
                    for item in items[:MAX_STATEMENT_ROWS]:
                        if not isinstance(item, dict):
                            continue
                        p_dt = _parse_vet_date(str(item.get("date") or ""), default_year)
                        if not p_dt:
                            continue
                        deb = parse_monetary_amount(item.get("debit"))
                        cre = parse_monetary_amount(item.get("credit"))
                        if deb <= 0.0 and cre <= 0.0:
                            continue
                        mov_t: Literal["DEBIT", "CREDIT"] = "DEBIT" if deb > 0.0 else "CREDIT"
                        amt_v = deb if deb > 0.0 else cre
                        bal_raw = item.get("balance")
                        bal_v = _parse_signed_balance(bal_raw) if bal_raw is not None else None
                        ref_v, con_v = _extract_reference(
                            str(item.get("concept") or bank_name),
                            explicit_ref=str(item.get("reference") or "") or None,
                        )
                        extracted.append(
                            ParsedStatementRow(
                                row_index=len(extracted),
                                date_vet=p_dt[0],
                                voucher_datetime_utc=p_dt[1],
                                reference_number=ref_v,
                                concept=con_v or "Movimiento bancario",
                                movement_type=mov_t,
                                amount_ves=round(amt_v, 2),
                                balance_ves=bal_v,
                                payment_method=_infer_payment_method(con_v),
                            )
                        )
                    return extracted
                except (httpx.HTTPError, KeyError, ValueError, TypeError):
                    continue
        return []

    def _fallback_extract_pdf_with_ai(
        self,
        file_bytes: bytes,
        default_year: int,
        bank_name: str,
    ) -> list[ParsedStatementRow]:
        """Respaldo opcional vía Gemini en lotes de páginas para PDFs escaneados sin capa de texto."""
        chunks: list[bytes] = []
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            total_p = min(len(reader.pages), MAX_PDF_PAGES)
            if total_p <= PDF_AI_CHUNK_PAGES:
                chunks = [file_bytes]
            else:
                for start in range(0, total_p, PDF_AI_CHUNK_PAGES):
                    writer = PdfWriter()
                    for p in reader.pages[start : start + PDF_AI_CHUNK_PAGES]:
                        writer.add_page(p)
                    buf = io.BytesIO()
                    writer.write(buf)
                    chunks.append(buf.getvalue())
        except (PdfReadError, OSError, ValueError):
            chunks = [file_bytes]

        client = self._client or httpx.Client(timeout=45.0)
        close_client = self._client is None
        all_rows: list[ParsedStatementRow] = []
        try:
            for chunk_bytes in chunks:
                part_rows = self._call_gemini_for_pdf_chunk(
                    chunk_bytes=chunk_bytes,
                    default_year=default_year,
                    bank_name=bank_name,
                    client=client,
                )
                for r in part_rows:
                    r.row_index = len(all_rows)
                    all_rows.append(r)
                    if len(all_rows) >= MAX_STATEMENT_ROWS:
                        return all_rows
        finally:
            if close_client:
                client.close()
        return all_rows

    def _verify_and_classify_rows(self, result: StatementPreviewResult) -> None:
        """Verifica orden cronológico (ASC vs DESC), depura impresiones duplicadas sin cambio de saldo y cuadra fila a fila."""
        rows = result.rows
        if not rows:
            result.balance_verified = False
            return

        # 1. Inferir orden cronológico (ASC vs DESC)
        with_bal = [r for r in rows if r.balance_ves is not None]
        order = "ASC"
        if len(rows) >= 2 and len(with_bal) >= 2:
            asc_hits = 0
            desc_hits = 0
            for i in range(1, len(rows)):
                prev_b = rows[i - 1].balance_ves
                curr_b = rows[i].balance_ves
                if prev_b is None or curr_b is None:
                    continue
                net = rows[i].amount_ves if rows[i].movement_type == "CREDIT" else -rows[i].amount_ves
                if (
                    abs((prev_b + net) - curr_b) <= 0.02
                    or (rows[i].amount_uncertain and abs((prev_b - rows[i].amount_ves) - curr_b) <= 0.02)
                ):
                    asc_hits += 1

            for i in range(len(rows) - 2, -1, -1):
                prev_chron_b = rows[i + 1].balance_ves
                curr_chron_b = rows[i].balance_ves
                if prev_chron_b is None or curr_chron_b is None:
                    continue
                net = rows[i].amount_ves if rows[i].movement_type == "CREDIT" else -rows[i].amount_ves
                if (
                    abs((prev_chron_b + net) - curr_chron_b) <= 0.02
                    or (
                        rows[i].amount_uncertain
                        and abs((prev_chron_b - rows[i].amount_ves) - curr_chron_b) <= 0.02
                    )
                ):
                    desc_hits += 1

            if desc_hits > asc_hits or (asc_hits == desc_hits and rows[0].date_vet > rows[-1].date_vet):
                order = "DESC"
        elif len(rows) >= 2 and rows[0].date_vet > rows[-1].date_vet:
            order = "DESC"

        result.detected_order = order

        # 1b. Depurar duplicados consecutivos de impresión bancaria (ej. BDV 21/05 manteniendo saldo idéntico)
        chron_raw = rows if order == "ASC" else list(reversed(rows))
        dedup_chron: list[ParsedStatementRow] = []
        dup_print_dates: list[str] = []
        for r in chron_raw:
            if dedup_chron:
                prev_r = dedup_chron[-1]
                same_meta = (
                    r.date_vet == prev_r.date_vet
                    and r.reference_number != "S/R"
                    and r.reference_number == prev_r.reference_number
                    and r.movement_type == prev_r.movement_type
                    and abs(r.amount_ves - prev_r.amount_ves) <= 0.02
                    and normalize_text(r.concept) == normalize_text(prev_r.concept)
                )
                if (
                    same_meta
                    and prev_r.balance_ves is not None
                    and r.balance_ves is not None
                    and abs(r.balance_ves - prev_r.balance_ves) <= 0.02
                ):
                    dup_print_dates.append(r.date_vet)
                    continue
            dedup_chron.append(r)

        if dup_print_dates:
            rows = dedup_chron if order == "ASC" else list(reversed(dedup_chron))
            for idx, r in enumerate(rows):
                r.row_index = idx
            result.rows = rows
            result.total_rows = len(rows)
            result.warnings.append(
                f"Se omitió automáticamente {len(dup_print_dates)} fila(s) duplicada(s) impresa(s) "
                f"por el banco sin variación de saldo (fecha ref. {dup_print_dates[0]})."
            )

        # 2. Verificar matemáticamente transición cronológica de saldo
        chron_rows = rows if order == "ASC" else list(reversed(rows))
        with_bal = [r for r in rows if r.balance_ves is not None]
        if with_bal:
            first_bal = next((r.balance_ves for r in chron_rows if r.balance_ves is not None), None)
            last_bal = next((r.balance_ves for r in reversed(chron_rows) if r.balance_ves is not None), None)
            if first_bal is not None:
                first_row = next(r for r in chron_rows if r.balance_ves is not None)
                net0 = first_row.amount_ves if first_row.movement_type == "CREDIT" else -first_row.amount_ves
                result.opening_balance = round(first_bal - net0, 2)
            result.closing_balance = round(last_bal, 2) if last_bal is not None else None

        mismatches = 0
        prev_bal: float | None = None
        for r in chron_rows:
            if r.balance_ves is None:
                continue
            if prev_bal is not None:
                if r.amount_uncertain:
                    if abs((prev_bal + r.amount_ves) - r.balance_ves) <= 0.02:
                        r.movement_type = "CREDIT"
                        r.amount_uncertain = False
                    elif abs((prev_bal - r.amount_ves) - r.balance_ves) <= 0.02:
                        r.movement_type = "DEBIT"
                        r.amount_uncertain = False

                net = r.amount_ves if r.movement_type == "CREDIT" else -r.amount_ves
                expected_bal = round(prev_bal + net, 2)
                diff = round(r.balance_ves - expected_bal, 2)
                if abs(diff) <= 0.02:
                    r.balance_ok = True
                    r.balance_discrepancy = 0.0
                else:
                    r.balance_ok = False
                    r.balance_discrepancy = diff
                    mismatches += 1
            else:
                r.balance_ok = True
            prev_bal = r.balance_ves

        result.balance_mismatch_count = mismatches
        result.balance_verified = bool(len(with_bal) >= 2 and mismatches == 0)

        # 2b. Verificación contra resumen de portada (fundamental para Mercantil sin columna Saldo por fila y auditoría Banesco)
        cs = result.cover_summary or {}
        if cs:
            cs_open = cs.get("opening_balance")
            cs_close = cs.get("closing_balance")
            cs_cred_tot = cs.get("declared_credits_total")
            cs_deb_tot = cs.get("declared_debits_total")
            if result.opening_balance is None and isinstance(cs_open, (int, float)):
                result.opening_balance = round(float(cs_open), 2)
            if result.closing_balance is None and isinstance(cs_close, (int, float)):
                result.closing_balance = round(float(cs_close), 2)

            sum_credits = round(sum(r.amount_ves for r in rows if r.movement_type == "CREDIT"), 2)
            sum_debits = round(sum(r.amount_ves for r in rows if r.movement_type == "DEBIT"), 2)

            if len(with_bal) < 2 and isinstance(cs_open, (int, float)) and isinstance(cs_close, (int, float)):
                expected_close = round(float(cs_open) + sum_credits - sum_debits, 2)
                close_ok = abs(expected_close - float(cs_close)) <= 0.05
                cred_ok = (
                    not isinstance(cs_cred_tot, (int, float))
                    or abs(sum_credits - float(cs_cred_tot)) <= 0.05
                )
                deb_ok = (
                    not isinstance(cs_deb_tot, (int, float))
                    or abs(sum_debits - float(cs_deb_tot)) <= 0.05
                )
                if close_ok and cred_ok and deb_ok:
                    result.balance_verified = True
                elif isinstance(cs_deb_tot, (int, float)) or isinstance(cs_cred_tot, (int, float)):
                    decl_cnt = int(cs.get("declared_debits_count") or 0) + int(
                        cs.get("declared_credits_count") or 0
                    )
                    if decl_cnt > len(rows):
                        result.warnings.append(
                            f"Portada declara {decl_cnt} movimientos (Créditos Bs. {float(cs_cred_tot or 0.0):.2f}, "
                            f"Débitos Bs. {float(cs_deb_tot or 0.0):.2f}); se extrajeron {len(rows)} "
                            f"(Créditos Bs. {sum_credits:.2f}, Débitos Bs. {sum_debits:.2f})."
                        )

        # 3. Clasificación base sin BD (comisiones bancarias explícitas e implícitas 0.30% de Banesco Pago Móvil)
        fee_count = 0
        for idx, r in enumerate(chron_rows):
            if r.movement_type == "DEBIT" and _is_bank_fee_concept(r.concept):
                r.suggested_action = "BANK_FEE"
                r.bank_fee_ves = r.amount_ves
                r.notes = "Comisión bancaria deducible detectada"
                fee_count += 1
                continue

            # Comisión implícita Banesco: fila inmediata con misma ref y concepto "Banesco Pago Movil" (con o sin espacios OCR) por ~0.30%
            is_implicit_banesco_fee = False
            curr_compact = re.sub(r"\s+", "", normalize_text(r.concept))
            if (
                idx > 0
                and r.movement_type == "DEBIT"
                and r.reference_number != "S/R"
                and ("BANESCOPAGOMOVIL" in curr_compact or "PAGOMOVIL" in curr_compact)
            ):
                prev_r = chron_rows[idx - 1]
                prev_compact = re.sub(r"\s+", "", normalize_text(prev_r.concept))
                if (
                    prev_r.movement_type == "DEBIT"
                    and prev_r.suggested_action != "BANK_FEE"
                    and prev_r.date_vet == r.date_vet
                    and prev_r.reference_number == r.reference_number
                    and ("BANESCOPAGOMOVIL" in prev_compact or "PAGOMOVIL" in prev_compact)
                    and 0.0 < r.amount_ves < prev_r.amount_ves
                ):
                    expected_fee = round(prev_r.amount_ves * 0.003, 2)
                    tol = max(0.05, round(prev_r.amount_ves * 0.0005, 2))
                    if abs(r.amount_ves - expected_fee) <= tol:
                        is_implicit_banesco_fee = True

            if is_implicit_banesco_fee:
                r.suggested_action = "BANK_FEE"
                r.bank_fee_ves = r.amount_ves
                r.notes = "Comisión bancaria 0.30% Banesco Pago Móvil detectada"
                fee_count += 1
            else:
                r.suggested_action = "P2P_UNMATCHED"

        result.bank_fee_count = fee_count
        result.unmatched_count = len(rows) - fee_count

    def preview_from_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        db: Session,
        user_id: int | None,
        bank_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
        year_hint: int | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> StatementPreviewResult:
        """Parsea el estado de cuenta y lo cruza contra órdenes P2P y comprobantes previos del usuario en O(1)."""
        preview = self.parse_bytes(
            file_bytes=file_bytes,
            filename=filename,
            bank_name=bank_name,
            column_mapping=column_mapping,
            year_hint=year_hint,
            progress_callback=progress_callback,
        )
        if not preview.rows:
            return preview
        if progress_callback is not None:
            progress_callback(1, 1, "Conciliando órdenes P2P")

        voucher_repo = BankVoucherRepository(db, user_id=user_id)
        order_repo = OrderRepository(db, user_id=user_id)

        # Acotar consultas al rango real del extracto (±4 días) sin ningún límite truncado de 500/2000 filas
        row_dates = [r.voucher_datetime_utc for r in preview.rows]
        min_dt = (min(row_dates) - timedelta(days=4)).astimezone(UTC).replace(tzinfo=None)
        max_dt = (max(row_dates) + timedelta(days=4)).astimezone(UTC).replace(tzinfo=None)

        already_matched_orders = voucher_repo.list_associated_order_numbers(user_id=user_id)
        existing_vouchers = voucher_repo.list_by_date_range(min_dt, max_dt, user_id=user_id)
        completed_orders = [
            o
            for o in order_repo.list_completed(start_date=min_dt, end_date=max_dt, user_id=user_id)
            if str(o.order_number) not in already_matched_orders
        ]

        # Índices en memoria O(1) para alto volumen (6,000–25,000 movimientos/mes)
        existing_by_ref: dict[str, list[BankVoucher]] = {}
        for v in existing_vouchers:
            v_ref = normalize_reference(str(v.reference_number or ""))
            if v_ref != "S/R":
                existing_by_ref.setdefault(v_ref, []).append(v)

        orders_by_bucket: dict[tuple[str, int], list[Order]] = {}
        for ord_item in completed_orders:
            t_type = str(ord_item.trade_type or "").upper()
            amt_bucket = round(float(ord_item.fiat_amount or 0.0))
            orders_by_bucket.setdefault((t_type, amt_bucket), []).append(ord_item)

        dup_count = 0
        match_count = 0
        fee_count = 0
        unmatched_count = 0
        used_order_numbers: set[str] = set()

        for row in preview.rows:
            # 1. Deduplicación contra BankVoucher existentes del mismo usuario (O(1) por referencia)
            norm_ref = normalize_reference(row.reference_number)
            ref_candidates = existing_by_ref.get(norm_ref, existing_vouchers) if norm_ref != "S/R" else existing_vouchers
            if self._is_duplicate_voucher(row, preview.bank_name, ref_candidates):
                row.suggested_action = "DUPLICATE_EXISTING"
                row.notes = "Ya existe un comprobante con esta referencia/monto"
                dup_count += 1
                continue

            # 2. Comisiones bancarias deducibles + guardia anti-doble-comisión (Recibo previo + PDF)
            if row.suggested_action == "BANK_FEE":
                if self._is_fee_already_covered_by_existing_voucher(row, preview.bank_name, ref_candidates):
                    row.suggested_action = "DUPLICATE_EXISTING"
                    row.notes = "Comisión bancaria ya contabilizada en comprobante previo"
                    dup_count += 1
                    continue
                fee_count += 1
                continue

            # 3. Cruce multi-factorial por monto + sentido + banco + hora exacta VET + contraparte
            matched_order, confidence = self._find_best_order_match(
                row=row,
                orders=completed_orders,
                used_order_numbers=used_order_numbers,
                bank_name=preview.bank_name,
                orders_by_bucket=orders_by_bucket,
            )
            if matched_order is not None:
                used_order_numbers.add(str(matched_order.order_number))
                row.suggested_action = "P2P_MATCH"
                row.matched_order_number = str(matched_order.order_number)
                row.matched_order_type = str(matched_order.trade_type)
                row.matched_order_crypto = float(matched_order.crypto_amount or 0.0)
                row.matched_order_fiat = float(matched_order.fiat_amount or 0.0)
                row.match_confidence = confidence
                row.notes = f"Emparejada con orden {matched_order.order_number}"
                match_count += 1
            else:
                row.suggested_action = "P2P_UNMATCHED"
                unmatched_count += 1

        preview.duplicate_count = dup_count
        preview.p2p_matched_count = match_count
        preview.bank_fee_count = fee_count
        preview.unmatched_count = unmatched_count
        avail: list[dict[str, Any]] = []
        # Enviar hasta 500 órdenes pendientes del período ordenadas de más reciente a más antigua
        for ord_item in list(reversed(completed_orders))[:500]:
            o_dt = cast(datetime | None, ord_item.created_at)
            if o_dt is not None:
                o_vet = (
                    o_dt.replace(tzinfo=UTC).astimezone(VET_TZ)
                    if o_dt.tzinfo is None
                    else o_dt.astimezone(VET_TZ)
                )
                d_str = o_vet.strftime("%Y-%m-%d")
            else:
                d_str = "-"
            avail.append(
                {
                    "order_number": str(ord_item.order_number),
                    "trade_type": str(ord_item.trade_type),
                    "fiat_amount": round(float(ord_item.fiat_amount or 0.0), 2),
                    "crypto_amount": round(float(ord_item.crypto_amount or 0.0), 4),
                    "date_vet": d_str,
                }
            )
        preview.available_orders = avail
        return preview

    def _is_fee_already_covered_by_existing_voucher(
        self,
        row: ParsedStatementRow,
        bank_name: str,
        existing_vouchers: list[BankVoucher],
    ) -> bool:
        """Evita doble deducción en cuenta 5.2.01 si la comisión de esta referencia ya se imputó en un recibo previo."""
        norm_row_ref = normalize_reference(row.reference_number)
        if norm_row_ref == "S/R":
            return False
        norm_row_bank = normalize_bank_name(bank_name)
        row_day = datetime.strptime(row.date_vet, "%Y-%m-%d").date()

        for v in existing_vouchers:
            v_fee = float(v.bank_fee_ves or 0.0)
            if v_fee <= 0.0:
                continue
            v_ref = normalize_reference(str(v.reference_number or ""))
            if v_ref == "S/R" or not (
                norm_row_ref == v_ref or norm_row_ref.endswith(v_ref) or v_ref.endswith(norm_row_ref)
            ):
                continue
            if abs(v_fee - row.amount_ves) > max(0.05, row.amount_ves * 0.05):
                continue
            v_dt = cast(datetime | None, v.voucher_date) or cast(datetime | None, v.created_at)
            if v_dt is not None:
                v_vet_day = (
                    v_dt.replace(tzinfo=UTC).astimezone(VET_TZ).date()
                    if v_dt.tzinfo is None
                    else v_dt.astimezone(VET_TZ).date()
                )
                if abs((row_day - v_vet_day).days) > 3:
                    continue
            v_bank = normalize_bank_name(str(v.bank_name or ""))
            if v_bank in (norm_row_bank, "BANCO DESCONOCIDO") or norm_row_bank == "BANCO DESCONOCIDO":
                return True
        return False

    def _is_duplicate_voucher(
        self,
        row: ParsedStatementRow,
        bank_name: str,
        existing_vouchers: list[BankVoucher],
    ) -> bool:
        norm_row_bank = normalize_bank_name(bank_name)
        norm_row_ref = normalize_reference(row.reference_number)
        row_day = datetime.strptime(row.date_vet, "%Y-%m-%d").date()

        for v in existing_vouchers:
            if abs(float(v.amount_ves or 0.0) - row.amount_ves) > 0.05:
                continue
            if str(v.movement_type or "DEBIT").upper() != row.movement_type:
                continue

            v_ref = normalize_reference(str(v.reference_number or ""))
            ref_matches = (
                norm_row_ref != "S/R"
                and v_ref != "S/R"
                and (norm_row_ref == v_ref or norm_row_ref.endswith(v_ref) or v_ref.endswith(norm_row_ref))
            )
            if not ref_matches:
                continue

            v_dt = cast(datetime | None, v.voucher_date) or cast(datetime | None, v.created_at)
            if v_dt is not None:
                v_vet_day = (
                    v_dt.replace(tzinfo=UTC).astimezone(VET_TZ).date()
                    if v_dt.tzinfo is None
                    else v_dt.astimezone(VET_TZ).date()
                )
                if abs((row_day - v_vet_day).days) > 3:
                    continue

            v_bank = normalize_bank_name(str(v.bank_name or ""))
            if v_bank in (norm_row_bank, "BANCO DESCONOCIDO") or norm_row_bank == "BANCO DESCONOCIDO":
                return True
        return False

    def _find_best_order_match(
        self,
        row: ParsedStatementRow,
        orders: list[Order],
        used_order_numbers: set[str],
        bank_name: str = "BANCO DESCONOCIDO",
        orders_by_bucket: dict[tuple[str, int], list[Order]] | None = None,
    ) -> tuple[Order | None, float]:
        expected_trade = "BUY" if row.movement_type == "DEBIT" else "SELL"
        norm_stmt_bank = normalize_bank_name(bank_name)
        row_cp_words = (
            {w for w in normalize_text(row.counterparty_name).split() if len(w) >= 3}
            if row.counterparty_name
            else set()
        )
        row_cid_digits = re.sub(r"\D", "", row.sender_id or "")
        row_ref_clean = normalize_reference(row.reference_number)

        if orders_by_bucket is not None:
            base_amt = round(row.amount_ves)
            pool: list[Order] = []
            for b in (base_amt - 1, base_amt, base_amt + 1):
                pool.extend(orders_by_bucket.get((expected_trade, b), ()))
        else:
            pool = orders

        # Tupla ordenable: (score descendente, time_diff_sec ascendente)
        scored: list[tuple[float, float, int, Order]] = []
        row_day = datetime.strptime(row.date_vet, "%Y-%m-%d").date()
        row_utc_naive = (
            row.voucher_datetime_utc.astimezone(UTC).replace(tzinfo=None)
            if row.voucher_datetime_utc.tzinfo is not None
            else row.voucher_datetime_utc
        )

        for ord_item in pool:
            ord_num = str(ord_item.order_number)
            if ord_num in used_order_numbers:
                continue
            if str(ord_item.trade_type or "").upper() != expected_trade:
                continue
            if abs(float(ord_item.fiat_amount or 0.0) - row.amount_ves) > 0.05:
                continue

            o_dt = cast(datetime | None, ord_item.created_at)
            day_diff = 0
            time_diff_sec = 0.0
            if o_dt is not None:
                o_vet = (
                    o_dt.replace(tzinfo=UTC).astimezone(VET_TZ)
                    if o_dt.tzinfo is None
                    else o_dt.astimezone(VET_TZ)
                )
                day_diff = abs((o_vet.date() - row_day).days)
                if day_diff > 2:
                    continue
                o_utc_naive = o_dt.astimezone(UTC).replace(tzinfo=None) if o_dt.tzinfo is not None else o_dt
                time_diff_sec = abs((o_utc_naive - row_utc_naive).total_seconds())

            # Puntuación multi-factorial para desambiguar montos redondos repetidos (ej. 10x 100.000 Bs)
            score = 60.0 if day_diff == 0 else (50.0 if day_diff == 1 else 38.0)

            # Banco reportado por Binance vs Banco del estado de cuenta
            o_pm_raw = str(ord_item.payment_method or "").strip()
            if o_pm_raw and norm_stmt_bank != "BANCO DESCONOCIDO":
                o_bank = detect_bank_from_text(o_pm_raw)
                if o_bank is not None:
                    if o_bank == norm_stmt_bank:
                        score += 35.0
                    else:
                        # La orden explícitamente pertenece a OTRO banco venezolano distinto -> penalizar fuerte
                        score -= 45.0

            # Proximidad horaria exacta (Mercantil u otros con HH:MM:SS)
            if row.tx_time_vet and o_dt is not None:
                if time_diff_sec <= 1800.0:
                    score += 25.0
                elif time_diff_sec <= 10800.0:
                    score += 12.0

            # Nombre de contraparte o cédula
            o_cp_norm = normalize_text(cast(str | None, ord_item.counterparty_name))
            if o_cp_norm:
                if row_cp_words:
                    o_words = {w for w in o_cp_norm.split() if len(w) >= 3}
                    if row_cp_words & o_words:
                        score += 30.0
                if len(row_cid_digits) >= 6 and row_cid_digits in re.sub(r"\D", "", o_cp_norm):
                    score += 30.0

            # Referencia exacta en orden
            if row_ref_clean != "S/R" and len(row_ref_clean) >= 5 and row_ref_clean in ord_num:
                score += 40.0

            scored.append((score, -time_diff_sec, -day_diff, ord_item))

        if not scored:
            return None, 0.0

        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        best_score, _, neg_days, best_order = scored[0]
        # Si la única orden disponible pertenecía explícitamente a otro banco y no hubo señal adicional, no forzar cruce
        if best_score < 20.0:
            return None, 0.0
        best_days = -neg_days
        confidence = min(99.0, max(75.0, round(best_score, 1))) if best_days <= 1 else 78.0
        return best_order, confidence

    def commit_rows(
        self,
        db: Session,
        user_id: int | None,
        bank_name: str,
        rows: list[StatementCommitRow],
    ) -> StatementCommitResult:
        """Persiste las filas aprobadas en una sola transacción atómica por lotes preservando la cadena SHA-256."""
        from sqlalchemy.exc import SQLAlchemyError

        norm_bank = normalize_bank_name(bank_name)
        active_rows = [r for r in rows if r.action not in ("IGNORE", "DUPLICATE_EXISTING")]

        # 1. Fail-Closed: verificar si alguno de los períodos activos ya tiene cierre mensual sellado
        periods_to_touch = {r.date_vet[:7] for r in active_rows if len(r.date_vet) >= 7}
        for per in sorted(periods_to_touch):
            snap_q = db.query(FiscalPeriodSnapshot).filter(FiscalPeriodSnapshot.period == per)
            snap = _apply_user_scope(db, snap_q, FiscalPeriodSnapshot, user_id).first()
            if snap is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"El período fiscal {per} ya fue cerrado y sellado. "
                        "No se pueden importar movimientos sobre un mes cerrado (Fail-closed)."
                    ),
                )

        voucher_repo = BankVoucherRepository(db, user_id=user_id)
        order_repo = OrderRepository(db, user_id=user_id)
        acct_engine = AccountingEngine(db=db, user_id=user_id)

        # Cargar comprobantes previos acotados al rango real de fechas del lote (sin truncar a 2000)
        parsed_dates: list[datetime] = []
        for r in active_rows:
            p_dt = _parse_vet_date(r.date_vet, datetime.now(VET_TZ).year)
            parsed_dates.append(p_dt[1] if p_dt else datetime.now(UTC))

        if parsed_dates:
            min_dt = (min(parsed_dates) - timedelta(days=4)).astimezone(UTC).replace(tzinfo=None)
            max_dt = (max(parsed_dates) + timedelta(days=4)).astimezone(UTC).replace(tzinfo=None)
            existing_vouchers = voucher_repo.list_by_date_range(min_dt, max_dt, user_id=user_id)
        else:
            existing_vouchers = []

        existing_by_ref: dict[str, list[BankVoucher]] = {}
        for v in existing_vouchers:
            v_ref = normalize_reference(str(v.reference_number or ""))
            if v_ref != "S/R":
                existing_by_ref.setdefault(v_ref, []).append(v)

        # Pre-cargar órdenes referenciadas en el lote en bloques de 500 para eliminar N+1
        req_order_nums = list({r.order_number.strip() for r in active_rows if r.action == "P2P_MATCH" and r.order_number})
        orders_map: dict[str, Order] = {}
        for i in range(0, len(req_order_nums), 500):
            chunk = req_order_nums[i : i + 500]
            oq = db.query(Order).filter(Order.order_number.in_(chunk))
            for ord_obj in _apply_user_scope(db, oq, Order, user_id).all():
                orders_map[str(ord_obj.order_number)] = ord_obj

        # Inicializar punteros de cadena SHA-256 una sola vez antes del bucle atómico
        last_entry = acct_engine.journal_repo.get_last_entry(user_id=user_id)
        next_entry_number = int(last_entry.entry_number) + 1 if last_entry is not None else 1
        current_prev_hash = str(last_entry.entry_hash) if last_entry is not None else "0" * 64

        created_vouchers = 0
        matched_orders = 0
        bank_fees_recorded = 0
        internal_transfers_recorded = 0
        unmatched_recorded = 0
        ignored_rows = len(rows) - len(active_rows)
        journal_entries_created = 0

        try:
            for row, tx_dt in zip(active_rows, parsed_dates, strict=False):
                amt = round(float(row.amount_ves), 2)
                fee_amt = round(float(row.bank_fee_ves or (amt if row.action == "BANK_FEE" else 0.0)), 2)
                if amt <= 0.0 and fee_amt <= 0.0:
                    ignored_rows += 1
                    continue

                # Idempotencia O(1) ante reenvíos simultáneos o repetidos
                probe_row = ParsedStatementRow(
                    row_index=row.row_index,
                    date_vet=row.date_vet,
                    voucher_datetime_utc=tx_dt,
                    reference_number=row.reference_number,
                    concept=row.concept,
                    movement_type=row.movement_type,
                    amount_ves=amt,
                )
                norm_ref = normalize_reference(row.reference_number)
                cand_vouchers = (
                    existing_by_ref.get(norm_ref, existing_vouchers)
                    if norm_ref != "S/R"
                    else existing_vouchers
                )
                if self._is_duplicate_voucher(probe_row, norm_bank, cand_vouchers):
                    ignored_rows += 1
                    continue

                safe_ref = (norm_ref if row.reference_number else "S/R")[:50]
                if safe_ref == "S/R":
                    safe_ref = f"STMT-{row.date_vet.replace('-', '')}-{row.row_index}"[:50]
                safe_concept = _sanitize_cell_text(row.concept, max_len=255)

                matched_order: Order | None = None
                verif_status = "UNMATCHED"
                if row.action == "P2P_MATCH" and row.order_number:
                    ord_key = row.order_number.strip()
                    cand_order = orders_map.get(ord_key) or order_repo.get_by_order_number(ord_key, user_id=user_id)
                    if (
                        cand_order is not None
                        and str(getattr(cand_order, "order_status", "") or "").upper() == "COMPLETED"
                    ):
                        matched_order = cand_order
                        verif_status = "MATCHED"
                elif row.action in ("BANK_FEE", "INTERNAL_TRANSFER"):
                    verif_status = "MATCHED"

                stored_amount = amt
                total_deb = round(stored_amount + (fee_amt if row.action != "BANK_FEE" else 0.0), 2)

                voucher = BankVoucher(
                    user_id=user_id,
                    bank_name=norm_bank[:100],
                    reference_number=safe_ref,
                    amount_ves=stored_amount,
                    bank_fee_ves=fee_amt,
                    total_debited_ves=total_deb if row.movement_type == "DEBIT" else stored_amount,
                    concept=safe_concept or "Movimiento importado de estado de cuenta",
                    payment_method=(row.payment_method or "TRANSFERENCIA")[:30],
                    movement_type=row.movement_type,
                    associated_order_number=str(matched_order.order_number) if matched_order else None,
                    verification_status=verif_status,
                    reconciliation_score=100.0 if verif_status == "MATCHED" else 0.0,
                    voucher_date=tx_dt,
                )
                saved_voucher = voucher_repo.create(voucher, auto_commit=False)
                existing_vouchers.append(saved_voucher)
                if norm_ref != "S/R":
                    existing_by_ref.setdefault(norm_ref, []).append(saved_voucher)
                created_vouchers += 1

                if row.action == "BANK_FEE":
                    entries = acct_engine.record_bank_fee_voucher(
                        saved_voucher,
                        auto_commit=False,
                        entry_number_override=next_entry_number,
                        prev_hash_override=current_prev_hash,
                    )
                    bank_fees_recorded += 1
                elif row.action == "INTERNAL_TRANSFER":
                    entries = acct_engine.record_capital_transfer_voucher(
                        saved_voucher,
                        auto_commit=False,
                        entry_number_override=next_entry_number,
                        prev_hash_override=current_prev_hash,
                    )
                    internal_transfers_recorded += 1
                elif matched_order is not None:
                    entries = acct_engine.record_p2p_trade(
                        order=matched_order,
                        voucher=saved_voucher,
                        auto_commit=False,
                        entry_number_override=next_entry_number,
                        prev_hash_override=current_prev_hash,
                    )
                    matched_orders += 1
                else:
                    entries = acct_engine.record_unmatched_voucher(
                        voucher=saved_voucher,
                        auto_commit=False,
                        entry_number_override=next_entry_number,
                        prev_hash_override=current_prev_hash,
                    )
                    unmatched_recorded += 1

                if entries:
                    next_entry_number += 1
                    current_prev_hash = str(entries[-1].entry_hash)
                    journal_entries_created += len(entries)

            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise

        logger.info(
            f"Importación estado cuenta completada: banco={norm_bank}, creados={created_vouchers}, "
            f"p2p={matched_orders}, fees={bank_fees_recorded}, ignorados={ignored_rows}"
        )

        return StatementCommitResult(
            bank_name=norm_bank,
            created_vouchers=created_vouchers,
            matched_orders=matched_orders,
            bank_fees_recorded=bank_fees_recorded,
            internal_transfers_recorded=internal_transfers_recorded,
            unmatched_recorded=unmatched_recorded,
            ignored_rows=ignored_rows,
            journal_entries_created=journal_entries_created,
            periods_affected=sorted(periods_to_touch),
        )
