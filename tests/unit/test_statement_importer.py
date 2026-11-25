"""Pruebas unitarias e integración (TDD) para el Importador Universal de Estados de Cuenta (SPEC-024)."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.data.database import Base
from src.data.models import BankVoucher, FiscalPeriodSnapshot, JournalEntry, Order, User
from src.integrations.statement_importer import (
    BankStatementImporter,
    StatementCommitRow,
)
from src.reporting.fiscal_reconciler import FiscalReconciler


def _build_positioned_pdf(pages_items: list[list[tuple[float, float, str]]]) -> bytes:
    """Genera un PDF multipágina vectorial válido con posicionamiento cartesiano exacto (x, y, texto)."""
    num_pages = max(1, len(pages_items))
    # obj 1: Catalog, obj 2: Pages, obj 3: Font, then per-page: Page (4 + 2*i), Contents (5 + 2*i)
    objs: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"",  # placeholder Pages
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
    ]
    kid_refs: list[str] = []
    for i in range(num_pages):
        page_obj_id = 4 + 2 * i
        content_obj_id = 5 + 2 * i
        kid_refs.append(f"{page_obj_id} 0 R")
        items = pages_items[i] if i < len(pages_items) else []
        stream_cmds = ["BT", "/F1 8 Tf"]
        for x, y, text in items:
            safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_cmds.append(f"1 0 0 1 {x:.1f} {y:.1f} Tm ({safe}) Tj")
        stream_cmds.append("ET")
        stream_bytes = "\n".join(stream_cmds).encode("latin-1", errors="replace")
        objs.append(
            (
                f"{page_obj_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_id} 0 R >>\nendobj\n"
            ).encode("ascii")
        )
        objs.append(
            f"{content_obj_id} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream\nendobj\n"
        )

    kids_str = " ".join(kid_refs)
    objs[1] = f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>\nendobj\n".encode("ascii")

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
        (
            f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def _build_minimal_pdf(lines: list[str]) -> bytes:
    """Genera un PDF vectorial válido en memoria con posicionamiento X/Y para pruebas deterministas."""
    items: list[tuple[float, float, str]] = []
    y = 750.0
    for line in lines:
        items.append((36.0, y, line))
        y -= 16.0
    return _build_positioned_pdf([items])


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_parse_csv_universal_venezuelan_and_international_formats():
    """Debe detectar encabezados tras filas de título, punto/coma decimal y validar cuadre de saldo."""
    csv_text = (
        b"BANCO NACIONAL DE CREDITO (BNC)\n"
        b"CUENTA CORRIENTE;0191-0001-11-1234567890\n\n"
        b"Fecha Operacion;Nro Referencia;Descripcion Movimiento;Debitos;Creditos;Saldo Disponible\n"
        b"01/11/2026;88001122;PAGO MOVIL ENVIADO C2P;1.500,50;0,00;8.499,50\n"
        b"01/11/2026;88001123;COMISION PAGO MOVIL INTERBANCARIO;4,50;0,00;8.495,00\n"
        b"02/11/2026;99004455;ABONO PAGO MOVIL RECIBIDO 0134;0,00;3.200,00;11.695,00\n"
    )

    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=csv_text, filename="estado_bnc.csv")

    assert preview.bank_name == "BNC"
    assert preview.file_type == "CSV"
    assert preview.total_rows == 3
    assert preview.balance_verified is True
    assert preview.balance_mismatch_count == 0
    assert preview.detected_order == "ASC"

    r0, r1, r2 = preview.rows
    assert r0.movement_type == "DEBIT"
    assert r0.amount_ves == 1500.50
    assert r0.payment_method == "PAGO_MOVIL"
    assert r1.suggested_action == "BANK_FEE"
    assert r1.amount_ves == 4.50
    assert r2.movement_type == "CREDIT"
    assert r2.amount_ves == 3200.00
    assert r2.balance_ves == 11695.00


def test_parse_csv_detects_balance_mismatch_and_supports_custom_column_mapping():
    """Debe señalar discrepancias matemáticas de saldo (Fail-Closed) y aceptar mapeo manual de columnas."""
    csv_weird = (
        b"DiaOper;CodigoTx;Glosa;ImpConSigno;RestoFinal\n"
        b"2026-11-05;REF-01;Pago proveedor;-200.00;800.00\n"
        b"2026-11-06;REF-02;Cobro cliente;+500.00;1400.00\n"  # Esperado: 1300.00 -> Discrepancia 100.00
    )

    importer = BankStatementImporter()
    # Sin mapeo manual, si las columnas tienen nombres raros pide o intenta detectar; con mapeo explícito siempre funciona
    preview = importer.parse_bytes(
        file_bytes=csv_weird,
        filename="banco_extranjero.csv",
        bank_name="Mercantil Panama",
        column_mapping={
            "date": "DiaOper",
            "reference": "CodigoTx",
            "concept": "Glosa",
            "amount": "ImpConSigno",
            "balance": "RestoFinal",
        },
    )

    assert preview.bank_name == "MERCANTIL"
    assert preview.total_rows == 2
    assert preview.balance_verified is False
    assert preview.balance_mismatch_count == 1
    assert preview.rows[1].balance_ok is False
    assert abs(preview.rows[1].balance_discrepancy - 100.00) < 0.01


def test_parse_native_pdf_multiline_bdv_style_and_descending_order():
    """Debe leer PDFs nativos estilo BDV/Banesco, unir descripciones multilínea e inferir orden DESC."""
    pdf_bytes = _build_minimal_pdf(
        [
            "BANCO DE VENEZUELA S.A. BANCO UNIVERSAL",
            "ESTADO DE CUENTA DEL 01/11/2026 AL 30/11/2026",
            "Fecha      Referencia    Concepto                         Cargos      Abonos        Saldo",
            "15/11/2026 50713000999   PAGO MOVIL RECIBIDO                           5.000,00    13.500,00",
            "                         DESDE EL NUMERO 0134-****1234",
            "14/11/2026 50713000888   PAGO MOVIL ENVIADO               1.500,00                  8.500,00",
        ]
    )

    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="bdv_noviembre.pdf")

    assert preview.bank_name == "BANCO DE VENEZUELA"
    assert preview.file_type == "PDF"
    assert preview.total_rows == 2
    assert preview.detected_order == "DESC"
    assert preview.balance_verified is True

    latest = preview.rows[0]
    assert latest.movement_type == "CREDIT"
    assert latest.amount_ves == 5000.00
    assert latest.reference_number == "50713000999"
    assert "DESDE EL NUMERO 0134" in latest.concept
    assert preview.rows[1].movement_type == "DEBIT"
    assert preview.rows[1].amount_ves == 1500.00


def test_preview_reconciles_with_orders_deduplicates_and_isolates_non_p2p_on_commit():
    """Debe cruzar en VET, evitar duplicados vs captures previos, aislar gastos personales y asentar Libro Diario."""
    db = _make_db()
    try:
        user = User(username="trader_stmt", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        # Orden P2P BUY 02/11/2026 23:30 UTC => 19:30 VET del 02/11/2026
        ord1 = Order(
            user_id=user.id,
            order_number="ORD-STMT-BUY-1",
            trade_type="BUY",
            asset="USDT",
            fiat="VES",
            fiat_amount=4000.00,
            crypto_amount=10.0,
            unit_price=400.00,
            fee_fiat=0.0,
            bcv_rate=390.0,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 3, 2, 0, 0, tzinfo=UTC),  # 2026-11-02 22:00 VET!
        )
        # Orden P2P SELL ya conciliada con capture previo -> debe marcarse DUPLICATE_EXISTING en el PDF/CSV
        ord2 = Order(
            user_id=user.id,
            order_number="ORD-STMT-SELL-PREV",
            trade_type="SELL",
            asset="USDT",
            fiat="VES",
            fiat_amount=2200.00,
            crypto_amount=5.0,
            unit_price=440.00,
            fee_fiat=0.0,
            bcv_rate=390.0,
            order_status="COMPLETED",
            created_at=datetime(2026, 11, 2, 16, 0, 0, tzinfo=UTC),
        )
        existing_voucher = BankVoucher(
            user_id=user.id,
            bank_name="BANESCO",
            reference_number="11223344",
            amount_ves=2200.00,
            bank_fee_ves=0.0,
            movement_type="CREDIT",
            payment_method="PAGO_MOVIL",
            associated_order_number="ORD-STMT-SELL-PREV",
            verification_status="MATCHED",
            voucher_date=datetime(2026, 11, 2, 16, 5, 0, tzinfo=UTC),
        )
        db.add_all([ord1, ord2, existing_voucher])
        db.commit()

        csv_bytes = (
            b"Fecha,Referencia,Concepto,Debito,Credito,Saldo\n"
            b"02/11/2026,11223344,PAGO MOVIL RECIBIDO,0.00,2200.00,12200.00\n"
            b"02/11/2026,55667788,PAGO MOVIL COMPRA CRIPTO,4000.00,0.00,8200.00\n"
            b"02/11/2026,55667789,COMISION PAGO MOVIL,12.00,0.00,8188.00\n"
            b"03/11/2026,99900011,COMPRA AUTOMERCADO GASTO PERSONAL,350.00,0.00,7838.00\n"
        )

        importer = BankStatementImporter()
        preview = importer.preview_from_bytes(
            file_bytes=csv_bytes,
            filename="banesco_nov.csv",
            bank_name="Banesco",
            db=db,
            user_id=user.id,
        )

        assert preview.duplicate_count == 1
        assert preview.p2p_matched_count == 1
        assert preview.bank_fee_count == 1
        assert preview.unmatched_count == 1

        assert preview.rows[0].suggested_action == "DUPLICATE_EXISTING"
        assert preview.rows[1].suggested_action == "P2P_MATCH"
        assert preview.rows[1].matched_order_number == "ORD-STMT-BUY-1"
        assert preview.rows[2].suggested_action == "BANK_FEE"
        assert preview.rows[3].suggested_action == "P2P_UNMATCHED"

        # Commit aprobando orden P2P y comisión, pero excluyendo gasto personal del supermercado (IGNORE)
        commit_rows = [
            StatementCommitRow(
                row_index=preview.rows[0].row_index,
                date_vet=preview.rows[0].date_vet,
                reference_number=preview.rows[0].reference_number,
                concept=preview.rows[0].concept,
                movement_type=preview.rows[0].movement_type,
                amount_ves=preview.rows[0].amount_ves,
                payment_method=preview.rows[0].payment_method,
                action="IGNORE",  # Duplicado ignorado
            ),
            StatementCommitRow(
                row_index=preview.rows[1].row_index,
                date_vet=preview.rows[1].date_vet,
                reference_number=preview.rows[1].reference_number,
                concept=preview.rows[1].concept,
                movement_type=preview.rows[1].movement_type,
                amount_ves=preview.rows[1].amount_ves,
                payment_method=preview.rows[1].payment_method,
                action="P2P_MATCH",
                order_number="ORD-STMT-BUY-1",
            ),
            StatementCommitRow(
                row_index=preview.rows[2].row_index,
                date_vet=preview.rows[2].date_vet,
                reference_number=preview.rows[2].reference_number,
                concept=preview.rows[2].concept,
                movement_type=preview.rows[2].movement_type,
                amount_ves=preview.rows[2].amount_ves,
                payment_method=preview.rows[2].payment_method,
                action="BANK_FEE",
            ),
            StatementCommitRow(
                row_index=preview.rows[3].row_index,
                date_vet=preview.rows[3].date_vet,
                reference_number=preview.rows[3].reference_number,
                concept=preview.rows[3].concept,
                movement_type=preview.rows[3].movement_type,
                amount_ves=preview.rows[3].amount_ves,
                payment_method=preview.rows[3].payment_method,
                action="IGNORE",  # Gasto personal excluido para no dañar SENIAT
            ),
        ]

        res = importer.commit_rows(
            db=db,
            user_id=user.id,
            bank_name=preview.bank_name,
            rows=commit_rows,
        )

        assert res.created_vouchers == 2  # Solo P2P match + Bank Fee (gasto personal y duplicado excluidos)
        assert res.matched_orders == 1
        assert res.bank_fees_recorded == 1
        assert res.ignored_rows == 2

        entries = db.query(JournalEntry).filter(JournalEntry.user_id == user.id).all()
        assert len(entries) > 0
        total_debe = round(sum(e.debit for e in entries), 2)
        total_haber = round(sum(e.credit for e in entries), 2)
        assert total_debe == total_haber  # Sumas iguales inviolables
        assert not any("AUTOMERCADO" in (e.description or "") for e in entries)

        # Verificar que el reconciliador fiscal contempla la comisión bancaria deducible
        fiscal = FiscalReconciler(db, user_id=user.id).reconcile_period("2026-11")
        assert fiscal.total_fees_ves >= 12.00
    finally:
        db.close()


def test_fail_closed_invalid_file_and_closed_period_guard():
    """Debe rechazar archivos corruptos/no soportados y bloquear commits sobre meses cerrados."""
    db = _make_db()
    try:
        user = User(username="trader_locked", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        importer = BankStatementImporter()

        # Magic bytes inválidos declarados como PDF
        with pytest.raises((ValueError, HTTPException)):
            importer.parse_bytes(file_bytes=b"<script>evil</script>", filename="fake.pdf")

        # Período cerrado en FiscalPeriodSnapshot
        db.add(
            FiscalPeriodSnapshot(
                user_id=user.id,
                period="2026-11",
                initial_balance=0.0,
                calculated_final_balance=100.0,
                actual_final_balance=100.0,
                status="BALANCED",
            )
        )
        db.commit()

        with pytest.raises((ValueError, HTTPException)):
            importer.commit_rows(
                db=db,
                user_id=user.id,
                bank_name="BANESCO",
                rows=[
                    StatementCommitRow(
                        row_index=0,
                        date_vet="2026-11-10",
                        reference_number="998877",
                        concept="MOVIMIENTO TARDIO",
                        movement_type="CREDIT",
                        amount_ves=100.0,
                        payment_method="TRANSFERENCIA",
                        action="P2P_UNMATCHED",
                    )
                ],
            )
    finally:
        db.close()


def test_xlsx_statement_and_formula_sanitization():
    """Debe importar Excel .xlsx de cualquier banco y neutralizar inyección de fórmulas (=, +, -)."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["MERCANTIL BANCO UNIVERSAL"])
    ws.append(["Fecha Valor", "Documento", "Descripción", "Retiros", "Depósitos", "Saldo"])
    ws.append(["05/11/2026", "44556677", "placeholder", 0.0, 2500.0, 12500.0])
    ws["C3"].value = "=CMD|' /C calc'!A0"
    ws["C3"].data_type = "s"
    ws.append(["06/11/2026", "44556678", "TRANSFERENCIA OTRO BANCO", 500.0, 0.0, 12000.0])
    buf = io.BytesIO()
    wb.save(buf)

    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=buf.getvalue(), filename="mercantil_nov.xlsx")

    assert preview.bank_name == "MERCANTIL"
    assert preview.file_type == "XLSX"
    assert preview.total_rows == 2
    assert preview.balance_verified is True
    assert preview.rows[0].concept.startswith("'=")


