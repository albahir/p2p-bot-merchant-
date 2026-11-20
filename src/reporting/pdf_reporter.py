"""Generador de Informes Contables y Fiscales Oficiales en PDF multipágina.

Produce documentos PDF 1.4 conformes con el Código de Comercio Art. 32-34,
BA VEN-NIF N° 12 y LISLR: paginación automática completa sin truncamiento,
hora legal de Venezuela (VET UTC-4), Sumas Iguales y Estado de Resultados PEPS.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

from src.data.models import BankVoucher, JournalEntry
from src.reporting.accounting_engine import LedgerSummary
from src.reporting.tax_engine import TradeResult

VET_TZ = timezone(timedelta(hours=-4))


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
        """Sanitiza y escapa caracteres especiales para el formato PDF Type1."""
        trans_table = str.maketrans({
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
            "ñ": "n", "Ñ": "N", "ü": "u", "Ü": "U",
            "(": r"\(", ")": r"\)", "\\": r"\\",
        })
        clean = text.translate(trans_table)
        return "".join(c for c in clean if 32 <= ord(c) <= 126)

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
    ) -> str:
        """Construye un archivo PDF 1.4 multipágina completo sin truncar asientos."""
        now_vet = datetime.now(VET_TZ).strftime("%Y-%m-%d %H:%M:%S VET")
        results = tax_results or []
        period_label = period or (metadata.get("period") if metadata else None) or "Mes en curso"

        pages: list[list[str]] = []
        current_cmds: list[str] = []
        y = 780

        def start_page(continuation: bool = False) -> None:
            nonlocal current_cmds, y
            current_cmds = []
            pages.append(current_cmds)

            current_cmds.append("0.1 0.2 0.4 rg")
            current_cmds.append("30 790 535 30 re f")
            current_cmds.append("1 1 1 rg")
            current_cmds.append("BT /F2 11 Tf 40 803 Td (REPUBLICA BOLIVARIANA DE VENEZUELA - CONTABILIDAD FISCAL) Tj ET")
            sub = (
                f"LIBRO DIARIO Y MAYOR (CONTINUACION) - PERIODO {period_label}"
                if continuation
                else f"LIBRO DIARIO, MAYOR Y ESTADO DE RESULTADOS (VET) - PERIODO {period_label}"
            )
            current_cmds.append(f"BT /F1 8 Tf 40 793 Td ({self._escape_pdf_text(sub)}) Tj ET")

            current_cmds.append("0 0 0 rg")
            if not continuation:
                current_cmds.append("BT /F2 9 Tf 30 768 Td (RAZON SOCIAL:) Tj ET")
                current_cmds.append(
                    f"BT /F1 9 Tf 115 768 Td ({self._escape_pdf_text(self.company_name)} - C.I./RIF: {self._escape_pdf_text(self.rif)}) Tj ET"
                )
                current_cmds.append("BT /F2 9 Tf 30 755 Td (EMISION (VET):) Tj ET")
                current_cmds.append(f"BT /F1 9 Tf 115 755 Td ({now_vet}) Tj ET")
                current_cmds.append("BT /F2 9 Tf 30 742 Td (NORMATIVA:) Tj ET")
                current_cmds.append(
                    "BT /F1 8 Tf 115 742 Td (LISLR Art. 1/4/27 y 177 Rgto / BA VEN-NIF 12 / Codigo Comercio Art. 32-34) Tj ET"
                )
                current_cmds.append("0.8 0.8 0.8 RG 1 w")
                current_cmds.append("30 732 m 565 732 l S")
                y = 714
            else:
                current_cmds.append(
                    f"BT /F1 8 Tf 30 770 Td ({self._escape_pdf_text(self.company_name)} | RIF: {self._escape_pdf_text(self.rif)} | {now_vet}) Tj ET"
                )
                y = 750

        def ensure_space(needed: int = 24, header_cb: Any = None) -> None:
            nonlocal y
            if y - needed < 75:
                start_page(continuation=True)
                if header_cb:
                    header_cb()

        def draw_diario_header() -> None:
            nonlocal y
            current_cmds.append("0.9 0.9 0.95 rg")
            current_cmds.append(f"30 {y - 3} 535 15 re f")
            current_cmds.append("0 0 0 rg")
            current_cmds.append(f"BT /F2 8 Tf 35 {y} Td (ASIENTO) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 75 {y} Td (FECHA VET) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 148 {y} Td (CUENTA) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 190 {y} Td (DETALLE / GLOSA) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 415 {y} Td (DEBE VES) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 490 {y} Td (HABER VES) Tj ET")

        start_page(continuation=False)

        # -------------------------------------------------------------
        # SECCION 1: ESTADO DE RESULTADOS FISCAL (LISLR PEPS)
        # -------------------------------------------------------------
        ingresos = round(sum(float(r.total_revenue_fiat) for r in results), 2)
        costo_peps = round(sum(float(r.acquisition_cost_fiat) for r in results), 2)
        comisiones_bin = round(sum(float(r.fee_fiat) for r in results), 2)
        if comisiones_bin == 0.0:
            comisiones_bin = round(sum(float(e.debit) for e in journal_entries if e.account_code == "5.1.02"), 2)
        comisiones_bco = round(sum(float(e.debit) for e in journal_entries if e.account_code == "5.2.01"), 2)
        neto_islr = round(ingresos - costo_peps - comisiones_bin - comisiones_bco, 2)

        current_cmds.append("0.15 0.3 0.5 rg")
        current_cmds.append(f"BT /F2 10 Tf 30 {y} Td (1. ESTADO DE RESULTADOS FISCAL - BASE ISLR PEPS) Tj ET")
        y -= 15
        current_cmds.append("0 0 0 rg")
        current_cmds.append(
            f"BT /F1 8 Tf 35 {y} Td (Ingresos Ventas: Bs. {ingresos:,.2f}  |  Costo PEPS: Bs. {costo_peps:,.2f}  |  Comisiones Deducibles: Bs. {(comisiones_bin + comisiones_bco):,.2f}) Tj ET"
        )
        y -= 13
        current_cmds.append(
            f"BT /F2 9 Tf 35 {y} Td (Enriquecimiento Neto Gravable ISLR: Bs. {neto_islr:,.2f}) Tj ET"
        )

        # -------------------------------------------------------------
        # SECCION 2: LIBRO MAYOR
        # -------------------------------------------------------------
        y -= 24
        ensure_space(45)
        current_cmds.append("0.15 0.3 0.5 rg")
        current_cmds.append(f"BT /F2 10 Tf 30 {y} Td (2. LIBRO MAYOR CONSOLIDADO) Tj ET")
        y -= 16
        current_cmds.append("0.9 0.9 0.95 rg")
        current_cmds.append(f"30 {y - 3} 535 15 re f")
        current_cmds.append("0 0 0 rg")
        current_cmds.append(f"BT /F2 8 Tf 35 {y} Td (CUENTA) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 80 {y} Td (DESCRIPCION) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 260 {y} Td (INICIAL) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 335 {y} Td (DEBE) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 410 {y} Td (HABER) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 485 {y} Td (FINAL) Tj ET")

        for s in ledger_summaries:
            ensure_space(16)
            y -= 14
            current_cmds.append("0 0 0 rg")
            current_cmds.append(f"BT /F1 8 Tf 35 {y} Td ({self._escape_pdf_text(str(s.account_code))}) Tj ET")
            current_cmds.append(f"BT /F1 8 Tf 80 {y} Td ({self._escape_pdf_text(str(s.account_name)[:28])}) Tj ET")
            current_cmds.append(f"BT /F1 8 Tf 260 {y} Td ({s.initial_balance:,.2f}) Tj ET")
            current_cmds.append(f"BT /F1 8 Tf 335 {y} Td ({s.total_debit:,.2f}) Tj ET")
            current_cmds.append(f"BT /F1 8 Tf 410 {y} Td ({s.total_credit:,.2f}) Tj ET")
            current_cmds.append(f"BT /F2 8 Tf 485 {y} Td ({s.final_balance:,.2f}) Tj ET")

        # -------------------------------------------------------------
        # SECCION 3: LIBRO DIARIO COMPLETO (PAGINADO, SIN TRUNCAR)
        # -------------------------------------------------------------
        y -= 24
        ensure_space(50)
        current_cmds.append("0.15 0.3 0.5 rg")
        current_cmds.append(f"BT /F2 10 Tf 30 {y} Td (3. LIBRO DIARIO COMPLETO - PARTIDA DOBLE ({len(journal_entries)} MOVIMIENTOS)) Tj ET")
        y -= 16
        draw_diario_header()

        total_debe = 0.0
        total_haber = 0.0
        for e in journal_entries:
            ensure_space(16, header_cb=draw_diario_header)
            y -= 13
            dt_vet = self._to_vet(cast(datetime | None, e.date_time))
            debe_val = float(e.debit)
            haber_val = float(e.credit)
            total_debe += debe_val
            total_haber += haber_val
            current_cmds.append("0 0 0 rg")
            current_cmds.append(f"BT /F1 7 Tf 35 {y} Td (#{int(e.entry_number)}) Tj ET")
            current_cmds.append(f"BT /F1 7 Tf 75 {y} Td ({dt_vet}) Tj ET")
            current_cmds.append(f"BT /F1 7 Tf 148 {y} Td ({self._escape_pdf_text(str(e.account_code))}) Tj ET")
            current_cmds.append(f"BT /F1 7 Tf 190 {y} Td ({self._escape_pdf_text(str(e.description)[:38])}) Tj ET")
            current_cmds.append(f"BT /F1 7 Tf 415 {y} Td ({debe_val:,.2f}) Tj ET")
            current_cmds.append(f"BT /F1 7 Tf 490 {y} Td ({haber_val:,.2f}) Tj ET")

        # Fila Sumas Iguales
        ensure_space(22)
        y -= 16
        current_cmds.append("0.94 0.94 0.96 rg")
        current_cmds.append(f"30 {y - 3} 535 14 re f")
        current_cmds.append("0 0 0 rg")
        current_cmds.append(f"BT /F2 8 Tf 190 {y} Td (SUMAS IGUALES LIBRO DIARIO:) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 415 {y} Td ({total_debe:,.2f}) Tj ET")
        current_cmds.append(f"BT /F2 8 Tf 490 {y} Td ({total_haber:,.2f}) Tj ET")

        # -------------------------------------------------------------
        # SECCION 4: CONCILIACION BANCARIA
        # -------------------------------------------------------------
        ensure_space(40)
        y -= 24
        matched_count = sum(1 for v in vouchers if v.verification_status == "MATCHED")
        total_vouchers = len(vouchers)
        rate_pct = (matched_count / total_vouchers * 100.0) if total_vouchers > 0 else 100.0
        current_cmds.append("0.15 0.3 0.5 rg")
        current_cmds.append(f"BT /F2 10 Tf 30 {y} Td (4. CONCILIACION BANCARIA Y TRAZABILIDAD) Tj ET")
        y -= 15
        current_cmds.append("0 0 0 rg")
        current_cmds.append(
            f"BT /F1 8 Tf 35 {y} Td (Comprobantes procesados: {total_vouchers}  |  Conciliados: {matched_count} ({rate_pct:.1f}%)) Tj ET"
        )

        # Pies de página enumerados
        total_pages = len(pages)
        for idx, p_cmds in enumerate(pages, start=1):
            p_cmds.append("0.8 0.8 0.8 RG 1 w")
            p_cmds.append("30 62 m 565 62 l S")
            p_cmds.append("0.4 0.4 0.4 rg")
            p_cmds.append(
                f"BT /F1 7 Tf 30 48 Td (Soporte contable P2P Merchant Engine - Horario VET UTC-4 | Pagina {idx} de {total_pages}) Tj ET"
            )

        # Construir objetos PDF 1.4 multipágina
        # Obj 1: Catalog, Obj 2: Pages, Obj 3: Font F1, Obj 4: Font F2, luego pares (Page, Stream)
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
            objects.append(
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
                f"/Contents {stream_num} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>\nendobj\n".encode("ascii")
            )
            objects.append(
                f"{stream_num} 0 obj\n<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
                + content_stream
                + b"\nendstream\nendobj\n"
            )

        pdf_bytes = bytearray(b"%PDF-1.4\n")
        xref_offsets = [0]
        for obj in objects:
            xref_offsets.append(len(pdf_bytes))
            pdf_bytes.extend(obj)

        xref_start = len(pdf_bytes)
        pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf_bytes.extend(b"0000000000 65535 f \n")
        for offset in xref_offsets[1:]:
            pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

        pdf_bytes.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
        )

        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        return output_path
