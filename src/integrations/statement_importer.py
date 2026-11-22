"""Importador Universal de Estados de Cuenta Bancarios (PDF, Excel, CSV, TXT) — SPEC-024.

Diseñado de forma agnóstica al banco para operar con cualquier entidad financiera venezolana
(Banesco, BDV, Mercantil, Provincial, Bancamiga, BNC, Exterior, Tesoro, Banplus, etc.)
o internacional, combinando extracción tabular local, alineación espacial PDF (pypdf layout),
verificación matemática Fail-Closed de saldo acumulado, deduplicación, cruce horario VET (UTC-4)
y respaldo opcional con IA multimodal para PDFs escaneados.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal, cast

import httpx
import pandas as pd
from fastapi import HTTPException, status
from pypdf import PdfReader
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

logger = logging.getLogger("statement_importer")

VET_TZ = timezone(timedelta(hours=-4))

MAX_STATEMENT_BYTES = 10 * 1024 * 1024  # 10 MB anti-DoS
MAX_STATEMENT_ROWS = 2500
MAX_PDF_PAGES = 60

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
        "nro. ref",
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

_PAGO_MOVIL_KEYWORDS: tuple[str, ...] = (
    "PAGO MOVIL",
    "PAGOMOVIL",
    "PAPM",
    "P.NAT",
    "P.JUR",
    "C2P",
    "P2C",
    "P2P MOVIL",
)

_NOISE_LINE_KEYWORDS: tuple[str, ...] = (
    "SALDO ANTERIOR",
    "SALDO INICIAL",
    "SALDO FINAL",
    "SALDO DE CIERRE",
    "TOTAL DEBITOS",
    "TOTAL CREDITOS",
    "TOTAL CARGOS",
    "TOTAL ABONOS",
    "RESUMEN DE MOVIMIENTOS",
    "PAGINA ",
    "PAGE ",
    "ESTADO DE CUENTA",
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
    return any(k in upper for k in _BANK_FEE_KEYWORDS)


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

    m_digits = re.search(r"(?<![\/\.-])\b(\d{5,16})\b(?![\/\.-])", text)
    if m_digits:
        ref_val = m_digits.group(1)
        cleaned = (text[: m_digits.start()] + " " + text[m_digits.end() :]).strip()
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
    return None


class BankStatementImporter:
    """Extractor, verificador matemático y conciliador universal de estados de cuenta bancarios."""

    GEMINI_MODELS: tuple[str, ...] = ("gemini-2.0-flash", "gemini-1.5-flash")

    def __init__(
        self,
        key_pool: AIKeyPool | None = None,
        http_client: httpx.Client | None = None,
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

    def _has_real_ai_key(self) -> bool:
        keys = getattr(self.key_pool, "keys", [])
        return any(k and k != "dummy_key" for k in keys)

    def _validate_upload(self, file_bytes: bytes, filename: str) -> str:
        """Valida tamaño, extensión y magic bytes (Fail-Closed)."""
        if not file_bytes:
            raise ValueError("El archivo de estado de cuenta está vacío.")
        if len(file_bytes) > MAX_STATEMENT_BYTES:
            raise ValueError("El archivo supera el límite máximo permitido de 10 MB.")

        ext = os.path.splitext((filename or "").lower())[1]
        if ext == ".pdf":
            head = file_bytes[:64].lstrip()
            if not head.startswith(b"%PDF-"):
                raise ValueError("El archivo PDF tiene cabecera o firma inválida (Fail-closed).")
            return "PDF"
        if ext == ".xlsx":
            if not file_bytes[:4].startswith(b"PK\x03\x04"):
                raise ValueError("El archivo Excel .xlsx no posee estructura ZIP válida.")
            return "XLSX"
        if ext == ".xls":
            return "XLS"
        if ext in (".csv", ".txt"):
            if b"\x00" in file_bytes[:4096]:
                raise ValueError("El archivo de texto/CSV contiene bytes binarios inválidos.")
            return "CSV"

        raise ValueError(
            f"Formato '{ext or 'desconocido'}' no soportado. Usa PDF, XLSX, XLS, CSV o TXT."
        )

    def parse_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
        year_hint: int | None = None,
    ) -> StatementPreviewResult:
        """Extrae movimientos bancarios desde PDF, Excel o CSV y valida su cuadre matemático."""
        file_type = self._validate_upload(file_bytes, filename)
        default_year = year_hint or datetime.now(VET_TZ).year

        if file_type in ("CSV", "XLSX", "XLS"):
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
            )

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

    def _read_excel_rows(self, file_bytes: bytes) -> list[list[str]]:
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
        raw_rows = self._decode_csv_rows(file_bytes) if file_type == "CSV" else self._read_excel_rows(file_bytes)
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
                file_type=file_type,
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
                bal_raw, _ = _parse_signed_amount(row[role_map["balance"]])
                bal_val = bal_raw

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
            file_type=file_type,
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

    def _parse_pdf_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        bank_name_override: str | None,
        default_year: int,
    ) -> StatementPreviewResult:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except (PdfReadError, OSError, ValueError) as exc:
            raise ValueError(f"No se pudo abrir el PDF del estado de cuenta: {exc}") from exc

        if reader.is_encrypted:
            try:
                res = reader.decrypt("")
                if res == 0:
                    raise ValueError("El PDF está protegido con contraseña. Descárgalo sin clave para importarlo.")
            except (PdfReadError, ValueError) as exc:
                raise ValueError("El PDF está protegido con contraseña.") from exc

        pages = reader.pages[:MAX_PDF_PAGES]
        warnings: list[str] = []
        if len(reader.pages) > MAX_PDF_PAGES:
            warnings.append(f"Se procesaron únicamente las primeras {MAX_PDF_PAGES} páginas del PDF.")

        all_lines: list[str] = []
        for page in pages:
            try:
                layout_txt = page.extract_text(extraction_mode="layout") or ""
            except (PdfReadError, ValueError, KeyError, AttributeError, TypeError):
                layout_txt = page.extract_text() or ""
            if layout_txt.strip():
                all_lines.extend(layout_txt.splitlines())

        header_lines: list[str] = []
        for ln in all_lines[:20]:
            if self._detect_pdf_header_spans(ln):
                break
            header_lines.append(ln)
        header_sample = "\n".join(header_lines or all_lines[:10]) + f"\n{filename}"
        detected_bank = (
            normalize_bank_name(bank_name_override)
            if bank_name_override and bank_name_override.strip()
            else (detect_bank_from_text(header_sample) or "BANCO DESCONOCIDO")
        )
        m_year = re.search(r"\b(20\d{2})\b", header_sample)
        eff_year = int(m_year.group(1)) if m_year and default_year == datetime.now(VET_TZ).year else default_year

        rows = self._extract_rows_from_layout_lines(all_lines, eff_year)
        extraction_method = "PDF_LAYOUT_UNIVERSAL"

        if not rows and self._has_real_ai_key():
            ai_rows = self._fallback_extract_pdf_with_ai(file_bytes, eff_year, detected_bank)
            if ai_rows:
                rows = ai_rows
                extraction_method = "PDF_AI_FALLBACK"
            else:
                warnings.append(
                    "No se detectaron movimientos legibles en el PDF (ni por texto ni por IA)."
                )
        elif not rows:
            warnings.append(
                "No se encontraron filas tabulares con fechas y montos en el PDF. "
                "Si el PDF es una imagen escaneada, configúrale una clave Gemini o expórtalo a CSV/Excel."
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
        )

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
        has_date = any(re.search(rf"(?<!\w){w}(?!\w)", lower) for w in ("fecha", "fec", "date"))
        has_amount = any(
            re.search(rf"(?<!\w){w}(?!\w)", lower)
            for w in ("cargos", "cargo", "debitos", "debito", "retiros", "retiro", "abonos", "abono", "creditos", "credito", "depositos", "deposito", "monto", "importe", "saldo", "balance")
        )
        if not (has_date and has_amount):
            return None

        spans: dict[str, tuple[int, int]] = {}
        token_roles: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("reference", ("referencia", "ref.", "ref", "comprobante", "serial", "documento", "movimiento")),
            ("debit", ("debitos", "debito", "cargos", "cargo", "retiros", "retiro", "egresos", "salidas")),
            ("credit", ("creditos", "credito", "abonos", "abono", "depositos", "deposito", "ingresos", "entradas")),
            ("amount", ("monto", "importe", "valor", "amount")),
            ("balance", ("saldo disponible", "saldo actual", "saldo final", "saldo", "balance")),
        )
        for role, kws in token_roles:
            for kw in kws:
                m = re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", lower)
                if m:
                    spans[role] = (m.start(), m.end())
                    break
        return spans if any(k in spans for k in ("debit", "credit", "amount", "balance")) else None

    def _extract_rows_from_layout_lines(self, lines: list[str], default_year: int) -> list[ParsedStatementRow]:
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

            upper_line = normalize_text(stripped)
            if any(upper_line.startswith(nk) or f" {nk}" in upper_line for nk in _NOISE_LINE_KEYWORDS):
                current_row = None
                continue

            m_date = _DATE_START_RE.match(line)
            if m_date:
                parsed_dt = _parse_vet_date(m_date.group(0).strip(), default_year)
                if not parsed_dt:
                    continue
                date_vet, dt_utc = parsed_dt

                money_matches = list(_MONEY_TOKEN_RE.finditer(line, pos=m_date.end()))
                if not money_matches:
                    continue

                first_money_start = money_matches[0].start()
                raw_mid = line[m_date.end() : first_money_start]
                middle_text = raw_mid.strip()

                explicit_ref: str | None = None
                if "reference" in col_spans:
                    rs, re_end = col_spans["reference"]
                    # Capturar palabra que cae cerca del span de Referencia
                    for word_m in re.finditer(r"\S+", raw_mid):
                        w_start = m_date.end() + word_m.start()
                        w_end = m_date.end() + word_m.end()
                        if w_end >= rs - 3 and w_start <= re_end + 8:
                            cand = word_m.group(0)
                            if re.search(r"\d{4,}", cand):
                                explicit_ref = cand
                                middle_text = (
                                    raw_mid[: word_m.start()] + " " + raw_mid[word_m.end() :]
                                ).strip()
                                break

                ref_num, concept = _extract_reference(middle_text, explicit_ref=explicit_ref)

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

                    # Si existe columna Saldo y hay >= 2 montos, el monto más a la derecha corresponde al Saldo
                    if "balance" in numeric_cols and len(remaining_matches) >= 2:
                        bal_mm = remaining_matches.pop(-1)
                        assigned["balance"] = _parse_signed_amount(bal_mm.group(0))

                    tx_cols: dict[str, tuple[int, int]] = {
                        k: v for k, v in numeric_cols.items() if k != "balance"
                    }
                    if not tx_cols:
                        tx_cols = numeric_cols

                    # Emparejamiento 1-a-1 sin colisión por proximidad horizontal
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
                    # Sin cabecera posicional: heurística universal según cantidad de montos a la derecha
                    parsed_moneys = [_parse_signed_amount(mm.group(0)) for mm in money_matches]
                    if len(parsed_moneys) >= 3:
                        debit_val = parsed_moneys[-3][0]
                        credit_val = parsed_moneys[-2][0]
                        bal_val = parsed_moneys[-1][0]
                    elif len(parsed_moneys) == 2:
                        mag, sdir = parsed_moneys[0]
                        bal_val = parsed_moneys[1][0]
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
                # Línea de continuación del concepto (ej. BDV "DESDE EL NUMERO ...")
                extra = _sanitize_cell_text(stripped, max_len=120)
                if extra and len(current_row.concept) < 220:
                    merged = _sanitize_cell_text(f"{current_row.concept} {extra}")
                    current_row.concept = merged
                    current_row.payment_method = _infer_payment_method(merged)

        return rows

    def _fallback_extract_pdf_with_ai(
        self,
        file_bytes: bytes,
        default_year: int,
        bank_name: str,
    ) -> list[ParsedStatementRow]:
        """Respaldo opcional vía Gemini para PDFs escaneados sin capa de texto."""
        if len(file_bytes) > 6 * 1024 * 1024:
            return []

        prompt = (
            "Extrae TODAS las transacciones del estado de cuenta bancario adjunto. "
            "Responde UNICAMENTE con un arreglo JSON válido sin markdown ni texto adicional. "
            'Cada elemento debe tener: {"date": "YYYY-MM-DD", "reference": "...", '
            '"concept": "...", "debit": 0.0, "credit": 0.0, "balance": 0.0}.'
        )
        encoded = base64.b64encode(file_bytes).decode("ascii")
        client = self._client or httpx.Client(timeout=25.0)
        close_client = self._client is None
        try:
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
                        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4096},
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
                            bal_v = parse_monetary_amount(bal_raw) if bal_raw is not None else None
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
        finally:
            if close_client:
                client.close()
        return []

    def _verify_and_classify_rows(self, result: StatementPreviewResult) -> None:
        """Verifica orden cronológico (ASC vs DESC), saldo fila por fila y clasificación base."""
        rows = result.rows
        if not rows:
            result.balance_verified = False
            return

        # 1. Inferir dirección en filas ambiguas (columna única sin signo) y detectar orden ASC/DESC
        with_bal = [r for r in rows if r.balance_ves is not None]
        order = "ASC"
        if len(rows) >= 2 and len(with_bal) >= 2:
            # Probar orden cronológico en sentido directo (0 -> N-1) vs inverso (N-1 -> 0)
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

        # 2. Verificar matemáticamente transición cronológica de saldo
        chron_rows = rows if order == "ASC" else list(reversed(rows))
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

        # 3. Clasificación base sin BD (comisiones bancarias)
        fee_count = 0
        for r in rows:
            if r.movement_type == "DEBIT" and _is_bank_fee_concept(r.concept):
                r.suggested_action = "BANK_FEE"
                r.bank_fee_ves = r.amount_ves
                r.notes = "Comisión bancaria deducible detectada"
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
    ) -> StatementPreviewResult:
        """Parsea el estado de cuenta y lo cruza contra órdenes P2P y comprobantes previos del usuario."""
        preview = self.parse_bytes(
            file_bytes=file_bytes,
            filename=filename,
            bank_name=bank_name,
            column_mapping=column_mapping,
            year_hint=year_hint,
        )
        if not preview.rows:
            return preview

        voucher_repo = BankVoucherRepository(db, user_id=user_id)
        order_repo = OrderRepository(db, user_id=user_id)

        existing_vouchers = voucher_repo.list_all(limit=2000, user_id=user_id)
        already_matched_orders: set[str] = {
            str(v.associated_order_number)
            for v in existing_vouchers
            if v.associated_order_number
        }
        completed_orders = [
            o
            for o in order_repo.list_completed(user_id=user_id)
            if str(o.order_number) not in already_matched_orders
        ]

        dup_count = 0
        match_count = 0
        fee_count = 0
        unmatched_count = 0
        used_order_numbers: set[str] = set()

        for row in preview.rows:
            # 1. Deduplicación contra BankVoucher existentes del mismo usuario
            if self._is_duplicate_voucher(row, preview.bank_name, existing_vouchers):
                row.suggested_action = "DUPLICATE_EXISTING"
                row.notes = "Ya existe un comprobante con esta referencia/monto"
                dup_count += 1
                continue

            # 2. Comisiones bancarias deducibles
            if row.suggested_action == "BANK_FEE":
                fee_count += 1
                continue

            # 3. Cruce por monto + dirección comercial (DEBIT=BUY, CREDIT=SELL) + proximidad VET
            matched_order, confidence = self._find_best_order_match(
                row=row,
                orders=completed_orders,
                used_order_numbers=used_order_numbers,
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
        for ord_item in completed_orders[:200]:
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
    ) -> tuple[Order | None, float]:
        expected_trade = "BUY" if row.movement_type == "DEBIT" else "SELL"
        candidates: list[tuple[float, float, Order]] = []

        for ord_item in orders:
            ord_num = str(ord_item.order_number)
            if ord_num in used_order_numbers:
                continue
            if abs(float(ord_item.fiat_amount or 0.0) - row.amount_ves) > 0.05:
                continue

            o_dt = cast(datetime | None, ord_item.created_at)
            day_diff = 0.0
            if o_dt is not None:
                o_vet = (
                    o_dt.replace(tzinfo=UTC).astimezone(VET_TZ)
                    if o_dt.tzinfo is None
                    else o_dt.astimezone(VET_TZ)
                )
                row_dt = datetime.strptime(row.date_vet, "%Y-%m-%d").replace(tzinfo=VET_TZ)
                day_diff = abs((o_vet.date() - row_dt.date()).days)
                if day_diff > 2:
                    continue

            same_dir_penalty = 0.0 if str(ord_item.trade_type or "").upper() == expected_trade else 10.0
            candidates.append((same_dir_penalty, day_diff, ord_item))

        if not candidates:
            return None, 0.0

        candidates.sort(key=lambda item: (item[0], item[1]))
        best_penalty, best_days, best_order = candidates[0]
        if best_penalty > 0.0:
            return None, 0.0
        confidence = 99.0 if best_days == 0 else (90.0 if best_days == 1 else 78.0)
        return best_order, confidence

    def commit_rows(
        self,
        db: Session,
        user_id: int | None,
        bank_name: str,
        rows: list[StatementCommitRow],
    ) -> StatementCommitResult:
        """Persiste las filas aprobadas por el usuario y genera sus asientos en partida doble."""
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

        existing_vouchers = voucher_repo.list_all(limit=2000, user_id=user_id)
        created_vouchers = 0
        matched_orders = 0
        bank_fees_recorded = 0
        internal_transfers_recorded = 0
        unmatched_recorded = 0
        ignored_rows = len(rows) - len(active_rows)
        journal_entries_created = 0

        for row in active_rows:
            parsed_dt = _parse_vet_date(row.date_vet, datetime.now(VET_TZ).year)
            tx_dt = parsed_dt[1] if parsed_dt else datetime.now(UTC)

            amt = round(float(row.amount_ves), 2)
            fee_amt = round(float(row.bank_fee_ves or (amt if row.action == "BANK_FEE" else 0.0)), 2)
            if amt <= 0.0 and fee_amt <= 0.0:
                ignored_rows += 1
                continue

            # Idempotencia ante reenvíos simultáneos o repetidos
            probe_row = ParsedStatementRow(
                row_index=row.row_index,
                date_vet=row.date_vet,
                voucher_datetime_utc=tx_dt,
                reference_number=row.reference_number,
                concept=row.concept,
                movement_type=row.movement_type,
                amount_ves=amt,
            )
            if self._is_duplicate_voucher(probe_row, norm_bank, existing_vouchers):
                ignored_rows += 1
                continue

            safe_ref = (normalize_reference(row.reference_number) if row.reference_number else "S/R")[:50]
            if safe_ref == "S/R":
                safe_ref = f"STMT-{row.date_vet.replace('-', '')}-{row.row_index}"[:50]
            safe_concept = _sanitize_cell_text(row.concept, max_len=255)

            matched_order: Order | None = None
            verif_status = "UNMATCHED"
            if row.action == "P2P_MATCH" and row.order_number:
                matched_order = order_repo.get_by_order_number(row.order_number.strip(), user_id=user_id)
                if matched_order is not None:
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
            saved_voucher = voucher_repo.create(voucher)
            existing_vouchers.append(saved_voucher)
            created_vouchers += 1

            if row.action == "BANK_FEE":
                entries = acct_engine.record_bank_fee_voucher(saved_voucher)
                bank_fees_recorded += 1
            elif row.action == "INTERNAL_TRANSFER":
                entries = acct_engine.record_capital_transfer_voucher(saved_voucher)
                internal_transfers_recorded += 1
            elif matched_order is not None:
                entries = acct_engine.record_p2p_trade(order=matched_order, voucher=saved_voucher)
                matched_orders += 1
            else:
                entries = acct_engine.record_unmatched_voucher(voucher=saved_voucher)
                unmatched_recorded += 1

            journal_entries_created += len(entries)

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