def test_scanned_pdf_ai_fallback_with_balance_check():
    """Cuando un PDF no contiene texto seleccionable (escaneado), debe usar respaldo Gemini y verificar saldo."""
    from unittest.mock import MagicMock

    from src.integrations.ai_assistant import AIKeyPool

    # PDF válido sin texto (ej. escaneo de imagen)
    empty_text_pdf = _build_minimal_pdf([])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '[{"date": "2026-11-10", "reference": "778899", '
                                '"concept": "PAGO MOVIL RECIBIDO", "debit": 0.0, "credit": 1000.0, "balance": 6000.0}, '
                                '{"date": "2026-11-11", "reference": "778900", '
                                '"concept": "COMISION PAGO MOVIL", "debit": 3.0, "credit": 0.0, "balance": 5997.0}]'
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp

    importer = BankStatementImporter(
        key_pool=AIKeyPool(["AIzaFakeRealTestKey12345"]),
        http_client=mock_client,
    )
    preview = importer.parse_bytes(
        file_bytes=empty_text_pdf,
        filename="escaneado_bancamiga.pdf",
        bank_name="Bancamiga",
    )

    assert preview.bank_name == "BANCAMIGA"
    assert preview.extraction_method == "PDF_AI_FALLBACK"
    assert preview.total_rows == 2
    assert preview.balance_verified is True
    assert preview.bank_fee_count == 1


