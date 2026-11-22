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


def _build_minimal_pdf(lines: list[str]) -> bytes:
    """Genera un PDF vectorial válido en memoria con posicionamiento X/Y para pruebas deterministas."""
    stream_cmds = ["BT", "/F1 9 Tf"]
    y = 750
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_cmds.append(f"1 0 0 1 36 {y} Tm ({safe}) Tj")
        y -= 16
    stream_cmds.append("ET")
    stream_bytes = "\n".join(stream_cmds).encode("latin-1")

    objs: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream\nendobj\n"
        ),
    ]

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
