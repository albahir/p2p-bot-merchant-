"""Pruebas TDD de seguridad anti-backdoor / anti-DoS sin fricción para carga de archivos."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image, PngImagePlugin
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.data.models import User
from src.integrations.statement_importer import BankStatementImporter
from src.security.file_guards import (
    MAX_OCR_IMAGE_PIXELS,
    MAX_STATEMENT_UPLOAD_BYTES,
    MAX_VOUCHER_UPLOAD_BYTES,
    build_clean_ocr_env,
    compute_safe_pdf_render_scale,
    read_upload_bounded,
    sanitize_and_load_image,
    validate_pdf_safety,
    validate_xls_safety,
    validate_xlsx_zip_safety,
)


def _make_clean_pdf(with_harmless_uri: bool = False, page_size: tuple[float, float] = (612, 792)) -> bytes:
    """Genera un PDF mínimo sintácticamente válido con opcional acción benigna de navegación."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=page_size[0], height=page_size[1])
    if with_harmless_uri:
        annot = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): ArrayObject(),
                NameObject("/A"): DictionaryObject(
                    {
                        NameObject("/S"): NameObject("/URI"),
                        NameObject("/URI"): TextStringObject("https://www.banesco.com"),
                    }
                ),
            }
        )
        page[NameObject("/Annots")] = ArrayObject([annot])
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {
                NameObject("/S"): NameObject("/GoTo"),
                NameObject("/D"): ArrayObject([page.indirect_reference, NameObject("/Fit")]),
            }
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_security_blocks_malicious_actions_and_embedded_files_without_false_positives():
    """Rechaza PDFs con /JavaScript, /Launch o /EmbeddedFiles pero permite links /URI y zoom /OpenAction."""
    # 1. PDF con enlace bancario legítimo (/URI + /OpenAction GoTo) debe pasar sin fricción
    clean_pdf = _make_clean_pdf(with_harmless_uri=True)
    validate_pdf_safety(clean_pdf)

    # 2. PDF con /JavaScript embebido en /OpenAction
    writer_js = PdfWriter()
    writer_js.add_blank_page(width=612, height=792)
    writer_js._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {
            NameObject("/S"): NameObject("/JavaScript"),
            NameObject("/JS"): TextStringObject("app.alert('backdoor');"),
        }
    )
    buf_js = io.BytesIO()
    writer_js.write(buf_js)
    with pytest.raises(ValueError, match="PDF rechazado"):
        validate_pdf_safety(buf_js.getvalue())

    # 3. PDF con acción /Launch (intento de lanzar ejecutable del SO)
    writer_launch = PdfWriter()
    writer_launch.add_blank_page(width=612, height=792)
    writer_launch._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {
            NameObject("/S"): NameObject("/Launch"),
            NameObject("/F"): TextStringObject("cmd.exe"),
        }
    )
    buf_launch = io.BytesIO()
    writer_launch.write(buf_launch)
    with pytest.raises(ValueError, match="PDF rechazado"):
        validate_pdf_safety(buf_launch.getvalue())

    # 4. PDF con archivo adjunto oculto (/EmbeddedFiles)
    writer_emb = PdfWriter()
    writer_emb.add_blank_page(width=612, height=792)
    writer_emb.add_attachment("payload.bin", b"MZ\x90\x00evil")
    buf_emb = io.BytesIO()
    writer_emb.write(buf_emb)
    with pytest.raises(ValueError, match="PDF rechazado"):
        validate_pdf_safety(buf_emb.getvalue())


def test_pdf_adaptive_render_scale_prevents_gigapixel_oom_without_blocking_large_scans():
    """Un PDF con MediaBox gigante adapta su escala de rasterizado automáticamente en lugar de colapsar la RAM."""
    normal_scale = compute_safe_pdf_render_scale(612.0, 792.0)
    assert normal_scale == pytest.approx(2.2, abs=0.01)

    huge_scale = compute_safe_pdf_render_scale(15000.0, 15000.0)
    assert huge_scale is not None
    assert 0.1 < huge_scale < 0.35
    assert (15000.0 * huge_scale) * (15000.0 * huge_scale) <= 13_000_000.0

    # Página corrupta o absurda > 200,000 pt retorna None (omitida fail-closed sin explotar)
    assert compute_safe_pdf_render_scale(0.0, 500.0) is None
    assert compute_safe_pdf_render_scale(500_000.0, 500_000.0) is None


