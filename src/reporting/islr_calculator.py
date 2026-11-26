"""Módulo puro de cálculo fiscal SENIAT (DPN-99025 / DPJ-99026), evaluación de umbrales SPE
(SNAT/2026/00099) y detección preventiva de pagos de terceros (LOCDOFT / UNIF / SUDEBAN).

Referencia normativa vigente (Nov 2026):
- Unidad Tributaria (UT): Bs. 43,00 (Providencia SNAT/2025/000048, G.O. N° 43.140).
- LISLR Art. 50 (Tarifa N° 1 - Personas Naturales) y Art. 52 (Tarifa N° 2 - Personas Jurídicas).
- Providencia SNAT/2026/00099 (G.O. N° 43.485): Sujetos Pasivos Especiales medidos en TCMV.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from difflib import SequenceMatcher
from typing import Literal

UT_VES_DEFAULT = 43.0
SINGLE_DEDUCTION_UT = 774.0
PERSONAL_REBATE_UT = 10.0
ISLR_PN_NET_THRESHOLD_UT = 1000.0
ISLR_PN_GROSS_THRESHOLD_UT = 1500.0

SPE_INTERIOR_ANNUAL_TCMV = 600_000.0
SPE_INTERIOR_MONTHLY_TCMV = 50_000.0
SPE_CAPITAL_ANNUAL_TCMV = 3_000_000.0
SPE_CAPITAL_MONTHLY_TCMV = 250_000.0

SENIAT_WORKPAPER_DISCLAIMER = (
    "Papel de trabajo contable e insumo para Declaración ISLR (Forma DPN-99025 PN / DPJ-99026 PJ). "
    "No sustituye la declaración oficial ante el SENIAT ni el dictamen de un Contador Público Colegiado (CPC)."
)

# Tablas oficiales LISLR: (techo_en_UT, alícuota, sustraendo_en_UT)
_TARIFF_1_BRACKETS: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (Decimal(1000), Decimal("0.06"), Decimal(0)),
    (Decimal(1500), Decimal("0.09"), Decimal(30)),
    (Decimal(2000), Decimal("0.12"), Decimal(75)),
    (Decimal(2500), Decimal("0.16"), Decimal(155)),
    (Decimal(3000), Decimal("0.20"), Decimal(255)),
    (Decimal(4000), Decimal("0.24"), Decimal(375)),
    (Decimal(6000), Decimal("0.29"), Decimal(575)),
    (Decimal("Infinity"), Decimal("0.34"), Decimal(875)),
)

_TARIFF_2_BRACKETS: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (Decimal(2000), Decimal("0.15"), Decimal(0)),
    (Decimal(3000), Decimal("0.22"), Decimal(140)),
    (Decimal("Infinity"), Decimal("0.34"), Decimal(500)),
)

_IGNORED_NAME_TOKENS = {
    "DE", "LA", "LAS", "EL", "LOS", "DEL", "Y", "CON", "PARA", "POR",
    "CA", "SA", "SRL", "FP", "C.A", "S.A", "USER", "TRADER", "BINANCE",
    "P2P", "CRYPTO", "USDT", "BTC", "CAMBIO", "EXCHANGE", "COMERCIO",
    "INVERSIONES", "COMERCIALIZADORA", "IMPORTADORA", "PAGO", "MOVIL",
    "PAGOMOVIL", "TPAGO", "TRANSF", "TRANSFERENCIA", "TERCERO", "TERCEROS",
    "BANESCO", "MERCANTIL", "VENEZUELA", "BNC", "BANCAMIGA", "PROVINCIAL",
    "CUENTA", "CTA", "REF", "NRO", "SR", "SRA",
}


@dataclass(frozen=True)
class ISLRCalculationResult:
    taxpayer_type: Literal["NATURAL", "JURIDICA"]
    form_code: Literal["DPN-99025", "DPJ-99026"]
    ut_value_ves: float
    gross_revenue_ves: float
    cost_of_sales_ves: float
    deductible_expenses_ves: float
    net_income_ves: float
    single_deduction_ves: float
    taxable_income_ves: float
    taxable_income_ut: float
    bracket_rate: float
    subtrahend_ut: float
    subtrahend_ves: float
    personal_rebate_ves: float
    gross_tax_ves: float
    determined_tax_ves: float


@dataclass(frozen=True)
class SeniatThresholdStatus:
    form_code: Literal["DPN-99025", "DPJ-99026"]
    taxpayer_type: Literal["NATURAL", "JURIDICA"]
    ut_value_ves: float
    tcmv_rate_ves: float
    gross_revenue_ves: float
    net_income_ves: float
    bank_rotated_volume_ves: float
    islr_pn_mandatory: bool
    islr_pn_gross_limit_ves: float
    islr_pn_net_limit_ves: float
    spe_interior_monthly_limit_ves: float
    spe_interior_annual_limit_ves: float
    spe_capital_monthly_limit_ves: float
    spe_capital_annual_limit_ves: float
    spe_interior_exceeded: bool
    spe_capital_exceeded: bool
    spe_interior_monthly_pct: float
    spe_capital_monthly_pct: float
    bank_volume_distinction_note: str


@dataclass(frozen=True)
class SeniatCasillaRow:
    section: str
    box: str
    item: str
    concept: str
    amount_ves: float
    note: str = ""


def classify_taxpayer_from_rif(
    tax_id: str | None,
) -> tuple[Literal["NATURAL", "JURIDICA"], Literal["DPN-99025", "DPJ-99026"]]:
    """Determina si el contribuyente es Persona Natural (DPN-99025) o Jurídica (DPJ-99026) según C.I./RIF."""
    clean = (tax_id or "").strip().upper()
    if clean.startswith(("J", "G")):
        return "JURIDICA", "DPJ-99026"
    return "NATURAL", "DPN-99025"


def _d2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def compute_islr_estimation(
    gross_revenue_ves: float,
    cost_of_sales_ves: float,
    deductible_expenses_ves: float,
    tax_id: str | None = None,
    ut_value_ves: float = UT_VES_DEFAULT,
    apply_single_deduction: bool = True,
    family_loads: int = 0,
) -> ISLRCalculationResult:
    """Calcula el ISLR referencial aplicando Tarifa N° 1 (Art. 50) o Tarifa N° 2 (Art. 52)."""
    taxpayer_type, form_code = classify_taxpayer_from_rif(tax_id)
    ut_dec = Decimal(str(max(0.01, float(ut_value_ves or UT_VES_DEFAULT))))
    gross_dec = _d2(Decimal(str(max(0.0, float(gross_revenue_ves or 0.0)))))
    cost_dec = _d2(Decimal(str(max(0.0, float(cost_of_sales_ves or 0.0)))))
    exp_dec = _d2(Decimal(str(max(0.0, float(deductible_expenses_ves or 0.0)))))

    net_dec = gross_dec - cost_dec - exp_dec
    if net_dec <= Decimal("0.00"):
        return ISLRCalculationResult(
            taxpayer_type=taxpayer_type,
            form_code=form_code,
            ut_value_ves=float(ut_dec),
            gross_revenue_ves=float(gross_dec),
            cost_of_sales_ves=float(cost_dec),
            deductible_expenses_ves=float(exp_dec),
            net_income_ves=float(net_dec),
            single_deduction_ves=0.0,
            taxable_income_ves=0.0,
            taxable_income_ut=0.0,
            bracket_rate=0.0,
            subtrahend_ut=0.0,
            subtrahend_ves=0.0,
            personal_rebate_ves=0.0,
            gross_tax_ves=0.0,
            determined_tax_ves=0.0,
        )

    if taxpayer_type == "NATURAL":
        ded_dec = (
            _d2(Decimal(str(SINGLE_DEDUCTION_UT)) * ut_dec)
            if apply_single_deduction
            else Decimal("0.00")
        )
        taxable_dec = max(Decimal("0.00"), net_dec - ded_dec)
        brackets = _TARIFF_1_BRACKETS
        rebate_units = Decimal(str(PERSONAL_REBATE_UT)) * Decimal(str(1 + max(0, int(family_loads))))
        rebate_dec = _d2(rebate_units * ut_dec) if taxable_dec > Decimal("0.00") else Decimal("0.00")
    else:
        ded_dec = Decimal("0.00")
        taxable_dec = net_dec
        brackets = _TARIFF_2_BRACKETS
        rebate_dec = Decimal("0.00")

    taxable_ut_dec = taxable_dec / ut_dec
    chosen_rate = Decimal(0)
    chosen_sub_ut = Decimal(0)
    for ceiling, rate, sub_ut in brackets:
        if taxable_ut_dec <= ceiling:
            chosen_rate = rate
            chosen_sub_ut = sub_ut
            break

    sub_ves_dec = _d2(chosen_sub_ut * ut_dec)
    gross_tax_dec = max(Decimal("0.00"), _d2((taxable_dec * chosen_rate) - sub_ves_dec))
    determined_dec = max(Decimal("0.00"), gross_tax_dec - rebate_dec)

    return ISLRCalculationResult(
        taxpayer_type=taxpayer_type,
        form_code=form_code,
        ut_value_ves=float(ut_dec),
        gross_revenue_ves=float(gross_dec),
        cost_of_sales_ves=float(cost_dec),
        deductible_expenses_ves=float(exp_dec),
        net_income_ves=float(net_dec),
        single_deduction_ves=float(ded_dec),
        taxable_income_ves=float(taxable_dec),
        taxable_income_ut=round(float(taxable_ut_dec), 2),
        bracket_rate=float(chosen_rate),
        subtrahend_ut=float(chosen_sub_ut),
        subtrahend_ves=float(sub_ves_dec),
        personal_rebate_ves=float(rebate_dec),
        gross_tax_ves=float(gross_tax_dec),
        determined_tax_ves=float(_d2(determined_dec)),
    )


def evaluate_seniat_thresholds(
    gross_revenue_ves: float,
    net_income_ves: float,
    bank_rotated_volume_ves: float,
    tcmv_rate_ves: float,
    tax_id: str | None = None,
    ut_value_ves: float = UT_VES_DEFAULT,
) -> SeniatThresholdStatus:
    """Evalúa umbrales obligatorios de ISLR (PN) y calificación SPE (SNAT/2026/00099) sobre ingreso real."""
    taxpayer_type, form_code = classify_taxpayer_from_rif(tax_id)
    ut_val = float(ut_value_ves or UT_VES_DEFAULT)
    tcmv = max(0.0, float(tcmv_rate_ves or 0.0))
    gross = max(0.0, float(gross_revenue_ves or 0.0))
    net = float(net_income_ves or 0.0)
    rotated = max(0.0, float(bank_rotated_volume_ves or 0.0))

    pn_gross_lim = round(ISLR_PN_GROSS_THRESHOLD_UT * ut_val, 2)
    pn_net_lim = round(ISLR_PN_NET_THRESHOLD_UT * ut_val, 2)
    islr_mandatory = gross > pn_gross_lim or net > pn_net_lim

    int_monthly_lim = round(SPE_INTERIOR_MONTHLY_TCMV * tcmv, 2) if tcmv > 0 else 0.0
    int_annual_lim = round(SPE_INTERIOR_ANNUAL_TCMV * tcmv, 2) if tcmv > 0 else 0.0
    cap_monthly_lim = round(SPE_CAPITAL_MONTHLY_TCMV * tcmv, 2) if tcmv > 0 else 0.0
    cap_annual_lim = round(SPE_CAPITAL_ANNUAL_TCMV * tcmv, 2) if tcmv > 0 else 0.0

    int_pct = round((gross / int_monthly_lim) * 100.0, 2) if int_monthly_lim > 0 else 0.0
    cap_pct = round((gross / cap_monthly_lim) * 100.0, 2) if cap_monthly_lim > 0 else 0.0

    note = (
        f"Volumen bancario rotado (Bs. {rotated:,.2f}) corresponde a capital de trabajo en cuentas nacionales (1.1.01) "
        "y no constituye ingreso bruto ni base imponible ISLR/SPE."
    )

    return SeniatThresholdStatus(
        form_code=form_code,
        taxpayer_type=taxpayer_type,
        ut_value_ves=ut_val,
        tcmv_rate_ves=tcmv,
        gross_revenue_ves=round(gross, 2),
        net_income_ves=round(net, 2),
        bank_rotated_volume_ves=round(rotated, 2),
        islr_pn_mandatory=islr_mandatory,
        islr_pn_gross_limit_ves=pn_gross_lim,
        islr_pn_net_limit_ves=pn_net_lim,
        spe_interior_monthly_limit_ves=int_monthly_lim,
        spe_interior_annual_limit_ves=int_annual_lim,
        spe_capital_monthly_limit_ves=cap_monthly_lim,
        spe_capital_annual_limit_ves=cap_annual_lim,
        spe_interior_exceeded=bool(int_monthly_lim > 0 and gross > int_monthly_lim),
        spe_capital_exceeded=bool(cap_monthly_lim > 0 and gross > cap_monthly_lim),
        spe_interior_monthly_pct=int_pct,
        spe_capital_monthly_pct=cap_pct,
        bank_volume_distinction_note=note,
    )


def build_seniat_casillas(
    islr: ISLRCalculationResult,
    initial_inventory_ves: float,
    purchases_ves: float,
    final_inventory_ves: float,
    exchange_fees_ves: float,
    bank_fees_ves: float,
) -> list[SeniatCasillaRow]:
    """Construye la tabla exacta de casillas e ítems SENIAT DPN-99025 o DPJ-99026."""
    init_inv = round(max(0.0, float(initial_inventory_ves or 0.0)), 2)
    purchases = round(max(0.0, float(purchases_ves or 0.0)), 2)
    available = round(init_inv + purchases, 2)
    final_inv = round(max(0.0, float(final_inventory_ves or 0.0)), 2)
    cogs = round(islr.cost_of_sales_ves, 2)
    exch_fees = round(max(0.0, float(exchange_fees_ves or 0.0)), 2)
    bco_fees = round(max(0.0, float(bank_fees_ves or 0.0)), 2)
    total_exp = round(islr.deductible_expenses_ves, 2)

    if islr.form_code == "DPJ-99026":
        rows = [
            SeniatCasillaRow("Secc. E", "Cas. 3 / 22", "703 / 711", "Ingresos Netos Sector Privado (Ventas P2P)", islr.gross_revenue_ves),
            SeniatCasillaRow("Secc. E", "Cas. 23", "712", "Inventario Inicial de Mercancías (USDT al costo)", init_inv),
            SeniatCasillaRow("Secc. E", "Cas. 24 / 26", "713 / 715", "Compras Netas Nacionales (Compras P2P)", purchases),
            SeniatCasillaRow("Secc. E", "Cas. 27", "716", "Total Mercancía Disponible para la Venta", available),
            SeniatCasillaRow("Secc. E", "Cas. 28", "717", "Menos: Inventario Final (USDT remanente)", final_inv),
            SeniatCasillaRow("Secc. E", "Cas. 29 / 51", "718 / 734", "Total Costo de Ventas", cogs),
            SeniatCasillaRow("Secc. E", "Cas. 70", "774", "Comisiones Varias (Exchange / Binance P2P)", exch_fees),
            SeniatCasillaRow("Secc. E", "Cas. 82", "742", "Otros Gastos Deducibles (Comisiones Bancarias 5.2.01)", bco_fees),
            SeniatCasillaRow("Secc. E", "Cas. 83", "743", "Total Gastos Operativos Deducibles", total_exp),
            SeniatCasillaRow("Secc. E", "Cas. 86 / 109", "744 / 763", "Enriquecimiento Neto o Pérdida Fiscal Territorial", islr.net_income_ves, "Traslada a Ítem 137"),
            SeniatCasillaRow("Secc. C", "Cas. 1 / 7", "137 / 431", "Enriquecimiento Neto Gravable (Tarifa N° 2)", max(0.0, islr.taxable_income_ves)),
            SeniatCasillaRow("Secc. C", "Cas. 8 / 54", "185 / 90", f"ISLR Estimado Tarifa N° 2 ({islr.bracket_rate * 100:.0f}% − {islr.subtrahend_ut:.0f} UT)", islr.determined_tax_ves, f"UT = Bs. {islr.ut_value_ves:.2f}"),
        ]
    else:
        rows = [
            SeniatCasillaRow("Secc. E", "Cas. 3 / 15", "703 / 711", "Ventas Brutas / Total Ingresos Netos (Ventas P2P)", islr.gross_revenue_ves),
            SeniatCasillaRow("Secc. E", "Cas. 16", "712", "Inventario Inicial de Mercancías (USDT al costo)", init_inv),
            SeniatCasillaRow("Secc. E", "Cas. 17 / 19", "713 / 715", "Compras Netas Nacionales (Compras P2P)", purchases),
            SeniatCasillaRow("Secc. E", "Cas. 20", "716", "Total Mercancía Disponible para la Venta", available),
            SeniatCasillaRow("Secc. E", "Cas. 21", "717", "Menos: Inventario Final (USDT remanente)", final_inv),
            SeniatCasillaRow("Secc. E", "Cas. 22 / 39", "718 / 734", "Total Costo de Ventas", cogs),
            SeniatCasillaRow("Secc. E", "Cas. 50 / 52", "742 / 743", "Otros Gastos / Total Gastos (Binance + Bancarios)", total_exp, f"Exchange Bs. {exch_fees:,.2f} + Bco Bs. {bco_fees:,.2f}"),
            SeniatCasillaRow("Secc. E", "Cas. 53 / 74", "744 / 763", "Enriquecimiento Neto o Pérdida Fiscal Territorial", islr.net_income_ves, "Traslada a Ítem 135"),
            SeniatCasillaRow("Secc. C", "Cas. 1", "135", "Enriquecimiento Neto (Tarifa N° 1 Persona Natural)", max(0.0, islr.net_income_ves)),
            SeniatCasillaRow("Secc. G", "Cas. 6 -> C.3", "851 / 163", "Desgravamen Único (774 UT Persona Residente)", islr.single_deduction_ves, "Bs. 33.282,00 con UT Bs. 43"),
            SeniatCasillaRow("Secc. C", "Cas. 4 / 10", "175 / 431", "Enriquecimiento Gravable / Renta Neta", islr.taxable_income_ves, f"{islr.taxable_income_ut:,.2f} UT"),
            SeniatCasillaRow("Rebajas", "Cas. 29", "202", "Rebaja Personal (10 UT Residente)", islr.personal_rebate_ves),
            SeniatCasillaRow("Secc. C", "Cas. 54", "185 / 90", f"ISLR Estimado Tarifa N° 1 ({islr.bracket_rate * 100:.0f}% − {islr.subtrahend_ut:.0f} UT)", islr.determined_tax_ves, "Papel de trabajo referencial"),
        ]
    return rows


def _extract_meaningful_name_tokens(raw_name: str | None) -> list[str]:
    if not raw_name or "*" in str(raw_name):
        return []
    cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü\s]", " ", str(raw_name)).upper()
    out: list[str] = []
    for tok in cleaned.split():
        if len(tok) >= 3 and tok not in _IGNORED_NAME_TOKENS:
            out.append(tok)
    return out


def is_third_party_counterparty_mismatch(
    bank_party: str | None,
    binance_party: str | None,
    bank_sender_id: str | None = None,
) -> tuple[bool, str | None]:
    """Detecta de forma conservadora posibles pagos de terceros (LOCDOFT / UNIF / SUDEBAN).

    Solo alerta cuando ambas partes identifican nombres reales completos (>=2 palabras no genéricas)
    que no comparten términos ni similitud mínima, o si existen cédulas explícitas distintas.
    """
    if bank_sender_id and binance_party:
        b_digits = re.sub(r"\D", "", str(bank_sender_id))
        o_digits_match = re.search(r"\b(\d{6,10})\b", str(binance_party))
        if len(b_digits) >= 6 and o_digits_match and b_digits != o_digits_match.group(1):
            return (
                True,
                f"Posible pago de tercero: Cédula bancaria ({bank_sender_id}) difiere de registro Binance ({o_digits_match.group(1)}).",
            )

    bank_tokens = _extract_meaningful_name_tokens(bank_party)
    binance_tokens = _extract_meaningful_name_tokens(binance_party)

    if len(bank_tokens) < 2 or len(binance_tokens) < 2:
        return False, None

    if set(bank_tokens) & set(binance_tokens):
        return False, None

    sim = SequenceMatcher(None, " ".join(bank_tokens), " ".join(binance_tokens)).ratio()
    if sim >= 0.55:
        return False, None

    return (
        True,
        f"Posible pago de tercero: Titular bancario ({' '.join(bank_tokens[:3])}) ≠ Contraparte Binance ({' '.join(binance_tokens[:3])}).",
    )