def test_api_statement_preview_and_commit_endpoints():
    """Verifica integración completa de los controladores /statements/preview y /statements/commit."""
    import io

    from fastapi import UploadFile

    from src.api.routes.accounting import (
        StatementCommitRequest,
        StatementCommitRowRequest,
        commit_bank_statement,
        preview_bank_statement,
    )

    db = _make_db()
    try:
        user = User(username="trader_api_stmt", password_hash="x", role="TRADER", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        csv_bytes = (
            b"Fecha,Referencia,Concepto,Cargos,Abonos,Saldo\n"
            b"08/11/2026,123456,APORTE CAPITAL PROPIO,0.00,5000.00,5000.00\n"
            b"09/11/2026,123457,COMISION MANTENIMIENTO,25.00,0.00,4975.00\n"
        )

        upload = UploadFile(file=io.BytesIO(csv_bytes), filename="bnc_movs.csv")
        prev_resp = preview_bank_statement(
            file=upload,
            db=db,
            current_user=user,
            bank_name="BNC",
        )
        assert prev_resp.bank_name == "BNC"
        assert prev_resp.total_rows == 2
        assert prev_resp.balance_verified is True

        commit_payload = StatementCommitRequest(
            bank_name=prev_resp.bank_name,
            rows=[
                StatementCommitRowRequest(
                    row_index=prev_resp.rows[0].row_index,
                    date_vet=prev_resp.rows[0].date_vet,
                    reference_number=prev_resp.rows[0].reference_number,
                    concept=prev_resp.rows[0].concept,
                    movement_type=prev_resp.rows[0].movement_type,
                    amount_ves=prev_resp.rows[0].amount_ves,
                    payment_method=prev_resp.rows[0].payment_method,
                    action="INTERNAL_TRANSFER",
                ),
                StatementCommitRowRequest(
                    row_index=prev_resp.rows[1].row_index,
                    date_vet=prev_resp.rows[1].date_vet,
                    reference_number=prev_resp.rows[1].reference_number,
                    concept=prev_resp.rows[1].concept,
                    movement_type=prev_resp.rows[1].movement_type,
                    amount_ves=prev_resp.rows[1].amount_ves,
                    payment_method=prev_resp.rows[1].payment_method,
                    action="BANK_FEE",
                ),
            ],
        )
        commit_resp = commit_bank_statement(payload=commit_payload, db=db, current_user=user)
        assert commit_resp.status == "SUCCESS"
        assert commit_resp.internal_transfers_recorded == 1
        assert commit_resp.bank_fees_recorded == 1
        assert commit_resp.journal_entries_created == 4
    finally:
        db.close()


def test_parse_bdv_middle_aligned_multiline_pagebreak_and_duplicate_print_bug():
    """Debe leer formato real BDV (Fecha en col 3, celdas centradas, salto de página y duplicado 21/05)."""
    page1: list[tuple[float, float, str]] = [
        (220, 755, "Estado de cuenta moneda nacional"),
        (30, 735, "Cuenta: 0102****3046"),
        (360, 735, "Periodo: 01/05/2026 - 31/10/2026"),
        (30, 715, "Saldo inicial: 47.091,66   Saldo final: 47.752,48"),
        # Cabecera real BDV: Referencia | Descripcion | Fecha | Mov | Debito | Credito | Saldo
        (24, 680, "Referencia"),
        (100, 680, "Descripcion"),
        (362, 680, "Fecha"),
        (422, 680, "Mov"),
        (454, 680, "Debito"),
        (505, 680, "Credito"),
        (558, 680, "Saldo"),
        # Fila SI
        (100, 660, "SALDO INICIAL"),
        (362, 660, "01/05/2026"),
        (422, 660, "SI"),
        (460, 660, "0,00"),
        (512, 660, "0,00"),
        (550, 660, "47.091,66"),
        # Mov 1: comision
        (24, 642, "9553100002641"),
        (100, 642, "COM BANCA MOVIL BDV"),
        (362, 642, "01/05/2026"),
        (422, 642, "ND"),
        (456, 642, "-8,00"),
        (512, 642, "0,00"),
        (550, 642, "47.083,66"),
        # Mov 2 + Mov 2 duplicado impreso por BDV el 21/05 con saldo identico (50.749,66)
        (24, 624, "0677299357250"),
        (100, 624, "OPERACION PAGOMOVIL BDV"),
        (362, 624, "21/05/2026"),
        (422, 624, "NC"),
        (460, 624, "0,00"),
        (502, 624, "3.666,00"),
        (550, 624, "50.749,66"),
        (24, 606, "0677299357250"),
        (100, 606, "OPERACION PAGOMOVIL BDV"),
        (362, 606, "21/05/2026"),
        (422, 606, "NC"),
        (460, 606, "0,00"),
        (502, 606, "3.666,00"),
        (550, 606, "50.749,66"),
        # Mov 3: Descripcion 2 lineas y Referencia/Fecha/Montos centrados verticalmente en medio
        (100, 588, "PAGOMOVIL TERCEROS BDV 015571046 AHISQUEL CHACON"),
        (24, 583, "0677204387399"),
        (362, 583, "29/09/2026"),
        (422, 583, "ND"),
        (448, 583, "-1.500,00"),
        (512, 583, "0,00"),
        (550, 583, "49.249,66"),
        (100, 578, "CANAL 54 0424***6427"),
        # Mov 4: Ultima fila de pagina 1 cuya continuacion salta a la pagina 2
        (24, 100, "0677231115921"),
        (100, 100, "PAGOMOVIL TERCEROS BDV 027293774 ENRIQUE RAMIREZ CANAL"),
        (362, 100, "10/10/2026"),
        (422, 100, "ND"),
        (448, 100, "-1.483,18"),
        (512, 100, "0,00"),
        (550, 100, "47.766,48"),
        (180, 45, "El Banco de Venezuela S.A Banco Universal certifica la informacion"),
        (520, 30, "Pagina: 1/2"),
    ]
    page2: list[tuple[float, float, str]] = [
        (220, 755, "Estado de cuenta moneda nacional"),
        (30, 735, "Cuenta: 0102****3046"),
        (30, 715, "Saldo inicial: 47.091,66   Saldo final: 47.752,48"),
        (24, 680, "Referencia"),
        (100, 680, "Descripcion"),
        (362, 680, "Fecha"),
        (422, 680, "Mov"),
        (454, 680, "Debito"),
        (505, 680, "Credito"),
        (558, 680, "Saldo"),
        # Continuacion huerfana de la fila 4 tras el salto de pagina
        (100, 662, "54 0424***9895"),
        # Mov 5: Comision siguiente
        (24, 642, "0210031115921"),
        (100, 642, "COBRO COMISION PAG MOVIL"),
        (362, 642, "10/10/2026"),
        (422, 642, "ND"),
        (456, 642, "-14,00"),
        (512, 642, "0,00"),
        (550, 642, "47.752,48"),
        (180, 45, "El Banco de Venezuela S.A Banco Universal certifica la informacion"),
        (520, 30, "Pagina: 3/2"),
    ]

    pdf_bytes = _build_positioned_pdf([page1, page2])
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="estado_cuenta_noviembre.pdf")

    assert preview.bank_name == "BANCO DE VENEZUELA"
    assert preview.total_rows == 5
    assert preview.balance_verified is True
    assert preview.balance_mismatch_count == 0
    assert preview.opening_balance == pytest.approx(47091.66, abs=0.02)
    assert preview.closing_balance == pytest.approx(47752.48, abs=0.02)

    # Validar union multilinea centrada y entre paginas sin contaminar filas vecinas
    assert "OPERACION PAGOMOVIL BDV" == preview.rows[1].concept
    assert "AHISQUEL CHACON" in preview.rows[2].concept
    assert "CANAL 54 0424***6427" in preview.rows[2].concept
    assert "ENRIQUE RAMIREZ CANAL" in preview.rows[3].concept
    assert "54 0424***9895" in preview.rows[3].concept
    assert preview.rows[4].suggested_action == "BANK_FEE"
    assert preview.rows[4].amount_ves == 14.00


