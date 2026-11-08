"""Motor Contable Formal de Partida Doble: Libro Diario y Libro Mayor (SPEC-017).

Implementa la generación de asientos contables cronológicos con hash encadenado SHA-256
(prev_hash -> entry_hash) garantizando inmutabilidad y la ecuación contable (Total Debe = Total Haber),
así como la consolidación mensual del Libro Mayor con saldos iniciales y finales.
"""

import calendar
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.data.models import BankVoucher, JournalEntry, Order
from src.data.repositories import JournalEntryRepository


@dataclass
class LedgerSummary:
    """Resumen consolidado mensual para una cuenta en el Libro Mayor."""

    account_code: str
    account_name: str
    year: int
    month: int
    initial_balance: float
    total_debit: float
    total_credit: float
    final_balance: float
    entries_count: int


@dataclass
class BankBalanceItem:
    """Desglose de saldo inicial y teórico para un banco específico."""

    bank_name: str
    initial_ves: float
    inflows_ves: float
    outflows_ves: float
    theoretical_ves: float


@dataclass
class LiveBalanceSummary:
    """Resumen de saldos dinámicos en tiempo real sin requerir saldo final manual."""

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
    bank_breakdown: list[BankBalanceItem]



class AccountingEngine:
    """Motor contable de partida doble e inmutabilidad con SHA-256."""

    ACCOUNT_BANCO_VES = "1.1.01"
    ACCOUNT_USDT_ASSET = "1.1.05"
    ACCOUNT_BANK_FEE = "5.2.01"
    ACCOUNT_BINANCE_FEE = "5.1.02"
    ACCOUNT_UNMATCHED_DEBIT = "5.2.02"
    ACCOUNT_UNMATCHED_CREDIT = "2.1.09"

    def __init__(self, db: Session):
        self.db = db
        self.journal_repo = JournalEntryRepository(db)

    def _compute_hash(
        self,
        prev_hash: str,
        entry_number: int,
        date_time: datetime,
        account_code: str,
        debit: float,
        credit: float,
        reference: str,
    ) -> str:
        """Calcula el hash criptográfico SHA-256 encadenado del asiento contable."""
        payload = (
            f"{prev_hash}|{entry_number}|{date_time.isoformat()}|"
            f"{account_code}|{debit:.2f}|{credit:.2f}|{reference}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record_p2p_trade(
        self,
        order: Order,
        voucher: BankVoucher,
    ) -> list[JournalEntry]:
        """Genera el asiento contable formal de partida doble para una orden P2P conciliada con su comprobante."""
        if voucher.id is not None and order.order_number:
            existing_entries = (
                self.db.query(JournalEntry)
                .filter(
                    JournalEntry.voucher_id == voucher.id,
                    JournalEntry.order_number == order.order_number,
                )
                .order_by(JournalEntry.id.asc())
                .all()
            )
            if existing_entries:
                return existing_entries

        entry_number = self.journal_repo.get_next_entry_number()
        last_entry = self.journal_repo.get_last_entry()
        current_prev_hash: str = str(last_entry.entry_hash) if last_entry else "0" * 64

        trade_type = str(order.trade_type or "BUY").upper()
        amount_ves = float(voucher.amount_ves)
        bank_fee = float(voucher.bank_fee_ves or 0.0)
        dt = cast(datetime | None, voucher.voucher_date) or cast(datetime | None, order.created_at) or datetime.now(UTC)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)

        lines: list[dict[str, Any]] = []

        if trade_type == "BUY":
            # Compra USDT:
            # 1. DEBE 1.1.05 Activos Cripto USDT (Entrada de USDT valorada en VES)
            # 2. DEBE 5.2.01 Comisiones Bancarias (si hubo débito por transferencia interbancaria)
            # 3. HABER 1.1.01 Bancos Nacionales VES (Egreso total del banco = monto + comisión)
            lines.append({
                "account_code": self.ACCOUNT_USDT_ASSET,
                "account_name": "Activos Criptográficos - USDT",
                "debit": amount_ves,
                "credit": 0.0,
                "reference": str(voucher.reference_number or order.order_number),
                "description": (
                    f"Compra P2P {order.crypto_amount} USDT - Orden {order.order_number} "
                    f"- Ref {voucher.reference_number} - Titular: {voucher.sender_name or 'N/A'}"
                ),
            })

            if bank_fee > 0.0:
                lines.append({
                    "account_code": self.ACCOUNT_BANK_FEE,
                    "account_name": "Gastos Financieros - Comisiones Bancarias",
                    "debit": bank_fee,
                    "credit": 0.0,
                    "reference": str(voucher.reference_number),
                    "description": f"Comisión bancaria débito P2P - Ref {voucher.reference_number}",
                })

            lines.append({
                "account_code": self.ACCOUNT_BANCO_VES,
                "account_name": f"Banco Nacional VES - {voucher.bank_name or 'Comercial'}",
                "debit": 0.0,
                "credit": round(amount_ves + bank_fee, 2),
                "reference": str(voucher.reference_number or order.order_number),
                "description": (
                    f"Egreso bancario compra P2P - Ref {voucher.reference_number} "
                    f"- Banco: {voucher.bank_name or 'Desconocido'}"
                ),
            })

        else:
            # Venta USDT:
            # 1. DEBE 1.1.01 Bancos Nacionales VES (Ingreso de fondos en banco)
            # 2. HABER 1.1.05 Activos Cripto USDT (Salida de inventario de USDT)
            lines.append({
                "account_code": self.ACCOUNT_BANCO_VES,
                "account_name": f"Banco Nacional VES - {voucher.bank_name or 'Comercial'}",
                "debit": amount_ves,
                "credit": 0.0,
                "reference": str(voucher.reference_number or order.order_number),
                "description": (
                    f"Ingreso bancario venta P2P - Orden {order.order_number} "
                    f"- Ref {voucher.reference_number} - De: {voucher.sender_name or 'N/A'}"
                ),
            })

            lines.append({
                "account_code": self.ACCOUNT_USDT_ASSET,
                "account_name": "Activos Criptográficos - USDT",
                "debit": 0.0,
                "credit": amount_ves,
                "reference": str(voucher.reference_number or order.order_number),
                "description": (
                    f"Venta P2P {order.crypto_amount} USDT - Orden {order.order_number} "
                    f"- Ref {voucher.reference_number}"
                ),
            })

        created_entries: list[JournalEntry] = []
        for line in lines:
            safe_ref = str(line["reference"])[:50]
            safe_acc_name = str(line["account_name"])[:100]
            entry_hash = self._compute_hash(
                prev_hash=current_prev_hash,
                entry_number=entry_number,
                date_time=dt,
                account_code=line["account_code"],
                debit=line["debit"],
                credit=line["credit"],
                reference=safe_ref,
            )

            entry = JournalEntry(
                entry_number=entry_number,
                date_time=dt,
                account_code=line["account_code"],
                account_name=safe_acc_name,
                debit=line["debit"],
                credit=line["credit"],
                reference=safe_ref,
                description=line["description"],
                voucher_id=voucher.id,
                order_number=order.order_number,
                prev_hash=current_prev_hash,
                entry_hash=entry_hash,
            )

            saved = self.journal_repo.create_entry(entry)
            created_entries.append(saved)
            current_prev_hash = entry_hash

        return created_entries

    def record_unmatched_voucher(self, voucher: BankVoucher) -> list[JournalEntry]:
        """Asienta un comprobante no conciliado como partida independiente sin forzar emparejamiento."""
        entry_number = self.journal_repo.get_next_entry_number()
        last_entry = self.journal_repo.get_last_entry()
        current_prev_hash: str = str(last_entry.entry_hash) if last_entry else "0" * 64

        amount_ves = float(voucher.amount_ves)
        bank_fee = float(voucher.bank_fee_ves or 0.0)
        mov_type = str(voucher.movement_type or "DEBIT").upper()
        dt = cast(datetime | None, voucher.voucher_date) or datetime.now(UTC)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)

        lines: list[dict[str, Any]] = []

        if mov_type == "DEBIT":
            lines.append({
                "account_code": self.ACCOUNT_UNMATCHED_DEBIT,
                "account_name": "Egresos Bancarios por Identificar / Partida no Conciliada",
                "debit": amount_ves,
                "credit": 0.0,
                "reference": str(voucher.reference_number),
                "description": f"Débito bancario no vinculado - Ref {voucher.reference_number}",
            })
            if bank_fee > 0.0:
                lines.append({
                    "account_code": self.ACCOUNT_BANK_FEE,
                    "account_name": "Gastos Financieros - Comisiones Bancarias",
                    "debit": bank_fee,
                    "credit": 0.0,
                    "reference": str(voucher.reference_number),
                    "description": f"Comisión bancaria débito no conciliado - Ref {voucher.reference_number}",
                })
            lines.append({
                "account_code": self.ACCOUNT_BANCO_VES,
                "account_name": f"Banco Nacional VES - {voucher.bank_name or 'Comercial'}",
                "debit": 0.0,
                "credit": round(amount_ves + bank_fee, 2),
                "reference": str(voucher.reference_number),
                "description": f"Egreso bancario no vinculado - Ref {voucher.reference_number}",
            })
        else:
            lines.append({
                "account_code": self.ACCOUNT_BANCO_VES,
                "account_name": f"Banco Nacional VES - {voucher.bank_name or 'Comercial'}",
                "debit": amount_ves,
                "credit": 0.0,
                "reference": str(voucher.reference_number),
                "description": f"Ingreso bancario no vinculado - Ref {voucher.reference_number}",
            })
            lines.append({
                "account_code": self.ACCOUNT_UNMATCHED_CREDIT,
                "account_name": "Pasivos / Ingresos por Identificar",
                "debit": 0.0,
                "credit": amount_ves,
                "reference": str(voucher.reference_number),
                "description": f"Depósito no conciliado P2P - Ref {voucher.reference_number}",
            })

        created: list[JournalEntry] = []
        for line in lines:
            entry_hash = self._compute_hash(
                prev_hash=current_prev_hash,
                entry_number=entry_number,
                date_time=dt,
                account_code=line["account_code"],
                debit=line["debit"],
                credit=line["credit"],
                reference=line["reference"],
            )

            entry = JournalEntry(
                entry_number=entry_number,
                date_time=dt,
                account_code=line["account_code"],
                account_name=line["account_name"],
                debit=line["debit"],
                credit=line["credit"],
                reference=line["reference"],
                description=line["description"],
                voucher_id=voucher.id,
                prev_hash=current_prev_hash,
                entry_hash=entry_hash,
            )
            saved = self.journal_repo.create_entry(entry)
            created.append(saved)
            current_prev_hash = entry_hash

        return created

    def calculate_ledger_for_account(
        self,
        account_code: str,
        year: int,
        month: int,
        initial_balance: float = 0.0,
    ) -> LedgerSummary:
        """Consolida el Libro Mayor para una cuenta contable específica en el mes solicitado."""
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1, 0, 0, 0)
        end_date = datetime(year, month, last_day, 23, 59, 59, 999999)

        entries = self.journal_repo.list_entries(
            start_date=start_date,
            end_date=end_date,
            account_code=account_code,
        )

        total_debit = sum(float(e.debit) for e in entries)
        total_credit = sum(float(e.credit) for e in entries)

        # Regla contable: Activos (1.) y Egresos/Gastos (5., 6.) aumentan por el Debe y disminuyen por el Haber
        # Pasivos (2.), Patrimonio (3.) e Ingresos (4.) aumentan por el Haber y disminuyen por el Debe
        if account_code.startswith(("1.", "5.", "6.")):
            final_balance = initial_balance + total_debit - total_credit
        else:
            final_balance = initial_balance + total_credit - total_debit

        account_name: str = str(entries[0].account_name) if entries else f"Cuenta {account_code}"

        return LedgerSummary(
            account_code=account_code,
            account_name=account_name,
            year=year,
            month=month,
            initial_balance=round(initial_balance, 2),
            total_debit=round(total_debit, 2),
            total_credit=round(total_credit, 2),
            final_balance=round(final_balance, 2),
            entries_count=len(entries),
        )

    def get_monthly_ledger_report(
        self,
        year: int,
        month: int,
        initial_balances: dict[str, float] | None = None,
    ) -> list[LedgerSummary]:
        """Genera el reporte consolidado de Libro Mayor para las principales cuentas del negocio."""
        balances = initial_balances or {}
        core_accounts = [
            (self.ACCOUNT_BANCO_VES, "Banco Nacional VES"),
            (self.ACCOUNT_USDT_ASSET, "Activos Criptográficos - USDT"),
            (self.ACCOUNT_BANK_FEE, "Gastos Financieros - Comisiones Bancarias"),
            (self.ACCOUNT_BINANCE_FEE, "Gastos Operativos - Comisiones Binance P2P"),
        ]

        summaries: list[LedgerSummary] = []
        for code, _ in core_accounts:
            init_bal = balances.get(code, 0.0)
            summary = self.calculate_ledger_for_account(
                account_code=code,
                year=year,
                month=month,
                initial_balance=init_bal,
            )
            summaries.append(summary)

        return summaries

    def get_live_theoretical_balance(
        self,
        year: int,
        month: int,
        initial_balances: dict[str, Any] | None = None,
    ) -> LiveBalanceSummary:
        """Calcula el saldo teórico en tiempo real (Inflow - Outflow) desglosado por banco y USDT."""
        cfg = initial_balances or {}
        init_usdt = float(cfg.get("crypto_usdt", 0.0))
        explicit_banks_cfg: dict[str, float] = dict(cfg.get("banks") or {})
        has_explicit_banks = bool(explicit_banks_cfg)
        banks_cfg: dict[str, float] = dict(explicit_banks_cfg)

        # Si el usuario solo colocó un saldo general en bolívares sin desglose
        if not banks_cfg and "total_ves" in cfg:
            banks_cfg = {"Banco Principal": float(cfg["total_ves"])}
        elif not banks_cfg and "1.1.01" in cfg:
            banks_cfg = {"Banco Principal": float(cfg["1.1.01"])}

        days_in_month = calendar.monthrange(year, month)[1]
        start_date = datetime(year, month, 1, 0, 0, 0)
        end_date = datetime(year, month, days_in_month, 23, 59, 59, 999999)

        # 1. Movimientos Cripto (USDT) desde órdenes completadas
        orders = (
            self.db.query(Order)
            .filter(
                Order.order_status == "COMPLETED",
                Order.created_at.between(start_date, end_date),
            )
            .all()
        )

        inflow_usdt = 0.0
        outflow_usdt = 0.0
        for o in orders:
            t_type = getattr(o, "trade_type", getattr(o, "order_type", ""))
            c_amount = float(getattr(o, "crypto_amount", getattr(o, "amount_crypto", 0.0)))
            if t_type == "BUY":
                inflow_usdt += c_amount
            elif t_type == "SELL":
                outflow_usdt += c_amount

        theoretical_usdt = round(init_usdt + inflow_usdt - outflow_usdt, 2)

        # 2. Movimientos Fiat (VES) por banco desde el Libro Diario
        bank_stats: dict[str, dict[str, float]] = {}
        for b_name, b_init in banks_cfg.items():
            bank_stats[b_name] = {
                "initial": float(b_init),
                "inflows": 0.0,
                "outflows": 0.0,
            }

        entries = self.journal_repo.list_entries(
            start_date=start_date,
            end_date=end_date,
            account_code=self.ACCOUNT_BANCO_VES,
        )

        for e in entries:
            matched_bank: str | None = None
            desc = (e.description or "").lower()
            acc_name = str(e.account_name or "")
            acc_lower = acc_name.lower()

            for b_name in bank_stats:
                if b_name == "Banco Principal" and not has_explicit_banks:
                    continue
                if b_name.lower() in desc or b_name.lower() in acc_lower:
                    matched_bank = b_name
                    break

            if not matched_bank:
                if has_explicit_banks and len(explicit_banks_cfg) == 1:
                    matched_bank = next(iter(explicit_banks_cfg.keys()))
                else:
                    extracted_bank = ""
                    if " - " in acc_name:
                        extracted_bank = acc_name.split(" - ", 1)[1].strip()
                    if extracted_bank and extracted_bank.lower() not in ("comercial", "desconocido"):
                        matched_bank = extracted_bank
                    elif not has_explicit_banks and "Banco Principal" in bank_stats:
                        matched_bank = "Banco Principal"
                    else:
                        matched_bank = "Otros / No Especificado"

                if matched_bank not in bank_stats:
                    bank_stats[matched_bank] = {"initial": 0.0, "inflows": 0.0, "outflows": 0.0}

            # En cuenta de Activo (1.1.01): Debe = Entrada de dinero (Venta P2P recibida)
            # Haber = Salida de dinero (Pago de Compra P2P)
            bank_stats[matched_bank]["inflows"] += float(e.debit)
            bank_stats[matched_bank]["outflows"] += float(e.credit)

        bank_items: list[BankBalanceItem] = []
        tot_init_ves = 0.0
        tot_inflows_ves = 0.0
        tot_outflows_ves = 0.0

        for b_name, stats in bank_stats.items():
            b_theo = round(stats["initial"] + stats["inflows"] - stats["outflows"], 2)
            bank_items.append(
                BankBalanceItem(
                    bank_name=b_name,
                    initial_ves=round(stats["initial"], 2),
                    inflows_ves=round(stats["inflows"], 2),
                    outflows_ves=round(stats["outflows"], 2),
                    theoretical_ves=b_theo,
                )
            )
            tot_init_ves += stats["initial"]
            tot_inflows_ves += stats["inflows"]
            tot_outflows_ves += stats["outflows"]

        tot_theo_ves = round(tot_init_ves + tot_inflows_ves - tot_outflows_ves, 2)

        return LiveBalanceSummary(
            year=year,
            month=month,
            initial_usdt=round(init_usdt, 2),
            inflow_usdt=round(inflow_usdt, 2),
            outflow_usdt=round(outflow_usdt, 2),
            theoretical_usdt=theoretical_usdt,
            total_initial_ves=round(tot_init_ves, 2),
            total_inflows_ves=round(tot_inflows_ves, 2),
            total_outflows_ves=round(tot_outflows_ves, 2),
            total_theoretical_ves=tot_theo_ves,
            bank_breakdown=bank_items,
        )

