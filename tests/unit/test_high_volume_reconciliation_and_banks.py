"""Pruebas TDD (Fase 9 — SPEC-024): Banesco 2 columnas, Mercantil 2 columnas multilínea,
expansión de límites BDV/PDF, streaming OCR, conciliación alto volumen y entrada manual segura.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routes.accounting import (
    ManualVoucherRequest,
    StatementCommitRequest,
    StatementCommitRowRequest,
    create_manual_voucher,
)
from src.data.database import Base
from src.data.models import BankVoucher, FiscalPeriodSnapshot, JournalEntry, Order, User
from src.integrations.receipt_ocr import BankReceiptOCR
from src.integrations.statement_importer import (
    MAX_PDF_PAGES,
    MAX_STATEMENT_ROWS,
    BankStatementImporter,
    StatementCommitRow,
)
from src.reporting.accounting_engine import AccountingEngine
from src.reporting.fiscal_reconciler import FiscalReconciler
from src.security.file_guards import MAX_STATEMENT_UPLOAD_BYTES


def _build_landscape_pdf(
    pages_items: list[list[tuple[float, float, str]]],
    width: float = 792.0,
    height: float = 612.0,
) -> bytes:
    """Genera un PDF apaisado multipágina vectorial válido con posicionamiento exacto (x, y, texto)."""
    num_pages = max(1, len(pages_items))
    objs: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"",
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
    ]
    kid_refs: list[str] = []
    for i in range(num_pages):
        page_obj_id = 4 + 2 * i
        content_obj_id = 5 + 2 * i
        kid_refs.append(f"{page_obj_id} 0 R")
        items = pages_items[i] if i < len(pages_items) else []
        stream_cmds = ["BT", "/F1 4.5 Tf"]
        for x, y, text in items:
            safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_cmds.append(f"1 0 0 1 {x:.1f} {y:.1f} Tm ({safe}) Tj")
        stream_cmds.append("ET")
        stream_bytes = "\n".join(stream_cmds).encode("latin-1", errors="replace")
        objs.append(
            (
                f"{page_obj_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.0f} {height:.0f}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_id} 0 R >>\nendobj\n"
            ).encode("ascii")
        )
        objs.append(
            f"{content_obj_id} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream\nendobj\n"
        )

    objs[1] = f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(kid_refs)}] /Count {num_pages} >>\nendobj\n".encode("ascii")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_expanded_high_volume_limits_for_bdv_and_all_banks():
    """Los límites deben aguantar estados mensuales reales de comerciante P2P (>250 págs, >6,000 filas, 50 MB)."""
    assert MAX_STATEMENT_UPLOAD_BYTES >= 50 * 1024 * 1024
    assert MAX_PDF_PAGES >= 500
    assert MAX_STATEMENT_ROWS >= 25_000

    # El schema de commit REST también debe admitir lotes > 2,500 filas (hasta 25,000)
    rows_payload = [
        StatementCommitRowRequest(
            row_index=i,
            date_vet="2026-10-05",
            reference_number=f"99{i:06d}",
            concept="PAGO MOVIL",
            movement_type="DEBIT",
            amount_ves=100.0,
            action="IGNORE",
        )
        for i in range(3000)
    ]
    req = StatementCommitRequest(bank_name="Banco de Venezuela", rows=rows_payload)
    assert len(req.rows) == 3000


def test_banesco_multipage_two_column_landscape_and_implicit_pago_movil_fee():
    """Debe leer PDF real de Banesco: pág. 1 panel derecho + pág. 2 doble columna paralela y comisiones 0.30% implícitas."""
    # Página 1: Resumen izquierdo + Detalle de Movimientos en mitad derecha (x >= 400)
    p1: list[tuple[float, float, str]] = [
        (30, 580, "Banesco Banco Universal"),
        (600, 580, "Estado de Cuenta"),
        (30, 420, "RESUMEN DE MOVIMIENTOS"),
        (170, 420, "No. de Cuenta: 01340335063553020772"),
        (310, 420, "Periodo: 10-2026"),
        (30, 395, "Otros Debitos"),
        (190, 395, "6"),
        (280, 395, "250.991,76"),
        (30, 380, "Otros Creditos"),
        (190, 380, "2"),
        (280, 380, "1.661.400,00"),
        (30, 350, "RESUMEN DE SALDOS"),
        (30, 330, "Inicial"),
        (280, 330, "13.991,52"),
        (30, 315, "Final"),
        (280, 315, "1.424.399,76"),
        # Panel derecho: cabecera y 4 movimientos (incluyendo comisión implícita 0.30% en Banesco Pago Movil)
        (410, 510, "DETALLE DE MOVIMIENTOS"),
        (410, 495, "DIA"),
        (430, 495, "REF."),
        (490, 495, "CONCEPTO"),
        (615, 495, "CARGOS"),
        (670, 495, "ABONOS"),
        (730, 495, "SALDOS"),
        (490, 480, "SALDO MES ANTERIOR"),
        (725, 480, "13.991,52"),
        (410, 465, "01"),
        (430, 465, "62743609608"),
        (490, 465, "PAGO MOVIL CCE"),
        (610, 465, "10.000,00"),
        (725, 465, "3.991,52"),
        (410, 450, "01"),
        (430, 450, "62743609608"),
        (490, 450, "COM, PAGO MOVIL CCE"),
        (620, 450, "30,00"),
        (725, 450, "3.961,52"),
        (410, 435, "01"),
        (430, 435, "62745238400"),
        (490, 435, "Banesco Pago Movil"),
        (610, 435, "13.920,00"),
        (725, 435, "-9.958,48"),
        # Comisión implícita 0.30% (13.920 * 0.003 = 41,76) con MISMA ref y SIN palabra "COM"
        (410, 420, "01"),
        (430, 420, "62745238400"),
        (490, 420, "Banesco Pago Movil"),
        (620, 420, "41,76"),
        (725, 420, "-10.000,24"),
    ]

    # Página 2: DOS TABLAS PARALELAS LADO A LADO (izquierda x=30..380, derecha x=410..770)
    p2: list[tuple[float, float, str]] = [
        (30, 580, "Banesco Banco Universal"),
        (600, 580, "Estado de Cuenta"),
        (30, 530, "DETALLE DE MOVIMIENTOS (continuacion)"),
        (410, 530, "DETALLE DE MOVIMIENTOS (continuacion)"),
        # Cabecera izquierda
        (30, 512, "DIA"),
        (50, 512, "REF."),
        (110, 512, "CONCEPTO"),
        (235, 512, "CARGOS"),
        (290, 512, "ABONOS"),
        (345, 512, "SALDOS"),
        # Cabecera derecha (en la MISMA coordenada Y = 512!)
        (410, 512, "DIA"),
        (430, 512, "REF."),
        (490, 512, "CONCEPTO"),
        (615, 512, "CARGOS"),
        (670, 512, "ABONOS"),
        (730, 512, "SALDOS"),
        # Fila 1 izquierda y Fila 1 derecha a la MISMA Y = 495
        (30, 495, "02"),
        (50, 495, "62745262625"),
        (110, 495, "TRANS.CTAS. A TERCEROS BANESCO"),
        (280, 495, "1.000.000,00"),
        (338, 495, "989.999,76"),
        (410, 495, "02"),
        (430, 495, "62758122567"),
        (490, 495, "TRANS.CTAS. A TERCEROS BANESCO"),
        (610, 495, "100.000,00"),
        (720, 495, "1.551.399,76"),
        # Fila 2 izquierda y Fila 2 derecha a la MISMA Y = 480
        (30, 480, "02"),
        (50, 480, "62745250274"),
        (110, 480, "TRANS.CTAS. A TERCEROS BANESCO"),
        (280, 480, "661.400,00"),
        (338, 480, "1.651.399,76"),
        (410, 480, "02"),
        (430, 480, "62758200050"),
        (490, 480, "TRANS.CTAS. A TERCEROS BANESCO"),
        (610, 480, "127.000,00"),
        (720, 480, "1.424.399,76"),
    ]

    pdf_bytes = _build_landscape_pdf([p1, p2])
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="banesco_oct_2026.pdf")

    assert preview.bank_name == "BANESCO"
    assert preview.total_rows == 8  # 4 en pág. 1 + 2 izquierda pág. 2 + 2 derecha pág. 2
    assert preview.detected_order == "ASC"
    assert preview.balance_verified is True
    assert preview.balance_mismatch_count == 0
    assert preview.opening_balance == pytest.approx(13991.52, abs=0.02)
    assert preview.closing_balance == pytest.approx(1424399.76, abs=0.02)

    # Verificar orden cronológico estricto: pág. 1 -> panel izq pág. 2 -> panel der pág. 2
    refs = [r.reference_number for r in preview.rows]
    assert refs == [
        "62743609608",
        "62743609608",
        "62745238400",
        "62745238400",
        "62745262625",
        "62745250274",
        "62758122567",
        "62758200050",
    ]
    # Ambas comisiones (explícita COM, e implícita 0.30% de Banesco Pago Movil) deben quedar como BANK_FEE
    assert preview.rows[1].suggested_action == "BANK_FEE"
    assert preview.rows[1].amount_ves == 30.00
    assert preview.rows[3].suggested_action == "BANK_FEE"
    assert preview.rows[3].amount_ves == 41.76
    assert preview.bank_fee_count == 2
    assert preview.rows[4].movement_type == "CREDIT"
    assert preview.rows[4].amount_ves == 1000000.00
    assert preview.rows[7].movement_type == "DEBIT"
    assert preview.rows[7].amount_ves == 127000.00


def test_mercantil_two_column_multiline_counterparty_time_and_cover_summary_balance():
    """Debe leer PDF real de Mercantil Corriente: portada con año 2 dígitos, 2 columnas, NUMERO, multilínea y cuadre contra portada."""
    # Página 1: Portada sin tabla de movimientos, fechas DD-MM-AA y resumen con comas múltiples típicas de Mercantil
    p1: list[tuple[float, float, str]] = [
        (30, 570, "Mercantil Mas de un siglo"),
        (600, 560, "Estado de Cuenta Corriente"),
        (430, 440, "RESUMEN ESTADO DE CUENTA CORRIENTE"),
        (430, 415, "BANCO   OFICINA   D.C.   NRO. DE CUENTA   DESDE      HASTA"),
        (430, 400, "0105    0172      53     1172060088       01-10-26   31-10-26"),
        (430, 360, "SALDO AL INICIO DEL PERIODO:              2.020.338,46"),
        (430, 335, "MAS:            DEPOSITOS EFECTUADOS POR  0,00"),
        (430, 320, "                1 OTROS CREDITOS A SU CUENTA  150,000,00"),
        (430, 290, "MENOS:          CHEQUES DEBITADOS POR     0,00"),
        (430, 275, "                3 OTROS DEBITOS A SU CUENTA   16.428,20"),
        (430, 245, "SALDO AL FINAL DEL PERIODO: 31-10-26      2.153.910,26"),
        (430, 120, "Mercantil, C.A., Banco Universal RIF: J-00002961-0"),
    ]

    # Página 2: 2 columnas paralelas con descripciones multilínea, salto de columna y SALDO vacío en movimientos
    p2: list[tuple[float, float, str]] = [
        (30, 560, "MOVIMIENTOS DE CUENTA"),
        (410, 560, "MOVIMIENTOS DE CUENTA"),
        # Cabecera izquierda
        (30, 540, "FECHA"),
        (65, 540, "NUMERO"),
        (115, 540, "DESCRIPCION"),
        (250, 540, "CARGOS"),
        (295, 540, "ABONOS"),
        (335, 540, "SALDO"),
        (370, 540, "IMPUESTO"),
        # Cabecera derecha (MISMA Y = 540)
        (410, 540, "FECHA"),
        (445, 540, "NUMERO"),
        (495, 540, "DESCRIPCION"),
        (630, 540, "CARGOS"),
        (675, 540, "ABONOS"),
        (715, 540, "SALDO"),
        (750, 540, "IMPUESTO"),
        # Panel izquierdo: SALDO AL INICIO (debe ignorarse) + Comisión T-Pago + Transferencia (cuya última línea salta al panel derecho!)
        (30, 520, "01/10"),
        (115, 520, "SALDO AL INICIO DEL PERIODO"),
        (330, 520, "2.020.338,46"),
        (30, 502, "01/10"),
        (65, 502, "32338873"),
        (115, 502, "COMISION POR SOLICITUD DE ENVIO DE CREDITO"),
        (250, 502, "28,20"),
        (115, 492, "INMEDIATO A LA CCE, A TRAVES DE T-PAGO"),
        (115, 482, "A V90026775"),
        (115, 472, "POR BS. 9.400,00"),
        (115, 462, "EL 01-10-26 A LAS 19:19:41 HORAS"),
        # Segundo movimiento izquierdo: T-Pago principal
        (30, 444, "01/10"),
        (65, 444, "32338873"),
        (115, 444, "OPERACION DE CREDITO INMEDIATO - TRANSF. PRES"),
        (248, 444, "9.400,00"),
        (115, 434, "A LA CCE A TRAVES DE T-PAGO A V90026775"),
        (115, 424, "EN BANCAMIGA BANCO UNIVERSAL"),
        (115, 414, "POR CONCEPTO DE: PAGO MOVIL."),
        # Tercer movimiento izquierdo (termina en el panel derecho!)
        (30, 396, "01/10"),
        (65, 396, "00487452"),
        (115, 396, "TRANSFERENCIA DESDE LA CUENTA ***0088 A LA CU"),
        (248, 396, "7.000,00"),
        (115, 386, "ENTA DE JESUS FAJARDO ***8921 POR BS. 7,000,0"),
        # Panel derecho: continuación huérfana de JESUS FAJARDO + 1 abono crédito
        (495, 520, "0 REALIZADA EN MERCANTIL PERSONAS EL 01/10/20"),
        (495, 510, "EL 01-10-26 A LAS 17:18:57 HORAS"),
        (410, 490, "01/10"),
        (445, 490, "00991122"),
        (495, 490, "ABONO TRANSFERENCIA DESDE CUENTA DE ANA PEREZ"),
        (670, 490, "150.000,00"),
        (495, 480, "EL 01-10-26 A LAS 18:05:10 HORAS"),
    ]

    pdf_bytes = _build_landscape_pdf([p1, p2])
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="mercantil_oct_2026.pdf")

    assert preview.bank_name == "MERCANTIL"
    assert preview.total_rows == 4
    assert preview.balance_verified is True
    assert preview.opening_balance == pytest.approx(2020338.46, abs=0.02)
    assert preview.closing_balance == pytest.approx(2153910.26, abs=0.02)

    r_fee, r_tpago, r_transf, r_credit = preview.rows
    assert r_fee.date_vet == "2026-10-01"
    assert r_fee.reference_number == "32338873"
    assert r_fee.suggested_action == "BANK_FEE"
    assert r_fee.amount_ves == 28.20
    assert r_fee.sender_id == "V-90026775"
    assert r_fee.tx_time_vet == "19:19:41"

    assert r_tpago.reference_number == "32338873"
    assert r_tpago.amount_ves == 9400.00
    assert r_tpago.payment_method == "PAGO_MOVIL"
    assert r_tpago.sender_id == "V-90026775"
    assert r_tpago.destination_bank == "BANCAMIGA"

    assert r_transf.reference_number == "00487452"
    assert r_transf.amount_ves == 7000.00
    assert r_transf.counterparty_name == "JESUS FAJARDO"
    assert r_transf.tx_time_vet == "17:18:57"
    # La hora VET 17:18:57 debe haberse trasladado a voucher_datetime_utc = 21:18:57 UTC
    assert r_transf.voucher_datetime_utc.hour == 21
    assert r_transf.voucher_datetime_utc.minute == 18

    assert r_credit.movement_type == "CREDIT"
    assert r_credit.amount_ves == 150000.00
    assert r_credit.tx_time_vet == "18:05:10"


def test_reconciliation_disambiguates_round_amounts_by_bank_and_prevents_double_fee_and_limit_bypass():
    """En alto volumen: desambigua montos redondos repetidos por banco/contraparte, evita doble comisión y no falla tras >2,000 vouchers."""
    db = _make_db()
    try:
        user = User(username="hv_merchant", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        vet_tz = timezone(timedelta(hours=-4))
        dt_merc = datetime(2026, 10, 5, 14, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        dt_bane = datetime(2026, 10, 5, 14, 5, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)

        # Dos órdenes BUY idénticas de Bs. 100.000,00 el mismo día, una en Mercantil y otra en Banesco
        ord_merc = Order(
            user_id=user.id,
            order_number="ORD-MERC-100K",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=100000.00,
            crypto_amount=100.0,
            unit_price=1000.0,
            bcv_rate=860.0,
            order_status="COMPLETED",
            counterparty_name="Carlos Quintero",
            payment_method="Mercantil",
            created_at=dt_merc,
        )
        ord_bane = Order(
            user_id=user.id,
            order_number="ORD-BANE-100K",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=100000.00,
            crypto_amount=100.0,
            unit_price=1000.0,
            bcv_rate=860.0,
            order_status="COMPLETED",
            counterparty_name="Pedro Perez",
            payment_method="Banesco",
            created_at=dt_bane,
        )
        # Orden BUY de 10.000 Bs ya conciliada con capture previo que YA incluyó la comisión de 30 Bs
        ord_prev = Order(
            user_id=user.id,
            order_number="ORD-PREV-10K",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=10000.00,
            crypto_amount=10.0,
            unit_price=1000.0,
            bcv_rate=860.0,
            order_status="COMPLETED",
            payment_method="Banesco",
            created_at=dt_bane,
        )
        prev_voucher = BankVoucher(
            user_id=user.id,
            bank_name="BANESCO",
            reference_number="62743609608",
            amount_ves=10000.00,
            bank_fee_ves=30.00,
            total_debited_ves=10030.00,
            movement_type="DEBIT",
            payment_method="PAGO_MOVIL",
            associated_order_number="ORD-PREV-10K",
            verification_status="MATCHED",
            voucher_date=dt_bane,
        )
        db.add_all([ord_merc, ord_bane, ord_prev, prev_voucher])
        db.commit()

        # Importar estado Banesco: debe cruzar 100.000 con ORD-BANE-100K (NO con ORD-MERC-100K)
        # y marcar TANTO el pago 10.000 como su línea de comisión 30,00 (misma ref) como DUPLICATE_EXISTING!
        csv_banesco = (
            b"BANESCO BANCO UNIVERSAL\n"
            b"Fecha,Referencia,Concepto,Cargos,Abonos,Saldo\n"
            b"05/10/2026,62743609608,PAGO MOVIL CCE,10000.00,0.00,200000.00\n"
            b"05/10/2026,62743609608,COM PAGO MOVIL CCE,30.00,0.00,199970.00\n"
            b"05/10/2026,62749999999,TRANS CTAS A TERCEROS BANESCO,100000.00,0.00,99970.00\n"
        )
        importer = BankStatementImporter()
        preview = importer.preview_from_bytes(
            file_bytes=csv_banesco,
            filename="banesco_oct.csv",
            bank_name="Banesco",
            db=db,
            user_id=user.id,
        )

        assert preview.rows[0].suggested_action == "DUPLICATE_EXISTING"
        assert preview.rows[1].suggested_action == "DUPLICATE_EXISTING"  # Anti-doble-comisión!
        assert preview.rows[2].suggested_action == "P2P_MATCH"
        assert preview.rows[2].matched_order_number == "ORD-BANE-100K"
    finally:
        db.close()


def test_reconcile_orphan_vouchers_enforces_direction_and_no_500_limit():
    """reconcile_orphan_vouchers jamás debe cruzar un DEBIT con una orden SELL (ni viceversa)."""
    db = _make_db()
    try:
        now = datetime(2026, 10, 10, 15, 0, 0, tzinfo=UTC)
        # Orden SELL de 50.000 Bs (espera CREDIT), pero el comprobante huérfano es DEBIT (egreso)
        sell_order = Order(
            order_number="ORD-SELL-50K",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=50000.00,
            crypto_amount=50.0,
            unit_price=1000.0,
            order_status="COMPLETED",
            created_at=now,
        )
        debit_voucher = BankVoucher(
            bank_name="BANESCO",
            reference_number="99887766",
            amount_ves=50000.00,
            bank_fee_ves=0.0,
            total_debited_ves=50000.00,
            movement_type="DEBIT",
            payment_method="TRANSFERENCIA",
            verification_status="UNMATCHED",
            voucher_date=now,
        )
        db.add_all([sell_order, debit_voucher])
        db.commit()

        count = BankReceiptOCR().reconcile_orphan_vouchers(db=db, tolerance_hours=48)
        assert count == 0
        db.refresh(debit_voucher)
        assert debit_voucher.verification_status == "UNMATCHED"
        assert debit_voucher.associated_order_number is None
    finally:
        db.close()


def test_manual_voucher_supports_date_vet_action_interbank_fee_closed_period_and_safe_direction():
    """La entrada manual debe respetar date_vet, tipo contable, comisión 0.3% interbancaria, mes cerrado y sentido BUY/SELL."""
    db = _make_db()
    try:
        user = User(username="manual_trader", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        vet_tz = timezone(timedelta(hours=-4))
        dt_oct10 = datetime(2026, 10, 10, 14, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        # Orden SELL (espera CREDIT) el 10/10 por 10.000 Bs
        db.add(
            Order(
                user_id=user.id,
                order_number="ORD-SELL-10K",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                fiat_amount=10000.00,
                crypto_amount=10.0,
                unit_price=1000.0,
                order_status="COMPLETED",
                created_at=dt_oct10,
            )
        )
        db.commit()

        # 1. DEBIT INTERBANK con date_vet=2026-10-10: debe cobrar 0.3% (30 Bs), NO cruzar con ORD-SELL-10K, y quedar en octubre
        res_deb = create_manual_voucher(
            payload=ManualVoucherRequest(
                bank_name="Banesco",
                reference_number="MAN-001",
                amount_ves=10000.00,
                movement_type="DEBIT",
                payment_method="INTERBANK",
                date_vet="2026-10-10",
            ),
            db=db,
            current_user=user,
        )
        assert res_deb["bank_fee_ves"] == 30.00
        assert res_deb["matched_order_number"] is None
        saved_v = db.query(BankVoucher).filter(BankVoucher.id == res_deb["voucher_id"]).first()
        assert saved_v is not None
        assert saved_v.voucher_date.month == 10 and saved_v.voucher_date.day == 10

        # 2. Comisión bancaria manual suelta (action="BANK_FEE") -> asienta en 5.2.01 sin cruzar con orden
        res_fee = create_manual_voucher(
            payload=ManualVoucherRequest(
                bank_name="Mercantil",
                reference_number="MAN-FEE-01",
                amount_ves=45.00,
                movement_type="DEBIT",
                payment_method="TRANSFERENCIA",
                date_vet="2026-10-12",
                action="BANK_FEE",
            ),
            db=db,
            current_user=user,
        )
        assert res_fee["verification_status"] == "MATCHED"
        fee_entries = db.query(JournalEntry).filter(JournalEntry.voucher_id == res_fee["voucher_id"]).all()
        assert any(e.account_code == "5.2.01" and e.debit == 45.00 for e in fee_entries)

        # 3. Bloqueo Fail-Closed en mes cerrado
        db.add(
            FiscalPeriodSnapshot(
                user_id=user.id,
                period="2026-09",
                initial_balance=0.0,
                calculated_final_balance=0.0,
                actual_final_balance=0.0,
                status="BALANCED",
            )
        )
        db.commit()
        with pytest.raises(HTTPException) as exc_closed:
            create_manual_voucher(
                payload=ManualVoucherRequest(
                    bank_name="Banesco",
                    reference_number="MAN-SEP-01",
                    amount_ves=100.00,
                    movement_type="CREDIT",
                    date_vet="2026-09-15",
                ),
                db=db,
                current_user=user,
            )
        assert exc_closed.value.status_code == 409
    finally:
        db.close()


def test_vet_end_of_month_boundary_consistency_in_accounting_and_fiscal():
    """Una orden del 31/10 a las 22:00 VET (01/11 02:00 UTC) debe contar en OCTUBRE, nunca en noviembre."""
    db = _make_db()
    try:
        user = User(username="vet_user", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        vet_tz = timezone(timedelta(hours=-4))
        oct31_night_utc = datetime(2026, 10, 31, 22, 0, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        assert oct31_night_utc.month == 11 and oct31_night_utc.day == 1  # En UTC ya es 1 de noviembre!

        db.add(
            Order(
                user_id=user.id,
                order_number="ORD-OCT31-NIGHT",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=10000.0,
                crypto_amount=10.0,
                unit_price=1000.0,
                bcv_rate=889.2553,
                order_status="COMPLETED",
                created_at=oct31_night_utc,
            )
        )
        db.commit()

        fres_oct = FiscalReconciler(db_session=db, user_id=int(user.id)).reconcile_period(
            period="2026-10",
            initial_balance=0.0,
            initial_bcv_rate=860.0,
        )
        fres_nov = FiscalReconciler(db_session=db, user_id=int(user.id)).reconcile_period(
            period="2026-11",
            initial_balance=0.0,
            initial_bcv_rate=890.0,
        )
        assert fres_oct.orders_count == 1
        assert fres_nov.orders_count == 0

        live_oct = AccountingEngine(db=db, user_id=int(user.id)).get_live_theoretical_balance(year=2026, month=10)
        live_nov = AccountingEngine(db=db, user_id=int(user.id)).get_live_theoretical_balance(year=2026, month=11)
        assert live_oct.inflow_usdt == 10.0
        assert live_nov.inflow_usdt == 0.0
    finally:
        db.close()


def test_atomic_batch_commit_preserves_sha256_chain_for_large_statement():
    """El commit en lote debe preservar cadena SHA-256 perfecta y sumas iguales sobre cientos de filas en una transacción."""
    db = _make_db()
    try:
        user = User(username="batch_trader", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        rows = [
            StatementCommitRow(
                row_index=i,
                date_vet="2026-10-05",
                reference_number=f"7700{i:04d}",
                concept=f"COMISION PAGO MOVIL {i}",
                movement_type="DEBIT",
                amount_ves=10.0,
                payment_method="PAGO_MOVIL",
                action="BANK_FEE",
                bank_fee_ves=10.0,
            )
            for i in range(120)
        ]
        res = BankStatementImporter().commit_rows(
            db=db,
            user_id=int(user.id),
            bank_name="BANESCO",
            rows=rows,
        )
        assert res.created_vouchers == 120
        assert res.bank_fees_recorded == 120
        assert res.journal_entries_created == 240

        entries = (
            db.query(JournalEntry)
            .filter(JournalEntry.user_id == user.id)
            .order_by(JournalEntry.entry_number.asc(), JournalEntry.id.asc())
            .all()
        )
        assert len(entries) == 240
        assert round(sum(e.debit for e in entries), 2) == round(sum(e.credit for e in entries), 2) == 1200.00
        # Verificar cadena SHA-256 lineal ininterrumpida
        for idx in range(1, len(entries)):
            assert entries[idx].prev_hash == entries[idx - 1].entry_hash
    finally:
        db.close()


def test_surgical_per_page_ocr_only_runs_tesseract_on_problematic_pages():
    """En modo PDF OCR, Tesseract solo debe re-procesar las páginas con descuadre/duda, no todo el documento."""
    from PIL import Image

    tess_calls: list[int] = []

    def _mk_page_words(page_idx: int, bad_bal: bool = False) -> tuple[list[dict[str, object]], float]:
        bal1 = "999,00" if bad_bal else f"{1000 + (page_idx + 1) * 100:.2f}".replace(".", ",")
        return (
            [
                {"text": "Banesco", "x0": 30.0, "x1": 100.0, "top": 10.0, "bottom": 20.0},
                {"text": "Fecha", "x0": 30.0, "x1": 70.0, "top": 35.0, "bottom": 45.0},
                {"text": "Referencia", "x0": 110.0, "x1": 175.0, "top": 35.0, "bottom": 45.0},
                {"text": "Concepto", "x0": 210.0, "x1": 290.0, "top": 35.0, "bottom": 45.0},
                {"text": "Cargos", "x0": 390.0, "x1": 440.0, "top": 35.0, "bottom": 45.0},
                {"text": "Abonos", "x0": 465.0, "x1": 515.0, "top": 35.0, "bottom": 45.0},
                {"text": "Saldo", "x0": 540.0, "x1": 590.0, "top": 35.0, "bottom": 45.0},
                {"text": f"0{page_idx + 1}/10/2026", "x0": 30.0, "x1": 85.0, "top": 60.0, "bottom": 70.0},
                {"text": f"50000{page_idx}", "x0": 110.0, "x1": 165.0, "top": 60.0, "bottom": 70.0},
                {"text": "ABONO PAGO MOVIL", "x0": 210.0, "x1": 320.0, "top": 60.0, "bottom": 70.0},
                {"text": "100,00", "x0": 465.0, "x1": 515.0, "top": 60.0, "bottom": 70.0},
                {"text": bal1, "x0": 540.0, "x1": 595.0, "top": 60.0, "bottom": 70.0},
            ],
            0.95,
        )

    # 4 páginas: páginas 0, 1, 3 perfectas; solo página 2 tiene saldo corrupto en RapidOCR
    rapid_idx = {"i": 0}

    def fake_rapid(_img: Image.Image):
        idx = rapid_idx["i"]
        rapid_idx["i"] += 1
        return _mk_page_words(idx, bad_bal=(idx == 2))

    def fake_tess(img: Image.Image):
        # Identificar qué página llegó por un pixel marcador en (0, 0)
        p_idx = int(img.getpixel((0, 0))[0])
        tess_calls.append(p_idx)
        return _mk_page_words(p_idx, bad_bal=False)

    imgs = []
    for i in range(4):
        im = Image.new("RGB", (60, 40), (i, 0, 0))
        imgs.append(im)

    importer = BankStatementImporter(ocr_engines={"rapidocr": fake_rapid, "tesseract": fake_tess})
    res = importer._extract_with_dual_ocr(
        images=imgs,
        file_type="PDF",
        method_prefix="PDF_OCR",
        filename="banesco_4pags.pdf",
        bank_name_override="Banesco",
        default_year=2026,
        extra_warnings=[],
    )

    assert res.total_rows == 4
    assert res.balance_verified is True
    assert res.balance_mismatch_count == 0
    # Tesseract NO debe haber corrido en las 4 páginas completas, solo en la zona del descuadre (<= 2 págs)
    assert 0 < len(tess_calls) < 4
    assert 2 in tess_calls


def test_pdfplumber_flushes_page_cache_and_reports_progress():
    """Debe purgar caché de cada página de pdfplumber (anti-OOM 4GB en PDFs largos) y reportar progreso."""
    from unittest.mock import patch

    import pdfplumber

    pages: list[list[tuple[float, float, str]]] = []
    running = 1000.0
    for i in range(4):
        running = round(running + 100.0, 2)
        bal = f"{running:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        items: list[tuple[float, float, str]] = []
        if i == 0:
            items.append((30, 580, "Banco de Venezuela"))
        items.extend(
            [
                (30, 520, "Fecha"),
                (110, 520, "Referencia"),
                (200, 520, "Descripcion"),
                (450, 520, "Abonos"),
                (550, 520, "Saldo"),
                (30, 500, f"0{i + 1}/10/2026"),
                (110, 500, f"70000{i}"),
                (200, 500, f"ABONO CLIENTE {i + 1}"),
                (450, 500, "100,00"),
                (550, 500, bal),
            ]
        )
        pages.append(items)

    pdf_bytes = _build_landscape_pdf(pages)
    flushed_pages = {"count": 0}
    progress_events: list[tuple[int, int, str]] = []

    orig_open = pdfplumber.open

    def _wrapped_open(*args, **kwargs):
        doc = orig_open(*args, **kwargs)
        for pg in doc.pages:
            orig_flush = pg.flush_cache

            def _counting_flush(_orig=orig_flush):
                flushed_pages["count"] += 1
                return _orig()

            pg.flush_cache = _counting_flush
        return doc

    importer = BankStatementImporter()
    with patch("src.integrations.statement_importer.pdfplumber.open", side_effect=_wrapped_open):
        preview = importer.parse_bytes(
            file_bytes=pdf_bytes,
            filename="bdv_4pags.pdf",
            progress_callback=lambda d, t, s: progress_events.append((d, t, s)),
        )

    assert preview.total_rows == 4
    assert preview.balance_verified is True
    assert flushed_pages["count"] == 4
    assert progress_events == [
        (1, 4, "Leyendo PDF"),
        (2, 4, "Leyendo PDF"),
        (3, 4, "Leyendo PDF"),
        (4, 4, "Leyendo PDF"),
        (4, 4, "Estructurando filas"),
    ]


def test_async_statement_preview_job_completes_and_enforces_user_isolation():
    """El preview asíncrono debe completar en segundo plano y aislar estrictamente el job_id por user_id (OWASP A01)."""
    import io as _io
    import time as _time

    from starlette.datastructures import UploadFile

    from src.api.routes.accounting import (
        get_preview_bank_statement_job,
        start_preview_bank_statement_job,
    )

    db = _make_db()
    try:
        u1 = User(username="trader_async_1", password_hash="x", role="TRADER", is_active=True)
        u2 = User(username="trader_async_2", password_hash="x", role="TRADER", is_active=True)
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)

        csv_bytes = (
            b"Fecha,Referencia,Concepto,Debito,Credito,Saldo\n"
            b"01/10/2026,99112233,PAGO MOVIL CLIENTE,0,500.00,1500.00\n"
            b"02/10/2026,99112244,COMISION PAGO MOVIL,1.50,0,1498.50\n"
        )
        up = UploadFile(filename="bdv_oct.csv", file=_io.BytesIO(csv_bytes))
        started = start_preview_bank_statement_job(
            file=up,
            db=db,
            current_user=u1,
            bank_name="Banco de Venezuela",
        )
        assert started.job_id

        # Otro usuario NO puede leer el job ajeno (OWASP A01)
        with pytest.raises(HTTPException) as exc_info:
            get_preview_bank_statement_job(job_id=started.job_id, current_user=u2)
        assert exc_info.value.status_code == 404

        # Esperar finalización del hilo de trabajo
        final_status = None
        for _ in range(50):
            st = get_preview_bank_statement_job(job_id=started.job_id, current_user=u1)
            if st.status in ("COMPLETED", "FAILED"):
                final_status = st
                break
            _time.sleep(0.05)

        assert final_status is not None
        assert final_status.status == "COMPLETED"
        assert final_status.result is not None
        assert final_status.result.total_rows == 2
        assert final_status.result.balance_verified is True
        assert final_status.result.bank_fee_count == 1
    finally:
        db.close()