def test_parse_universal_bank_column_permutations_and_two_dates():
    """Debe leer diseños tipo Provincial/Mercantil/Internacional: doble fecha, monto único + Tipo, cabecera 2 líneas."""
    page1: list[tuple[float, float, str]] = [
        (36, 755, "BBVA PROVINCIAL ESTADO DE CUENTA - ANO 2026"),
        # Cabecera en 2 renglones + doble columna de fecha + monto unico + columna Tipo
        (30, 710, "Fecha"),
        (30, 700, "Oper"),
        (90, 710, "Fecha"),
        (90, 700, "Valor"),
        (155, 705, "Concepto"),
        (345, 705, "Referencia"),
        (415, 705, "Tipo"),
        (465, 705, "Monto"),
        (540, 710, "Saldo"),
        (540, 700, "Disponible"),
        # Orden descendente con fechas textuales y formato internacional
        (30, 680, "16 NOV 2026"),
        (90, 680, "16 NOV 2026"),
        (155, 680, "PAGO MOVIL RECIBIDO CLIENTE"),
        (345, 680, "REF-9911"),
        (420, 680, "CR"),
        (460, 680, "1,250.50"),
        (535, 680, "6,250.50"),
        (30, 660, "15 NOV 2026"),
        (90, 660, "15 NOV 2026"),
        (155, 660, "CARGO COMISION INTERBANCARIA"),
        (345, 660, "REF-9910"),
        (420, 660, "DB"),
        (465, 660, "50.00"),
        (535, 660, "5,000.00"),
    ]

    pdf_bytes = _build_positioned_pdf([page1])
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="provincial_movs.pdf")

    assert preview.bank_name == "PROVINCIAL"
    assert preview.total_rows == 2
    assert preview.detected_order == "DESC"
    assert preview.balance_verified is True

    assert preview.rows[0].date_vet == "2026-11-16"
    assert preview.rows[0].movement_type == "CREDIT"
    assert preview.rows[0].amount_ves == 1250.50
    assert preview.rows[0].reference_number == "9911"

    assert preview.rows[1].date_vet == "2026-11-15"
    assert preview.rows[1].movement_type == "DEBIT"
    assert preview.rows[1].amount_ves == 50.00
    assert preview.rows[1].suggested_action == "BANK_FEE"


