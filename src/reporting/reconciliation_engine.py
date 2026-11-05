"""Motor de Conciliación Multi-Factorial P2P (SPEC-017).

Evalúa la compatibilidad entre comprobantes bancarios (BankVoucher) y órdenes de Binance P2P (Order)
aplicando filtros excluyentes (hard filters) de dirección de flujo y ventana de tiempo,
junto con una matriz de scoring de 0 a 100% para garantizar cero falsos positivos.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast

from src.data.models import BankVoucher, Order
from src.reporting.normalizers import (
    normalize_bank_name,
    normalize_reference,
    normalize_text,
)


class ReconciliationDecision(str, Enum):
    AUTO_MATCHED = "AUTO_MATCHED"  # Score >= 90%
    SUGGESTED = "SUGGESTED"        # Score 60% - 89%
    UNMATCHED = "UNMATCHED"        # Score < 60%


@dataclass
class ReconciliationMatchResult:
    voucher_id: int | None
    matched_order: Order | None
    score: float
    decision: ReconciliationDecision
    details: dict[str, Any] = field(default_factory=dict)


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convierte datetimes a formato UTC sin timezone (naive) para comparaciones seguras."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class P2PReconciliationEngine:
    """Motor de análisis multi-factorial y scoring de comprobantes bancarios vs órdenes P2P."""

    # Umbrales de decisión
    AUTO_MATCH_THRESHOLD: float = 90.0
    SUGGESTED_THRESHOLD: float = 60.0

    # Ventanas máximas de tiempo por método de pago (en segundos)
    WINDOW_PAGO_MOVIL_SEC: float = 1800.0       # 30 minutos
    WINDOW_TRANSFER_SEC: float = 172800.0       # 48 horas (ACH / interbancario)

    def calculate_score(self, voucher: BankVoucher, order: Order) -> float:
        """Calcula el puntaje de coincidencia (0 - 100%) entre un comprobante y una orden."""
        # ---------------------------------------------------------
        # 1. HARD FILTER: Dirección de Flujo de Fondos (Fail-closed)
        # ---------------------------------------------------------
        voucher_mov = (voucher.movement_type or "DEBIT").upper()
        trade_type = (order.trade_type or "BUY").upper()

        # En BUY compramos cripto -> nosotros transferimos dinero (DEBIT)
        # En SELL vendemos cripto -> nosotros recibimos dinero (CREDIT)
        if voucher_mov == "DEBIT" and trade_type != "BUY":
            return 0.0
        if voucher_mov == "CREDIT" and trade_type != "SELL":
            return 0.0

        # ---------------------------------------------------------
        # 2. HARD FILTER: Ventana de Tiempo
        # ---------------------------------------------------------
        v_dt = _to_naive_utc(cast(datetime | None, voucher.voucher_date))
        o_created = _to_naive_utc(cast(datetime | None, order.created_at))
        o_completed = _to_naive_utc(cast(datetime | None, order.completed_at)) or o_created

        if v_dt is not None and o_created is not None and o_completed is not None:
            diff_sec = min(
                abs((v_dt - o_created).total_seconds()),
                abs((v_dt - o_completed).total_seconds()),
            )
            pay_method = (voucher.payment_method or "PAGO_MOVIL").upper()
            if "TRANSF" in pay_method:
                if diff_sec > self.WINDOW_TRANSFER_SEC:
                    return 0.0
            else:
                if diff_sec > self.WINDOW_PAGO_MOVIL_SEC:
                    return 0.0

        # ---------------------------------------------------------
        # 3. MATRIZ DE SCORING MULTI-FACTORIAL
        # ---------------------------------------------------------
        score = 0.0

        # Factor A: Monto exacto en VES (Tolerancia 0.05 Bs) - 30% + Bonus 5% por céntimos
        diff_amount = abs(float(voucher.amount_ves) - float(order.fiat_amount))
        if diff_amount <= 0.05:
            score += 30.0
            # Montos con céntimos impares tienen una unicidad muy superior en P2P
            if float(order.fiat_amount) % 1.0 > 0.001:
                score += 5.0
        else:
            # Si el monto en bolívares no coincide, no puede conciliarse
            return 0.0

        # Factor B: Banco / Método de Pago - 30%
        v_bank = normalize_bank_name(cast(str | None, voucher.bank_name))
        v_dest = normalize_bank_name(cast(str | None, voucher.destination_bank)) if voucher.destination_bank else ""
        o_pm = normalize_bank_name(cast(str | None, order.payment_method)) if order.payment_method else ""

        bank_matched = False
        if (o_pm and (v_bank in o_pm or o_pm in v_bank)) or (v_dest and o_pm and (v_dest in o_pm or o_pm in v_dest)):
            bank_matched = True
        elif order.payment_method:
            raw_pm = normalize_text(cast(str | None, order.payment_method))
            if v_bank in raw_pm or (v_dest and v_dest in raw_pm):
                bank_matched = True

        if bank_matched:
            score += 30.0

        # Factor C: Referencia Bancaria en Orden / Chat - 40%
        if voucher.reference_number:
            clean_ref = normalize_reference(cast(str | None, voucher.reference_number))
            if len(clean_ref) >= 4:
                ref_in_order = clean_ref in str(order.order_number or "")
                ref_in_counterparty = clean_ref in str(order.counterparty_name or "")
                if ref_in_order or ref_in_counterparty:
                    score += 40.0

        # Factor D: Titular / Contraparte (Bonus 15%)
        if voucher.sender_name and order.counterparty_name:
            v_words = {w for w in normalize_text(cast(str | None, voucher.sender_name)).split() if len(w) >= 3}
            o_words = {w for w in normalize_text(cast(str | None, order.counterparty_name)).split() if len(w) >= 3}
            if v_words & o_words:
                score += 15.0

        return min(100.0, score)

    def find_best_match(
        self,
        voucher: BankVoucher,
        candidate_orders: list[Order],
    ) -> ReconciliationMatchResult:
        """Encuentra la mejor orden coincidente para un comprobante bancario individual."""
        best_order: Order | None = None
        best_score: float = 0.0

        for order in candidate_orders:
            score = self.calculate_score(voucher, order)
            if score > best_score:
                best_score = score
                best_order = order

        if best_score >= self.AUTO_MATCH_THRESHOLD:
            decision = ReconciliationDecision.AUTO_MATCHED
        elif best_score >= self.SUGGESTED_THRESHOLD:
            decision = ReconciliationDecision.SUGGESTED
        else:
            decision = ReconciliationDecision.UNMATCHED
            best_order = None

        return ReconciliationMatchResult(
            voucher_id=cast(int | None, voucher.id),
            matched_order=best_order,
            score=best_score,
            decision=decision,
            details={"voucher_reference": voucher.reference_number},
        )

    def reconcile_batch(
        self,
        vouchers: list[BankVoucher],
        orders: list[Order],
    ) -> list[ReconciliationMatchResult]:
        """Conciliación masiva en lote con asignación biunívoca (1 voucher = 1 orden)."""
        # Calcular todos los pares posibles ordenados por score descendente
        pair_scores: list[tuple[float, BankVoucher, Order]] = []
        for v in vouchers:
            for o in orders:
                s = self.calculate_score(v, o)
                if s >= self.SUGGESTED_THRESHOLD:
                    pair_scores.append((s, v, o))

        pair_scores.sort(key=lambda x: x[0], reverse=True)

        assigned_vouchers: set[int] = set()
        assigned_orders: set[str] = set()
        results_map: dict[int, ReconciliationMatchResult] = {}

        for score, voucher, order in pair_scores:
            v_id = int(cast(int, voucher.id)) if voucher.id is not None else -1
            o_num = str(order.order_number)

            if v_id in assigned_vouchers or o_num in assigned_orders:
                continue

            decision = (
                ReconciliationDecision.AUTO_MATCHED
                if score >= self.AUTO_MATCH_THRESHOLD
                else ReconciliationDecision.SUGGESTED
            )

            results_map[v_id] = ReconciliationMatchResult(
                voucher_id=cast(int | None, voucher.id),
                matched_order=order,
                score=score,
                decision=decision,
                details={"assigned_order_number": o_num},
            )
            assigned_vouchers.add(v_id)
            assigned_orders.add(o_num)

        # Completar comprobantes no emparejados
        for voucher in vouchers:
            v_id = int(cast(int, voucher.id)) if voucher.id is not None else -1
            if v_id not in results_map:
                results_map[v_id] = ReconciliationMatchResult(
                    voucher_id=cast(int | None, voucher.id),
                    matched_order=None,
                    score=0.0,
                    decision=ReconciliationDecision.UNMATCHED,
                )

        return list(results_map.values())
