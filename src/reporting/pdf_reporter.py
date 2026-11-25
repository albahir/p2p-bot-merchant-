"""Generador de Informes Contables y Fiscales Oficiales en PDF multipágina.

Produce documentos PDF 1.4 con formato ejecutivo de estudio contable conformes con
el Código de Comercio Art. 32-34, BA VEN-NIF N° 12, LISLR Art. 1/4/27 y Art. 177 Rgto.,
y Providencia SNAT/2026/00099: tablas estructuradas con alineación numérica, paginación
automática completa sin truncamiento, hora legal VET (UTC-4), tasa BCV oficial y Sumas Iguales.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

from src.data.models import BankVoucher, JournalEntry, Order
from src.reporting.accounting_engine import LedgerSummary
from src.reporting.tax_engine import TradeResult

VET_TZ = timezone(timedelta(hours=-4))

# Anchos promedio por carácter en Helvetica Type1 (fracción del tamaño de fuente)
_CHAR_WIDTH_RATIO = 0.50
_DIGIT_WIDTH_RATIO = 0.54


class PDFReporter:
    """Generador de reportes contables oficiales multipágina en formato PDF 1.4."""

    def __init__(
        self,
        company_name: str = "P2P MERCHANT COMMERCE C.A.",
        rif: str = "J-50000000-0",
    ):
        self.company_name = company_name
        self.rif = rif

    def _escape_pdf_text(self, text: str) -> str:
        """Sanitiza y escapa caracteres especiales para el formato PDF Type1 (WinAnsi/ASCII)."""
        trans_table = str.maketrans({
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
            "ñ": "n", "Ñ": "N", "ü": "u", "Ü": "U",
            "°": "o", "—": "-", "–": "-", "•": "-",
            "(": r"\(", ")": r"\)", "\\": r"\\",
        })
        clean = text.translate(trans_table)
        return "".join(c for c in clean if 32 <= ord(c) <= 126)

    @staticmethod
    def _estimate_width(text: str, font_size: float) -> float:
        width = 0.0
        for ch in text:
            if ch in "0123456789.,+-":
                width += font_size * _DIGIT_WIDTH_RATIO
            elif ch in "ilI1.,:;| ":
                width += font_size * 0.28
            elif ch in "MWmw":
                width += font_size * 0.78
            else:
                width += font_size * _CHAR_WIDTH_RATIO
        return width

    @staticmethod
    def _to_vet(dt: datetime | None) -> str:
        if not dt:
            return "-"
        aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        return aware.astimezone(VET_TZ).strftime("%Y-%m-%d %H:%M")

    def generate_accounting_pdf(
        self,
        journal_entries: list[JournalEntry],
        ledger_summaries: list[LedgerSummary],
        vouchers: list[BankVoucher],
        output_path: str = "reporte_contable.pdf",
        metadata: dict[str, Any] | None = None,
        tax_results: list[TradeResult] | None = None,
        period: str | None = None,
        orders: list[Order] | None = None,
        wallet_movements: list[Any] | None = None,
        bcv_rate: float | None = None,
        initial_usdt: float = 0.0,
        initial_usdt_cost_ves: float = 0.0,
        initial_ves: float = 0.0,
        actual_final_usdt: float | None = None,
        actual_final_ves: float | None = None,
    ) -> str:
        """Construye un informe contable PDF 1.4 multipágina estructurado sin truncar asientos."""
        now_vet = datetime.now(VET_TZ).strftime("%Y-%m-%d %H:%M:%S VET")
        results = tax_results or []
        order_list = orders or []
        period_label = period or (metadata.get("period") if metadata else None) or "Mes en curso"

        ref_bcv = float(bcv_rate or 0.0)
        if ref_bcv <= 0 and results:
            valid_bcv = [float(r.bcv_rate) for r in results if float(r.bcv_rate) > 0]
            ref_bcv = valid_bcv[-1] if valid_bcv else 0.0
        if ref_bcv <= 0 and order_list:
            valid_obcv = [float(o.bcv_rate) for o in order_list if float(o.bcv_rate or 0.0) > 0]
            ref_bcv = valid_obcv[-1] if valid_obcv else 0.0

        def _usd(ves_val: float) -> str:
            if ref_bcv <= 0:
                return "-"
            return f"$ {ves_val / ref_bcv:,.2f}"

        pages: list[list[str]] = []
        current_cmds: list[str] = []
        y = 780.0
        left_x = 32.0
        right_x = 563.0
        content_w = right_x - left_x

        def draw_text(
            x: float,
            y_pos: float,
            text: str,
            font: str = "F1",
            size: float = 8.0,
            color: str = "0.10 0.12 0.16",
            align: str = "left",
        ) -> None:
            safe = self._escape_pdf_text(text)
            draw_x = x
            if align == "right":
                draw_x = max(left_x, x - self._estimate_width(safe, size))
            elif align == "center":
                draw_x = max(left_x, x - self._estimate_width(safe, size) / 2.0)
            current_cmds.append(f"{color} rg")
            current_cmds.append(f"BT /{font} {size:.1f} Tf {draw_x:.1f} {y_pos:.1f} Td ({safe}) Tj ET")

        def draw_rect(
            x: float,
            y_pos: float,
            w: float,
            h: float,
            fill: str | None = None,
            stroke: str | None = None,
            line_w: float = 0.6,
        ) -> None:
            if fill and stroke:
                current_cmds.append(f"{fill} rg {stroke} RG {line_w} w {x:.1f} {y_pos:.1f} {w:.1f} {h:.1f} re B")
            elif fill:
                current_cmds.append(f"{fill} rg {x:.1f} {y_pos:.1f} {w:.1f} {h:.1f} re f")
            elif stroke:
                current_cmds.append(f"{stroke} RG {line_w} w {x:.1f} {y_pos:.1f} {w:.1f} {h:.1f} re S")

        def draw_line(x1: float, y1: float, x2: float, y2: float, color: str = "0.82 0.85 0.89", w: float = 0.6) -> None:
            current_cmds.append(f"{color} RG {w} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

        def start_page(continuation: bool = False) -> None:
            nonlocal current_cmds, y
            current_cmds = []
            pages.append(current_cmds)

            # Banner institucional superior (Azul Marino + Franja Dorada)
            draw_rect(left_x, 786, content_w, 36, fill="0.07 0.13 0.24")
            draw_rect(left_x, 783, content_w, 3, fill="0.85 0.56 0.06")
            draw_text(left_x + 12, 807, "REPUBLICA BOLIVARIANA DE VENEZUELA  |  EXPEDIENTE CONTABLE Y FISCAL", "F2", 9.5, "1 1 1")
            sub = (
                f"ESTADOS FINANCIEROS Y LIBROS LEGALES (CONTINUACION)  -  PERIODO {period_label}"
                if continuation
                else f"ESTADOS FINANCIEROS, KARDEX Y LIBROS LEGALES (VET)  -  PERIODO {period_label}"
            )
            draw_text(left_x + 12, 794, sub, "F1", 7.8, "0.82 0.88 0.96")

            if not continuation:
                # Ficha estructurada del contribuyente (2 columnas con borde limpio)
                draw_rect(left_x, 725, content_w, 52, fill="0.97 0.98 0.99", stroke="0.82 0.85 0.89", line_w=0.6)
                draw_text(left_x + 10, 763, "CONTRIBUYENTE / TITULAR:", "F2", 7.5, "0.35 0.42 0.52")
                draw_text(left_x + 128, 763, self.company_name[:38], "F2", 8.5, "0.07 0.13 0.24")
                draw_text(left_x + 10, 749, "C.I. / RIF:", "F2", 7.5, "0.35 0.42 0.52")
                draw_text(left_x + 128, 749, self.rif, "F1", 8.2, "0.10 0.12 0.16")
                draw_text(left_x + 10, 735, "MARCO NORMATIVO:", "F2", 7.5, "0.35 0.42 0.52")
                draw_text(left_x + 128, 735, "LISLR Art. 1/4/27 y 177 Rgto | BA VEN-NIF 12 | C.Com. Art. 32-34", "F1", 7.3, "0.25 0.30 0.38")

                mid_x = 370.0
                draw_line(mid_x - 8, 729, mid_x - 8, 773, "0.85 0.88 0.92", 0.5)
                draw_text(mid_x, 763, "PERIODO FISCAL:", "F2", 7.5, "0.35 0.42 0.52")
                draw_text(right_x - 10, 763, period_label, "F2", 8.2, "0.07 0.13 0.24", align="right")
                draw_text(mid_x, 749, "MONEDA / TASA BCV:", "F2", 7.5, "0.35 0.42 0.52")
                bcv_txt = f"VES  |  Bs. {ref_bcv:,.4f}" if ref_bcv > 0 else "VES (Oficial)"
                draw_text(right_x - 10, 749, bcv_txt, "F1", 7.8, "0.10 0.12 0.16", align="right")
                draw_text(mid_x, 735, "EMISION (VET):", "F2", 7.5, "0.35 0.42 0.52")
                draw_text(right_x - 10, 735, now_vet, "F1", 7.4, "0.25 0.30 0.38", align="right")
                y = 708.0
            else:
                draw_text(left_x, 770, f"{self.company_name}  |  C.I./RIF: {self.rif}  |  Periodo {period_label}", "F1", 7.5, "0.35 0.42 0.52")
                draw_text(right_x, 770, now_vet, "F1", 7.5, "0.35 0.42 0.52", align="right")
                draw_line(left_x, 765, right_x, 765, "0.85 0.88 0.92", 0.5)
                y = 748.0

        def ensure_space(needed: float = 28.0, header_cb: Any = None) -> None:
            nonlocal y
            if y - needed < 68.0:
                start_page(continuation=True)
                if header_cb:
                    header_cb()

        def draw_section_title(title: str) -> None:
            nonlocal y
            ensure_space(48.0)
            draw_rect(left_x, y - 3, 3.5, 13, fill="0.85 0.56 0.06")
            draw_text(left_x + 9, y, title, "F2", 9.5, "0.07 0.13 0.24")
            draw_line(left_x, y - 5, right_x, y - 5, "0.78 0.82 0.88", 0.7)
            y -= 17.0

        def draw_table_header(cols: list[tuple[str, float, str]]) -> None:
            nonlocal y
            draw_rect(left_x, y - 4, content_w, 15, fill="0.11 0.18 0.31")
            for label, cx, align in cols:
                draw_text(cx, y, label, "F2", 7.5, "1 1 1", align=align)
            y -= 15.0

        def draw_table_row(
            cols: list[tuple[str, float, str]],
            shaded: bool = False,
            bold: bool = False,
            highlight: bool = False,
            font_size: float = 7.6,
            row_h: float = 14.0,
        ) -> None:
            nonlocal y
            if highlight:
                draw_rect(left_x, y - 4, content_w, row_h, fill="0.93 0.95 0.98", stroke="0.72 0.78 0.86", line_w=0.6)
            elif shaded:
                draw_rect(left_x, y - 4, content_w, row_h, fill="0.97 0.98 0.99")
            font_name = "F2" if (bold or highlight) else "F1"
            txt_color = "0.07 0.13 0.24" if highlight else "0.12 0.15 0.20"
            for val, cx, align in cols:
                draw_text(cx, y, val, font_name, font_size, txt_color, align=align)
            draw_line(left_x, y - 4, right_x, y - 4, "0.89 0.91 0.94", 0.35)
            y -= row_h

        start_page(continuation=False)

        # =====================================================================
        # SECCION 1: ESTADO DE RESULTADOS FISCAL (BASE ISLR PEPS)
        # =====================================================================
        ingresos = round(sum(float(r.total_revenue_fiat) for r in results), 2)
        costo_peps = round(sum(float(r.acquisition_cost_fiat) for r in results), 2)
        utilidad_bruta = round(ingresos - costo_peps, 2)
        comisiones_bin = round(sum(float(r.fee_fiat) for r in results), 2)
        if comisiones_bin == 0.0:
            comisiones_bin = round(sum(float(e.debit) for e in journal_entries if e.account_code == "5.1.02"), 2)
        comisiones_bco = round(sum(float(e.debit) for e in journal_entries if e.account_code == "5.2.01"), 2)
        neto_islr = round(utilidad_bruta - comisiones_bin - comisiones_bco, 2)

        draw_section_title("1. ESTADO DE RESULTADOS FISCAL (LISLR ART. 1, 4 Y 27 - METODO PEPS)")
        er_headers = [
            ("PARTIDA CONTABLE (VEN-NIF / LISLR)", left_x + 6, "left"),
            ("MONTO (VES)", 445.0, "right"),
            ("EQUIV. USD (BCV)", right_x - 6, "right"),
        ]
        draw_table_header(er_headers)
        er_rows = [
            ("Ingresos Brutos por Enajenacion P2P", f"Bs. {ingresos:,.2f}", _usd(ingresos), False, False),
            ("(-) Costo de Adquisicion PEPS (FIFO)", f"Bs. {costo_peps:,.2f}", _usd(costo_peps), False, False),
            ("(=) Utilidad Bruta Realizada", f"Bs. {utilidad_bruta:,.2f}", _usd(utilidad_bruta), True, False),
            ("(-) Comisiones Plataforma Exchange (Deducible)", f"Bs. {comisiones_bin:,.2f}", _usd(comisiones_bin), False, False),
            ("(-) Comisiones Bancarias Nacionales (Deducible)", f"Bs. {comisiones_bco:,.2f}", _usd(comisiones_bco), False, False),
            ("(=) ENRIQUECIMIENTO NETO GRAVABLE ISLR", f"Bs. {neto_islr:,.2f}", _usd(neto_islr), True, True),
        ]
        for idx, (label, v_ves, v_usd, is_bold, is_hi) in enumerate(er_rows):
            ensure_space(16.0)
            draw_table_row(
                [(label, left_x + 6, "left"), (v_ves, 445.0, "right"), (v_usd, right_x - 6, "right")],
                shaded=(idx % 2 == 1),
                bold=is_bold,
                highlight=is_hi,
            )

        # =====================================================================
        # SECCION 2: ESTADO DE SITUACION FINANCIERA (BALANCE GENERAL BA VEN-NIF 12)
        # =====================================================================
        completed_orders = [o for o in order_list if str(getattr(o, "order_status", "COMPLETED")) == "COMPLETED"]
        compras_usdt = round(sum(float(o.crypto_amount) for o in completed_orders if o.trade_type == "BUY"), 4)
        compras_ves = round(sum(float(o.fiat_amount) for o in completed_orders if o.trade_type == "BUY"), 2)
        ventas_usdt = round(
            sum(float(o.crypto_amount) for o in completed_orders if o.trade_type == "SELL")
            if completed_orders
            else sum(float(r.crypto_amount) for r in results),
            4,
        )
        init_usdt_val = round(float(initial_usdt or 0.0), 4)
        init_usdt_cost = round(float(initial_usdt_cost_ves or 0.0), 2)
        if init_usdt_cost <= 0.0 and init_usdt_val > 0.0 and ref_bcv > 0.0:
            init_usdt_cost = round(init_usdt_val * ref_bcv, 2)

        wm_usdt = [
            m
            for m in (wallet_movements or [])
            if str(getattr(m, "asset", "") or "").upper() == "USDT"
            and str(getattr(m, "status", "") or "").upper() in ("COMPLETED", "SUCCESS")
        ]
        otros_ing_usdt = round(
            sum(float(m.amount or 0.0) for m in wm_usdt if str(m.movement_type or "").upper() == "DEPOSIT"),
            4,
        )
        otros_egr_usdt = round(
            sum(
                float(m.amount or 0.0) + float(m.fee or 0.0)
                for m in wm_usdt
                if str(m.movement_type or "").upper() == "WITHDRAWAL"
            ),
            4,
        )
        otros_ing_ves = round(otros_ing_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0
        otros_egr_ves = round(otros_egr_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0

        inv_final_usdt = round(init_usdt_val + compras_usdt + otros_ing_usdt - ventas_usdt - otros_egr_usdt, 4)
        inv_final_ves = round(
            max(0.0, init_usdt_cost + compras_ves + otros_ing_ves - costo_peps - otros_egr_ves),
            2,
        )

        banco_ledger = next((s for s in ledger_summaries if str(s.account_code) == "1.1.01"), None)
        banco_teorico = (
            round(float(banco_ledger.final_balance), 2)
            if banco_ledger is not None
            else round(float(initial_ves or 0.0), 2)
        )
        efectivo_bancos = round(float(actual_final_ves), 2) if actual_final_ves is not None else banco_teorico
        pasivo_pendiente = max(
            0.0,
            round(sum(float(e.credit) - float(e.debit) for e in journal_entries if str(e.account_code) == "2.1.09"), 2),
        )
        total_activo = round(efectivo_bancos + inv_final_ves, 2)
        capital_inicial = round(float(initial_ves or 0.0) + init_usdt_cost, 2)
        ajuste_conciliacion = round(total_activo - pasivo_pendiente - capital_inicial - neto_islr, 2)
        total_pasivo_patrimonio = round(pasivo_pendiente + capital_inicial + neto_islr + ajuste_conciliacion, 2)

        y -= 10.0
        draw_section_title("2. ESTADO DE SITUACION FINANCIERA (BALANCE GENERAL - BA VEN-NIF 12)")
        bg_headers = [
            ("RUBRO PATRIMONIAL (SEPARACION EFECTIVO VS CRIPTOACTIVOS)", left_x + 6, "left"),
            ("MONTO (VES)", 445.0, "right"),
            ("EQUIV. USD (BCV)", right_x - 6, "right"),
        ]
        draw_table_header(bg_headers)
        bg_rows = [
            ("1.1.01 Efectivo en Bancos Nacionales (VES)", f"Bs. {efectivo_bancos:,.2f}", _usd(efectivo_bancos), False, False),
            ("1.1.05 Criptoactivos Propios - Inventario USDT al Costo", f"Bs. {inv_final_ves:,.2f}", _usd(inv_final_ves), False, False),
            ("TOTAL ACTIVO CORRIENTE", f"Bs. {total_activo:,.2f}", _usd(total_activo), True, True),
            ("2.1.09 Pasivos / Creditos Bancarios por Conciliar", f"Bs. {pasivo_pendiente:,.2f}", _usd(pasivo_pendiente), False, False),
            ("3.1.01 Patrimonio - Capital Inicial Declarado (Bancos + USDT)", f"Bs. {capital_inicial:,.2f}", _usd(capital_inicial), False, False),
            ("3.2.01 Resultado Neto del Periodo (Enriquecimiento ISLR)", f"Bs. {neto_islr:,.2f}", _usd(neto_islr), False, False),
            ("3.2.02 Ajustes de Arqueo / Transito Bancario por Conciliar", f"Bs. {ajuste_conciliacion:,.2f}", _usd(ajuste_conciliacion), False, False),
            ("TOTAL PASIVO + PATRIMONIO", f"Bs. {total_pasivo_patrimonio:,.2f}", _usd(total_pasivo_patrimonio), True, True),
        ]
        for idx, (label, v_ves, v_usd, is_bold, is_hi) in enumerate(bg_rows):
            ensure_space(16.0)
            draw_table_row(
                [(label, left_x + 6, "left"), (v_ves, 445.0, "right"), (v_usd, right_x - 6, "right")],
                shaded=(idx % 2 == 1),
                bold=is_bold,
                highlight=is_hi,
            )

        # =====================================================================
        # SECCION 3: KARDEX DE INVENTARIO USDT (ART. 177 RGTO. LISLR) Y ARQUEO
        # =====================================================================
        y -= 10.0
        draw_section_title("3. KARDEX DE INVENTARIO USDT (ART. 177 RGTO. LISLR) Y ARQUEO DE CIERRE")
        kx_headers = [
            ("MOVIMIENTO DE EXISTENCIAS CRIPTO (USDT)", left_x + 6, "left"),
            ("CANTIDAD (USDT)", 425.0, "right"),
            ("VALOR / COSTO (VES)", right_x - 6, "right"),
        ]
        draw_table_header(kx_headers)
        kx_rows: list[tuple[str, str, str, bool, bool]] = [
            ("Saldo Inicial de Inventario USDT", f"{init_usdt_val:,.4f} USDT", f"Bs. {init_usdt_cost:,.2f}", False, False),
            ("(+) Compras P2P Completadas del Periodo", f"{compras_usdt:,.4f} USDT", f"Bs. {compras_ves:,.2f}", False, False),
        ]
        if otros_ing_usdt > 0:
            kx_rows.append(
                ("(+) Entradas Binance Pay / Depositos USDT", f"{otros_ing_usdt:,.4f} USDT", f"Bs. {otros_ing_ves:,.2f}", False, False)
            )
        kx_rows.append(
            ("(-) Ventas P2P Completadas (Costo PEPS)", f"{ventas_usdt:,.4f} USDT", f"Bs. {costo_peps:,.2f}", False, False)
        )
        if otros_egr_usdt > 0:
            kx_rows.append(
                ("(-) Salidas Binance Pay / Retiros USDT", f"{otros_egr_usdt:,.4f} USDT", f"Bs. {otros_egr_ves:,.2f}", False, False)
            )
        kx_rows.append(
            ("(=) Inventario Final Teorico USDT", f"{inv_final_usdt:,.4f} USDT", f"Bs. {inv_final_ves:,.2f}", True, True)
        )
        if actual_final_usdt is not None:
            real_u = round(float(actual_final_usdt), 4)
            diff_u = round(real_u - inv_final_usdt, 4)
            kx_rows.append(
                (
                    "Arqueo Final Real Declarado (Binance USDT)",
                    f"{real_u:,.4f} USDT",
                    f"Bs. {real_u * ref_bcv:,.2f}" if ref_bcv > 0 else "-",
                    True,
                    False,
                )
            )
            kx_rows.append(
                (
                    "Diferencia de Arqueo (Real - Teorico)",
                    f"{diff_u:+,.4f} USDT",
                    "CUADRADO" if abs(diff_u) <= 0.05 else "REVISAR DIFERENCIA",
                    True,
                    False,
                )
            )
        for idx, (label, q_usdt, v_ves, is_bold, is_hi) in enumerate(kx_rows):
            ensure_space(16.0)
            draw_table_row(
                [(label, left_x + 6, "left"), (q_usdt, 425.0, "right"), (v_ves, right_x - 6, "right")],
                shaded=(idx % 2 == 1),
                bold=is_bold,
                highlight=is_hi,
            )

        # =====================================================================
        # SECCION 4: LIBRO MAYOR CONSOLIDADO
        # =====================================================================
        y -= 10.0
        draw_section_title("4. LIBRO MAYOR CONSOLIDADO (SALDOS MENSUALES POR CUENTA)")
        mayor_headers = [
            ("CUENTA", left_x + 6, "left"),
            ("DESCRIPCION CONTABLE", left_x + 54, "left"),
            ("INICIAL (VES)", 345.0, "right"),
            ("DEBE (VES)", 418.0, "right"),
            ("HABER (VES)", 490.0, "right"),
            ("FINAL (VES)", right_x - 6, "right"),
        ]
        draw_table_header(mayor_headers)

        fallback_names = {
            "1.1.01": "Banco Nacional VES",
            "1.1.05": "Activos Criptograficos - USDT",
            "5.2.01": "Gastos Financieros - Comisiones Bancarias",
            "5.1.02": "Gastos Operativos - Comisiones Binance P2P",
        }
        sum_init = 0.0
        sum_deb = 0.0
        sum_cred = 0.0
        sum_fin = 0.0
        for idx, s in enumerate(ledger_summaries):
            ensure_space(16.0)
            code_str = str(s.account_code)
            raw_name = str(s.account_name or "")
            disp_name = fallback_names.get(code_str, raw_name) if raw_name.startswith("Cuenta ") else raw_name
            sum_init += float(s.initial_balance)
            sum_deb += float(s.total_debit)
            sum_cred += float(s.total_credit)
            sum_fin += float(s.final_balance)
            draw_table_row(
                [
                    (code_str, left_x + 6, "left"),
                    (disp_name[:34], left_x + 54, "left"),
                    (f"{s.initial_balance:,.2f}", 345.0, "right"),
                    (f"{s.total_debit:,.2f}", 418.0, "right"),
                    (f"{s.total_credit:,.2f}", 490.0, "right"),
                    (f"{s.final_balance:,.2f}", right_x - 6, "right"),
                ],
                shaded=(idx % 2 == 1),
                font_size=7.4,
            )
        if ledger_summaries:
            ensure_space(18.0)
            draw_table_row(
                [
                    ("", left_x + 6, "left"),
                    ("TOTALES LIBRO MAYOR", left_x + 54, "left"),
                    (f"{sum_init:,.2f}", 345.0, "right"),
                    (f"{sum_deb:,.2f}", 418.0, "right"),
                    (f"{sum_cred:,.2f}", 490.0, "right"),
                    (f"{sum_fin:,.2f}", right_x - 6, "right"),
                ],
                highlight=True,
                bold=True,
                font_size=7.5,
            )

        # =====================================================================
        # SECCION 5: LIBRO DIARIO COMPLETO (PAGINADO, SIN TRUNCAR)
        # =====================================================================
        diario_headers = [
            ("ASIENTO", left_x + 5, "left"),
            ("FECHA (VET)", left_x + 44, "left"),
            ("CUENTA", left_x + 114, "left"),
            ("DETALLE / GLOSA", left_x + 154, "left"),
            ("DEBE (VES)", 488.0, "right"),
            ("HABER (VES)", right_x - 6, "right"),
        ]

        def draw_diario_header() -> None:
            draw_table_header(diario_headers)

        y -= 10.0
        draw_section_title(f"5. LIBRO DIARIO COMPLETO - PARTIDA DOBLE ({len(journal_entries)} MOVIMIENTOS)")
        draw_diario_header()

        total_debe = 0.0
        total_haber = 0.0
        if not journal_entries:
            ensure_space(16.0)
            draw_table_row(
                [
                    ("-", left_x + 5, "left"),
                    ("-", left_x + 44, "left"),
                    ("-", left_x + 114, "left"),
                    ("Sin asientos bancarios conciliados en este periodo (suba estado bancario o OCR).", left_x + 154, "left"),
                    ("0.00", 488.0, "right"),
                    ("0.00", right_x - 6, "right"),
                ],
                font_size=7.1,
            )
        else:
            for idx, e in enumerate(journal_entries):
                ensure_space(15.0, header_cb=draw_diario_header)
                dt_vet = self._to_vet(cast(datetime | None, e.date_time))
                debe_val = float(e.debit)
                haber_val = float(e.credit)
                total_debe += debe_val
                total_haber += haber_val
                draw_table_row(
                    [
                        (f"#{int(e.entry_number)}", left_x + 5, "left"),
                        (dt_vet, left_x + 44, "left"),
                        (str(e.account_code), left_x + 114, "left"),
                        (str(e.description)[:44], left_x + 154, "left"),
                        (f"{debe_val:,.2f}", 488.0, "right"),
                        (f"{haber_val:,.2f}", right_x - 6, "right"),
                    ],
                    shaded=(idx % 2 == 1),
                    font_size=7.0,
                    row_h=13.0,
                )

        # Fila Sumas Iguales
        ensure_space(20.0)
        cuadre_label = (
            "SUMAS IGUALES LIBRO DIARIO (PARTIDA DOBLE CUADRADA):"
            if abs(total_debe - total_haber) < 0.02
            else "SUMAS IGUALES LIBRO DIARIO (REVISAR DESCUADRE):"
        )
        draw_table_row(
            [
                ("", left_x + 5, "left"),
                ("", left_x + 44, "left"),
                ("", left_x + 114, "left"),
                (cuadre_label, left_x + 154, "left"),
                (f"{total_debe:,.2f}", 488.0, "right"),
                (f"{total_haber:,.2f}", right_x - 6, "right"),
            ],
            highlight=True,
            bold=True,
            font_size=7.4,
            row_h=15.0,
        )

        # =====================================================================
        # SECCION 6: CONCILIACION BANCARIA, IGTF Y FIRMAS
        # =====================================================================
        y -= 10.0
        ensure_space(105.0)
        draw_section_title("6. CONCILIACION BANCARIA, REGIMEN IGTF Y NOTAS REVELATORIAS")
        matched_count = sum(1 for v in vouchers if v.verification_status == "MATCHED")
        total_vouchers = len(vouchers)
        if total_vouchers > 0:
            concil_txt = f"Comprobantes procesados: {total_vouchers}  |  Conciliados con Binance P2P: {matched_count} ({matched_count / total_vouchers * 100.0:.1f}%)"
        else:
            concil_txt = "Comprobantes bancarios procesados: 0 (Pendiente carga de estado de cuenta bancario o capturas OCR)."

        draw_rect(left_x, y - 42, content_w, 48, fill="0.97 0.98 0.99", stroke="0.82 0.85 0.89", line_w=0.6)
        draw_text(left_x + 10, y - 6, concil_txt, "F2", 7.6, "0.10 0.12 0.16")
        draw_text(
            left_x + 10,
            y - 20,
            "Regimen IGTF (Decreto 4.972): Operaciones liquidadas 100% en Bolivares via banca nacional estan exentas del 3% IGTF.",
            "F1",
            7.3,
            "0.25 0.30 0.38",
        )
        draw_text(
            left_x + 10,
            y - 33,
            "Providencia SNAT/2026/00099: Capital de trabajo rotativo separado del enriquecimiento neto gravable ISLR (PEPS).",
            "F1",
            7.3,
            "0.25 0.30 0.38",
        )
        y -= 66.0

        # Bloque de Firmas Legales
        ensure_space(46.0)
        draw_line(left_x + 30, y, left_x + 225, y, "0.45 0.50 0.58", 0.7)
        draw_line(right_x - 225, y, right_x - 30, y, "0.45 0.50 0.58", 0.7)
        draw_text(left_x + 127.5, y - 11, self.company_name[:34], "F2", 7.6, "0.10 0.12 0.16", align="center")
        draw_text(left_x + 127.5, y - 21, f"Contribuyente / Titular ({self.rif})", "F1", 7.0, "0.40 0.45 0.52", align="center")
        draw_text(right_x - 127.5, y - 11, "CONTADOR PUBLICO COLEGIADO", "F2", 7.6, "0.10 0.12 0.16", align="center")
        draw_text(right_x - 127.5, y - 21, "C.P.C. Nro. _____________________", "F1", 7.0, "0.40 0.45 0.52", align="center")

        # Pies de página enumerados
        total_pages = len(pages)
        for idx, p_cmds in enumerate(pages, start=1):
            p_cmds.append("0.82 0.85 0.89 RG 0.6 w")
            p_cmds.append(f"{left_x:.1f} 54.0 m {right_x:.1f} 54.0 l S")
            p_cmds.append("0.42 0.47 0.55 rg")
            p_cmds.append(
                f"BT /F1 7.0 Tf {left_x:.1f} 42.0 Td (Soporte contable Comerciante P2P - sistemap2pmerchant.com | Horario VET UTC-4) Tj ET"
            )
            pg_lbl = f"Pagina {idx} de {total_pages}"
            pg_x = right_x - self._estimate_width(pg_lbl, 7.0)
            p_cmds.append(f"BT /F2 7.0 Tf {pg_x:.1f} 42.0 Td ({pg_lbl}) Tj ET")

        # Construir objetos PDF 1.4 multipágina
        objects: list[bytes] = []
        page_obj_nums: list[int] = []
        first_page_obj = 5

        for idx in range(total_pages):
            page_obj_nums.append(first_page_obj + idx * 2)

        kids_str = " ".join(f"{n} 0 R" for n in page_obj_nums)
        objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        objects.append(
            f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>\nendobj\n".encode("ascii")
        )
        objects.append(b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
        objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

        for idx, p_cmds in enumerate(pages):
            page_num = first_page_obj + idx * 2
            stream_num = page_num + 1
            content_stream = "\n".join(p_cmds).encode("latin1", errors="replace")
            page_obj = (
                f"{page_num} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {stream_num} 0 R >>\n"
                f"endobj\n"
            ).encode("ascii")
            stream_obj = (
                f"{stream_num} 0 obj\n"
                f"<< /Length {len(content_stream)} >>\n"
                f"stream\n"
            ).encode("ascii") + content_stream + b"\nendstream\nendobj\n"
            objects.append(page_obj)
            objects.append(stream_obj)

        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets: list[int] = []
        body = bytearray(header)

        for obj in objects:
            offsets.append(len(body))
            body.extend(obj)

        xref_offset = len(body)
        xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
        for off in offsets:
            xref += f"{off:010d} 00000 n \n"

        trailer = (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        )
        body.extend(xref.encode("ascii"))
        body.extend(trailer.encode("ascii"))

        with open(output_path, "wb") as f:
            f.write(body)

        return output_path