def test_parse_pdf_over_60_pages_not_truncated_and_chunked_ai_fallback():
    """Debe leer PDFs >60 páginas sin truncar y dividir PDFs escaneados largos en lotes para Gemini."""
    pages: list[list[tuple[float, float, str]]] = []
    running = 1000.00
    for i in range(65):
        day = (i % 28) + 1
        month = 5 + (i // 28)
        running = round(running + 10.00, 2)
        bal_str = f"{running:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        items: list[tuple[float, float, str]] = []
        if i == 0:
            items.append((36, 755, "BANCO MERCANTIL - CUENTA 0105****8899"))
        items.extend(
            [
                (30, 710, "Referencia"),
                (110, 710, "Fecha"),
                (185, 710, "Descripcion"),
                (440, 710, "Credito"),
                (530, 710, "Saldo"),
                (30, 685, f"8800{i:04d}"),
                (110, 685, f"{day:02d}/{month:02d}/2026"),
                (185, 685, f"ABONO CLIENTE PAGO {i + 1}"),
                (440, 685, "10,00"),
                (525, 685, bal_str),
            ]
        )
        pages.append(items)

    large_pdf = _build_positioned_pdf(pages)
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=large_pdf, filename="estado_65_paginas.pdf")

    assert preview.bank_name == "MERCANTIL"
    assert preview.total_rows == 65
    assert preview.balance_verified is True
    assert not any("primeras 60" in w.lower() for w in preview.warnings)

    # Scanned 6-page PDF without text -> Gemini batching (2 + 2 + 2 pages = 3 API calls para no truncar salidas densas)
    from unittest.mock import MagicMock

    from src.integrations.ai_assistant import AIKeyPool

    scanned_pages: list[list[tuple[float, float, str]]] = [[] for _ in range(6)]
    scanned_pdf = _build_positioned_pdf(scanned_pages)

    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '[{"date": "2026-11-01", "reference": "100001", '
                                '"concept": "ABONO LOTE 1", "debit": 0.0, "credit": 500.0, "balance": 1500.0}]'
                            )
                        }
                    ]
                }
            }
        ]
    }
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '[{"date": "2026-11-02", "reference": "100002", '
                                '"concept": "ABONO LOTE 2", "debit": 0.0, "credit": 250.0, "balance": 1750.0}]'
                            )
                        }
                    ]
                }
            }
        ]
    }
    resp3 = MagicMock()
    resp3.status_code = 200
    resp3.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '[{"date": "2026-11-03", "reference": "100003", '
                                '"concept": "ABONO LOTE 3", "debit": 0.0, "credit": 100.0, "balance": 1850.0}]'
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.side_effect = [resp1, resp2, resp3]

    ai_importer = BankStatementImporter(
        key_pool=AIKeyPool(["AIzaFakeRealTestKey12345"]),
        http_client=mock_client,
    )
    ai_preview = ai_importer.parse_bytes(
        file_bytes=scanned_pdf,
        filename="escaneado_6pag.pdf",
        bank_name="Banesco",
    )

    assert ai_preview.extraction_method == "PDF_AI_FALLBACK"
    assert ai_preview.total_rows == 3
    assert ai_preview.balance_verified is True
    assert mock_client.post.call_count == 3