def test_xlsx_security_blocks_macros_xxe_and_zip_bomb():
    """Detecta macros VBA, payloads XXE XML y bombas ZIP en archivos .xlsx."""
    # 1. Macros VBA (vbaProject.bin)
    buf_macro = io.BytesIO()
    with zipfile.ZipFile(buf_macro, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("xl/workbook.xml", "<workbook/>")
        zf.writestr("xl/vbaProject.bin", b"\x00\x01macro")
    with pytest.raises(ValueError, match="macros|activos"):
        validate_xlsx_zip_safety(buf_macro.getvalue())

    # 2. Payload XXE <!DOCTYPE / <!ENTITY dentro de XML OOXML
    buf_xxe = io.BytesIO()
    with zipfile.ZipFile(buf_xxe, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><sst/>',
        )
    with pytest.raises(ValueError, match="XML|XXE|entidades"):
        validate_xlsx_zip_safety(buf_xxe.getvalue())

    # 3. ZIP-bomb (>120x compresión sobre entrada >1 MB)
    buf_bomb = io.BytesIO()
    with zipfile.ZipFile(buf_bomb, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("xl/worksheets/sheet1.xml", b"A" * (6 * 1024 * 1024))
    with pytest.raises(ValueError, match="compresión|ZIP"):
        validate_xlsx_zip_safety(buf_bomb.getvalue())


def test_xls_allows_venezuelan_html_table_exports_but_blocks_executables_and_xss():
    """No rompe exports .xls tipo tabla HTML bancaria, pero bloquea ejecutables MZ/ELF y <script>."""
    # HTML tabla legítima exportada como .xls por banca venezolana
    valid_html_xls = (
        b"<html><body><table><tr><th>Fecha</th><th>Referencia</th><th>Concepto</th>"
        b"<th>Debito</th><th>Credito</th><th>Saldo</th></tr>"
        b"<tr><td>02/05/2025</td><td>991122</td><td>PAGO MOVIL</td><td>0,00</td><td>500,00</td><td>500,00</td></tr>"
        b"</table></body></html>"
    )
    assert validate_xls_safety(valid_html_xls) == "HTML"

    # Ejecutable PE Windows camuflado como .xls
    with pytest.raises(ValueError, match="ejecutable|inválido"):
        validate_xls_safety(b"MZ\x90\x00\x03\x00\x00\x00This program cannot be run in DOS mode")

    # HTML .xls con etiqueta <script>
    with pytest.raises(ValueError, match="script|malicioso"):
        validate_xls_safety(b"<html><body><script>fetch('http://evil')</script><table></table></body></html>")


def test_image_guards_allow_long_mobile_scroll_captures_strip_metadata_and_stop_pixel_bombs():
    """Permite capturas móviles largas sin fastidiar, limpia metadatos EXIF/PNG y frena bombas de megapíxeles."""
    # 1. Captura larga móvil realista (1080 x 12500 px = 13.5 MP < 60 MP) debe pasar sin fricción
    buf_scroll = io.BytesIO()
    img_scroll = Image.new("RGB", (1080, 12500), "white")
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "payload_oculto_exif_xmp")
    img_scroll.save(buf_scroll, format="PNG", pnginfo=info)

    clean_img = sanitize_and_load_image(buf_scroll.getvalue())
    assert clean_img.size == (1080, 12500)
    assert clean_img.mode == "RGB"
    # Pixel-wash: cualquier chunk de metadatos previo fue descartado
    assert "Comment" not in clean_img.info

    # 2. Bomba de descompresión (8000 x 8000 = 64 MP > MAX_OCR_IMAGE_PIXELS=60 MP)
    assert MAX_OCR_IMAGE_PIXELS == 60_000_000
    buf_bomb = io.BytesIO()
    Image.new("1", (8000, 8000), 1).save(buf_bomb, format="PNG")
    with pytest.raises(ValueError, match="límite de seguridad"):
        sanitize_and_load_image(buf_bomb.getvalue())


def test_clean_ocr_subprocess_env_strips_sensitive_secrets(monkeypatch: pytest.MonkeyPatch):
    """El entorno heredado por subprocesos OCR nunca debe contener credenciales ni claves de la API."""
    monkeypatch.setenv("BINANCE_API_SECRET", "super_secret_binance")
    monkeypatch.setenv("JWT_SECRET_KEY", "super_secret_jwt")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/db")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("AI_API_KEYS", "AIzaSecret")

    clean = build_clean_ocr_env()
    assert "BINANCE_API_SECRET" not in clean
    assert "JWT_SECRET_KEY" not in clean
    assert "DATABASE_URL" not in clean
    assert "TELEGRAM_BOT_TOKEN" not in clean
    assert "AI_API_KEYS" not in clean
    assert "PATH" in clean


def test_api_upload_endpoints_enforce_size_and_threat_guards_fail_closed():
    """Los endpoints HTTP /vouchers/upload, /orders/upload y /statements/preview imponen cotas y validan contenido."""
    from src.api.routes.accounting import preview_bank_statement, upload_voucher
    from src.api.routes.orders import upload_orders_file

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        trader = User(username="sec_trader", password_hash="x", role="TRADER", is_active=True)
        db.add(trader)
        db.commit()
        db.refresh(trader)

        # 1. Helper bounded reader devuelve 413 al superar cota
        big_upload = UploadFile(filename="gigante.pdf", file=io.BytesIO(b"%PDF-" + b"0" * 2048))
        with pytest.raises(HTTPException) as exc_413:
            read_upload_bounded(big_upload, max_bytes=1024)
        assert exc_413.value.status_code == 413

        # 2. /vouchers/upload rechaza SVG/HTML XSS disfrazado de JPEG con HTTP 400
        xss_voucher = UploadFile(
            filename="recibo.jpg",
            file=io.BytesIO(b"<svg onload=alert(1)></svg>"),
        )
        with pytest.raises(HTTPException) as exc_voucher:
            upload_voucher(file=xss_voucher, db=db, current_user=trader)
        assert exc_voucher.value.status_code == 400

        # 3. /vouchers/upload acepta PNG válido tras Pixel-Wash
        valid_png_buf = io.BytesIO()
        Image.new("RGB", (120, 80), "white").save(valid_png_buf, format="PNG")
        valid_voucher = UploadFile(filename="recibo.png", file=io.BytesIO(valid_png_buf.getvalue()))
        mock_extraction = MagicMock(
            is_valid=True,
            bank_name="BANESCO",
            reference_number="12345678",
            amount_ves=500.0,
            bank_fee_ves=0.0,
            movement_type="CREDIT",
            date_time=None,
            sender_cedula=None,
            sender_name=None,
            destination_bank=None,
            sender_phone=None,
            concept="PAGO MOVIL",
            payment_method="PAGO_MOVIL",
        )
        with patch("src.integrations.receipt_ocr.BankReceiptOCR.extract_from_image", return_value=mock_extraction):
            res_v = upload_voucher(file=valid_voucher, db=db, current_user=trader)
        assert res_v["bank_name"] == "BANESCO"

        # 4. /orders/upload rechaza archivo .xlsx con macros VBA
        macro_xlsx = io.BytesIO()
        with zipfile.ZipFile(macro_xlsx, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("xl/vbaProject.bin", b"macro")
        bad_orders = UploadFile(filename="ordenes.xlsx", file=io.BytesIO(macro_xlsx.getvalue()))
        with pytest.raises(HTTPException) as exc_orders:
            upload_orders_file(file=bad_orders, db=db, current_user=trader)
        assert exc_orders.value.status_code == 400

        # 5. /statements/preview rechaza PDF con /JavaScript embebido sin bloquear archivos limpios
        writer_js = PdfWriter()
        writer_js.add_blank_page(width=612, height=792)
        writer_js._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("1+1")}
        )
        bad_pdf_buf = io.BytesIO()
        writer_js.write(bad_pdf_buf)
        bad_stmt = UploadFile(filename="extracto_malicioso.pdf", file=io.BytesIO(bad_pdf_buf.getvalue()))
        with pytest.raises(HTTPException) as exc_stmt:
            preview_bank_statement(file=bad_stmt, db=db, current_user=trader)
        assert exc_stmt.value.status_code == 400

        assert MAX_STATEMENT_UPLOAD_BYTES >= 25 * 1024 * 1024
        assert MAX_VOUCHER_UPLOAD_BYTES >= 15 * 1024 * 1024

        # 6. Importador acepta HTML-table .xls de banca venezolana de forma transparente
        html_xls = (
            b"<html><body><table>"
            b"<tr><td>Fecha</td><td>Referencia</td><td>Concepto</td><td>Debito</td><td>Credito</td><td>Saldo</td></tr>"
            b"<tr><td>05/05/2025</td><td>77889900</td><td>PAGO MOVIL RECIBIDO</td><td>0,00</td><td>1500,00</td><td>1500,00</td></tr>"
            b"</table></body></html>"
        )
        preview_xls = BankStatementImporter().parse_bytes(html_xls, "provincial.xls")
        assert preview_xls.total_rows == 1
        assert preview_xls.rows[0].amount_ves == 1500.00
    finally:
        db.close()