def test_parse_banesco_split_panel_day_only_negative_balance_and_cheques_table():
    """Debe leer diseño real Banesco: 2 paneles lado a lado, mini-tabla CHEQUES, DIA solo dígitos y saldos negativos."""
    page1: list[tuple[float, float, str]] = [
        (36, 755, "Estado de cuenta"),
        # Panel izquierdo (resumen paralelo en las mismas Y que los movimientos derechos; espaciado Courier 8pt)
        (25, 650, "RESUMEN DE MOVIMIENTOS"),
        (25, 638, "No. de Cuenta: 0134086698691024513"),
        (200, 638, "Periodo: 05-2025"),
        (30, 620, "Otros Debitos"),
        (140, 620, "172"),
        (210, 620, "251.883,56"),
        (25, 595, "RESUMEN DE SALDOS"),
        (30, 575, "Inicial"),
        (210, 575, "12.115,76"),
        (30, 560, "Final"),
        (210, 560, "-1.735,37"),
        # Panel derecho: sub-tabla CHEQUES arriba + DETALLE DE MOVIMIENTOS abajo
        (305, 710, "CHEQUES"),
        (312, 695, "CHEQUE"),
        (365, 695, "DIA"),
        (420, 695, "MONTO"),
        (485, 695, "CHEQUE"),
        (535, 695, "DIA"),
        (575, 695, "MONTO"),
        (305, 678, "DETALLE DE MOVIMIENTOS"),
        (305, 658, "DIA"),
        (332, 658, "REF."),
        (392, 658, "CONCEPTO"),
        (485, 658, "CARGOS"),
        (532, 658, "ABONOS"),
        (578, 658, "SALDOS"),
        # Saldo mes anterior + movimientos con solo DIA (02, 05) y saldo negativo al final
        (392, 642, "SALDO MES ANTERIOR"),
        (572, 642, "12.115,76"),
        (305, 625, "02"),
        (332, 625, "12114000875"),
        (392, 625, "COMPRA POS CTA"),
        (485, 625, "1.677,45"),
        (572, 625, "10.438,31"),
        (305, 610, "02"),
        (332, 610, "02681930542"),
        (392, 610, "Banesco Pago Movil"),
        (525, 610, "2.178,00"),
        (572, 610, "12.616,31"),
        # Debito grande que lleva la cuenta a saldo negativo (-1.735,24) + Comision con coma ("Com,")
        (305, 575, "05"),
        (332, 575, "51244171531"),
        (392, 575, "Banesco Pago Movil"),
        (485, 575, "14.351,55"),
        (572, 575, "-1.735,24"),
        (305, 560, "05"),
        (332, 560, "51244486200"),
        (392, 560, "Com, Pago Movil"),
        (485, 560, "0,13"),
        (572, 560, "-1.735,37"),
    ]

    pdf_bytes = _build_positioned_pdf([page1])
    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=pdf_bytes, filename="edo_cuenta.pdf")

    assert preview.bank_name == "BANESCO"
    assert preview.total_rows == 4
    assert preview.detected_order == "ASC"
    assert preview.balance_verified is True
    assert preview.balance_mismatch_count == 0
    assert preview.opening_balance == pytest.approx(12115.76, abs=0.02)
    assert preview.closing_balance == pytest.approx(-1735.37, abs=0.02)

    assert preview.rows[0].date_vet == "2025-05-02"
    assert preview.rows[0].movement_type == "DEBIT"
    assert preview.rows[0].amount_ves == 1677.45

    assert preview.rows[1].movement_type == "CREDIT"
    assert preview.rows[1].amount_ves == 2178.00

    assert preview.rows[2].date_vet == "2025-05-05"
    assert preview.rows[2].balance_ves == pytest.approx(-1735.24, abs=0.02)

    assert preview.rows[3].suggested_action == "BANK_FEE"
    assert preview.rows[3].amount_ves == 0.13
    assert preview.rows[3].balance_ves == pytest.approx(-1735.37, abs=0.02)


def test_parse_bnc_debe_haber_and_mercantil_egresos_ingresos_sin_saldo():
    """Debe leer BNC (Debe/Haber, DESC, logo imagen) y Mercantil en Línea (Egresos/Ingresos sin Saldo + SALDO FINAL)."""
    # 1. BNC (Debe | Haber | Saldo)
    bnc_page: list[tuple[float, float, str]] = [
        (220, 740, "25 ULTIMOS MOVIMIENTOS HASTA EL: 05 de octubre de 2024"),
        (30, 710, "CUENTA CORRIENTE ***2700"),
        (30, 680, "Fecha"),
        (110, 680, "Descripcion"),
        (330, 680, "Referencia"),
        (420, 680, "Debe"),
        (485, 680, "Haber"),
        (555, 680, "Saldo"),
        (30, 658, "05/10/2024"),
        (110, 658, "Comision Pago Movil - ref: 349947745"),
        (330, 658, "349947745"),
        (415, 658, "-0,13"),
        (485, 658, "0,00"),
        (555, 658, "0,98"),
        (30, 640, "05/10/2024"),
        (110, 640, "Cargo Pago Movil BNC - ref: 349947745"),
        (330, 640, "349947745"),
        (415, 640, "-5,00"),
        (485, 640, "0,00"),
        (555, 640, "1,11"),
        (30, 622, "03/10/2024"),
        (110, 622, "Abono Pago Movil BNC - ref: 204704004"),
        (330, 622, "204704004"),
        (420, 622, "0,00"),
        (480, 622, "+140,00"),
        (555, 622, "6,11"),
    ]
    importer = BankStatementImporter()
    bnc_prev = importer.parse_bytes(
        file_bytes=_build_positioned_pdf([bnc_page]),
        filename="ultimos_movimientos.pdf",
    )
    assert bnc_prev.bank_name == "BNC"
    assert bnc_prev.total_rows == 3
    assert bnc_prev.detected_order == "DESC"
    assert bnc_prev.balance_verified is True
    assert bnc_prev.rows[0].suggested_action == "BANK_FEE"
    assert bnc_prev.rows[2].movement_type == "CREDIT"
    assert bnc_prev.rows[2].amount_ves == 140.00

    # 2. Mercantil en Línea (Egresos | Ingresos sin columna Saldo + fila SALDO FINAL al inicio)
    mercantil_page: list[tuple[float, float, str]] = [
        (30, 755, "Mercantil en Linea"),
        (30, 730, "Cuenta Corriente - 001636029302 - Bs"),
        (30, 700, "Transacciones del mes de Febrero de 2024."),
        (30, 675, "Fecha"),
        (95, 675, "Numero de"),
        (95, 667, "Referencia"),
        (210, 671, "Descripcion"),
        (450, 671, "Egresos"),
        (535, 671, "Ingresos"),
        # Fila trampa SALDO FINAL dentro de la tabla -> no debe contarse como ingreso!
        (30, 650, "20/02/2024"),
        (210, 650, "SALDO FINAL"),
        (535, 650, "482,03"),
        (30, 634, "20/02/2024"),
        (95, 634, "000082553898152"),
        (210, 634, "ND - PAGO MOVIL COMERCIAL INTERBANCARIO"),
        (450, 634, "-102,00"),
        (30, 618, "19/02/2024"),
        (95, 618, "000022200000182"),
        (210, 618, "NC - PAGO DE NOMINA"),
        (535, 618, "814,00"),
        (30, 602, "15/02/2024"),
        (95, 602, "000044301478164"),
        (210, 602, "ND - MENSUALIDAD MENSAJERIA DE TEXTO"),
        (450, 602, "-0,50"),
    ]
    merc_prev = importer.parse_bytes(
        file_bytes=_build_positioned_pdf([mercantil_page]),
        filename="transacciones_febrero.pdf",
    )
    assert merc_prev.bank_name == "MERCANTIL"
    assert merc_prev.total_rows == 3
    assert merc_prev.detected_order == "DESC"
    assert merc_prev.rows[0].movement_type == "DEBIT"
    assert merc_prev.rows[0].amount_ves == 102.00
    assert merc_prev.rows[1].movement_type == "CREDIT"
    assert merc_prev.rows[1].amount_ves == 814.00
    assert merc_prev.rows[2].suggested_action == "BANK_FEE"
    assert merc_prev.rows[2].amount_ves == 0.50


def test_comis_abbreviation_and_concept_aware_dedup():
    """Debe detectar abreviatura COMIS como comisión deducible sin falsos positivos y exigir concepto igual al depurar impresiones repetidas."""
    csv_content = (
        b"Banco de Venezuela\n"
        b"Fecha;Referencia;Descripcion;Debito;Credito;Saldo\n"
        b"23/08/2026;9604523082026;COMIS CLAVE DE PAGO VIA S;0,52;0,00;37867,67\n"
        b"23/08/2026;9604523082026;COMIS CLAVE DE PAGO VIA S;0,52;0,00;37867,67\n"
        b"23/08/2026;999888777;TRANSFERENCIA FIDEICOMISO PRUEBA;100,00;0,00;37767,67\n"
        b"23/08/2026;999888777;AJUSTE OPERATIVO DISTINTO;100,00;0,00;37767,67"
    )

    importer = BankStatementImporter()
    preview = importer.parse_bytes(file_bytes=csv_content, filename="bdv_comis.csv")

    assert preview.total_rows == 3
    assert preview.rows[0].suggested_action == "BANK_FEE"
    assert preview.rows[0].bank_fee_ves == 0.52
    # "FIDEICOMISO" no debe confundirse con "COMIS"
    assert preview.rows[1].suggested_action == "P2P_UNMATCHED"
    # Misma fecha/ref/monto/saldo pero distinto concepto NO se descarta como duplicado de impresión
    assert preview.rows[2].concept == "AJUSTE OPERATIVO DISTINTO"


def _render_positioned_statement_image(
    rows_positioned: list[list[tuple[int, str]]],
    *,
    img_format: str = "PNG",
    size: tuple[int, int] = (1200, 420),
) -> bytes:
    """Genera una imagen bancaria nítida (PNG/JPEG/PDF-raster) sin capa de texto para probar OCR real."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=20)
    for row_idx, cols in enumerate(rows_positioned):
        y = 28 + row_idx * 46
        for x, text in cols:
            draw.text((x, y), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format=img_format)
    return buf.getvalue()


def test_image_upload_fail_closed_and_real_local_rapidocr():
    """Debe validar magic bytes de imágenes (Fail-Closed) y extraer movimientos offline desde PNG con RapidOCR."""
    importer = BankStatementImporter()

    # Archivo .png con bytes falsos -> Fail-Closed
    with pytest.raises(ValueError, match="imagen|PNG|firma|inválida"):
        importer.parse_bytes(file_bytes=b"NOT_A_REAL_PNG_FILE", filename="captura_falsa.png")

    # Imagen PNG real generada en memoria simulando estado Mercantil/BNC con saldo verificable
    png_bytes = _render_positioned_statement_image(
        [
            [(30, "BANCO NACIONAL DE CREDITO")],
            [(30, "Fecha"), (200, "Referencia"), (390, "Descripcion"), (740, "Debe"), (890, "Haber"), (1040, "Saldo")],
            [(30, "05/10/2024"), (200, "349947745"), (390, "ABONO PAGO MOVIL"), (740, "0,00"), (890, "140,00"), (1040, "142,58")],
            [(30, "05/10/2024"), (200, "349947746"), (390, "COMISION PAGO MOVIL"), (740, "5,00"), (890, "0,00"), (1040, "137,58")],
            [(30, "06/10/2024"), (200, "349947747"), (390, "COMPRA POS"), (740, "60,00"), (890, "0,00"), (1040, "77,58")],
        ],
        img_format="PNG",
    )
    preview = importer.parse_bytes(file_bytes=png_bytes, filename="captura_bnc.png")

    assert preview.bank_name == "BNC"
    assert preview.file_type == "IMAGE"
    assert preview.extraction_method.startswith("IMAGE_OCR_")
    assert preview.total_rows == 3
    assert preview.balance_verified is True
    assert preview.balance_mismatch_count == 0
    assert preview.bank_fee_count == 1
    assert preview.rows[0].movement_type == "CREDIT"
    assert preview.rows[0].amount_ves == 140.00
    assert preview.rows[2].balance_ves == pytest.approx(77.58, abs=0.02)


def test_dual_ocr_arbitration_and_row_level_consensus():
    """En caso de dudas (descuadre de saldo), el árbitro Dual-OCR evalúa Tesseract y concilia fila a fila."""

    def _mk_words(rows_spec: list[tuple[float, list[tuple[float, float, str]]]]) -> tuple[list[dict[str, object]], float]:
        words: list[dict[str, object]] = []
        for y, cols in rows_spec:
            for x0, x1, txt in cols:
                words.append({"text": txt, "x0": x0, "x1": x1, "top": y, "bottom": y + 10.0})
        return words, 0.82

    header = (
        40.0,
        [
            (30.0, 70.0, "Fecha"),
            (110.0, 175.0, "Referencia"),
            (210.0, 290.0, "Concepto"),
            (390.0, 440.0, "Cargos"),
            (465.0, 515.0, "Abonos"),
            (540.0, 590.0, "Saldo"),
        ],
    )

    # Caso A: RapidOCR lee un saldo erróneo (999,00) generando 1 descuadre; Tesseract lee exacto (850,00) y gana el arbitraje
    rapid_bad = _mk_words(
        [
            (15.0, [(30.0, 150.0, "Banesco")]),
            header,
            (60.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "1001"), (210.0, 320.0, "ABONO PAGO MOVIL"), (465.0, 515.0, "500,00"), (540.0, 595.0, "999,00")]),
            (80.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "1002"), (210.0, 320.0, "COMISION PAGO MOVIL"), (390.0, 440.0, "10,00"), (540.0, 595.0, "840,00")]),
        ]
    )
    tess_clean = _mk_words(
        [
            (15.0, [(30.0, 150.0, "Banesco")]),
            header,
            (60.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "1001"), (210.0, 320.0, "ABONO PAGO MOVIL"), (465.0, 515.0, "500,00"), (540.0, 595.0, "850,00")]),
            (80.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "1002"), (210.0, 320.0, "COMISION PAGO MOVIL"), (390.0, 440.0, "10,00"), (540.0, 595.0, "840,00")]),
        ]
    )

    dummy_png = _render_positioned_statement_image([[(10, "dummy")]], size=(120, 60))
    importer_a = BankStatementImporter(
        ocr_engines={
            "rapidocr": lambda _img: rapid_bad,
            "tesseract": lambda _img: tess_clean,
        }
    )
    res_a = importer_a.parse_bytes(file_bytes=dummy_png, filename="banesco_duda.png")
    assert res_a.extraction_method == "IMAGE_OCR_TESSERACT"
    assert res_a.balance_verified is True
    assert res_a.balance_mismatch_count == 0
    assert res_a.rows[0].balance_ves == 850.00
    assert any("Tesseract" in w and "RapidOCR" in w for w in res_a.warnings)

    # Caso B: Consenso fila-a-fila: RapidOCR captura 3 filas con 1 error puntual en fila 1; Tesseract captura 2 filas pero bien fila 1 -> Consenso repara y cuadra 3/3!
    rapid_3_with_1_err = _mk_words(
        [
            (15.0, [(30.0, 150.0, "Banesco")]),
            header,
            (60.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "2001"), (210.0, 320.0, "ABONO UNO"), (465.0, 515.0, "500,00"), (540.0, 595.0, "500,00")]),
            (80.0, [(30.0, 85.0, "03/05/2025"), (110.0, 165.0, "2002"), (210.0, 320.0, "CARGO DOS"), (390.0, 440.0, "100,00"), (540.0, 595.0, "999,00")]),
            (100.0, [(30.0, 85.0, "04/05/2025"), (110.0, 165.0, "2003"), (210.0, 320.0, "ABONO TRES"), (465.0, 515.0, "50,00"), (540.0, 595.0, "450,00")]),
        ]
    )
    tess_2_repaired = _mk_words(
        [
            (15.0, [(30.0, 150.0, "Banesco")]),
            header,
            (60.0, [(30.0, 85.0, "02/05/2025"), (110.0, 165.0, "2001"), (210.0, 320.0, "ABONO UNO"), (465.0, 515.0, "500,00"), (540.0, 595.0, "500,00")]),
            (80.0, [(30.0, 85.0, "03/05/2025"), (110.0, 165.0, "2002"), (210.0, 320.0, "CARGO DOS"), (390.0, 440.0, "100,00"), (540.0, 595.0, "400,00")]),
        ]
    )
    importer_b = BankStatementImporter(
        ocr_engines={
            "rapidocr": lambda _img: rapid_3_with_1_err,
            "tesseract": lambda _img: tess_2_repaired,
        }
    )
    res_b = importer_b.parse_bytes(file_bytes=dummy_png, filename="banesco_consenso.png")
    assert res_b.total_rows == 3
    assert res_b.balance_verified is True
    assert res_b.balance_mismatch_count == 0
    assert res_b.rows[1].balance_ves == 400.00
    assert res_b.extraction_method == "IMAGE_OCR_CONSENSUS"


def test_scanned_image_pdf_uses_local_ocr_without_gemini_key():
    """Un PDF escaneado (solo imagen raster sin capa de texto) debe leerse localmente y gratis con RapidOCR sin clave Gemini."""
    scanned_pdf = _render_positioned_statement_image(
        [
            [(30, "BANESCO ESTADO DE CUENTA")],
            [(30, "Fecha"), (200, "Referencia"), (390, "Concepto"), (740, "Cargos"), (890, "Abonos"), (1040, "Saldo")],
            [(30, "05/05/2025"), (200, "512441715"), (390, "PAGO MOVIL RECIBIDO"), (740, "0,00"), (890, "2.000,00"), (1040, "12.000,00")],
            [(30, "05/05/2025"), (200, "512444862"), (390, "COMISION PAGO MOVIL"), (740, "6,00"), (890, "0,00"), (1040, "11.994,00")],
        ],
        img_format="PDF",
    )

    importer = BankStatementImporter()  # Sin clave Gemini
    preview = importer.parse_bytes(file_bytes=scanned_pdf, filename="escaneado_local.pdf")

    assert preview.bank_name == "BANESCO"
    assert preview.file_type == "PDF"
    assert preview.extraction_method.startswith("PDF_OCR_")
    assert preview.total_rows == 2
    assert preview.balance_verified is True
    assert preview.bank_fee_count == 1
    assert preview.rows[1].balance_ves == pytest.approx(11994.00, abs=0.02)


def test_oversized_pixel_bomb_image_rejected_fail_closed():
    """Una imagen que declare dimensiones superiores al límite anti-DoS debe rechazarse Fail-Closed sin decodificar píxeles."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("1", (8000, 8000), 1).save(buf, format="PNG")
    importer = BankStatementImporter()
    with pytest.raises(ValueError, match="Dimensiones de imagen fuera del límite de seguridad"):
        importer.parse_bytes(file_bytes=buf.getvalue(), filename="bomba.png")
