"""Guardias de seguridad estructural, anti-backdoor y anti-DoS para carga de archivos.

Validan archivos PDF, Excel (.xlsx/.xls), CSV e imágenes (.png/.jpg/.webp) sin generar
falsos positivos sobre extractos reales ni fricción para usuarios legítimos.
"""

from __future__ import annotations

import io
import math
import os
import zipfile
from html.parser import HTMLParser
from typing import Any, Literal

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, PdfObject

MAX_STATEMENT_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB (extractos largos / escaneados de alta calidad)
MAX_VOUCHER_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB por comprobante individual
MAX_ORDERS_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB por histórico Excel/CSV de órdenes

MAX_OCR_IMAGE_LONG_EDGE = 32_000  # Soporta capturas largas móviles con desplazamiento (scroll)
MAX_OCR_IMAGE_PIXELS = 60_000_000  # 60 MP máx. en memoria antes de decodificar (~180 MB RGB máx.)

MAX_PDF_SCAN_OBJECTS = 30_000
MAX_PDF_SCAN_DEPTH = 32
MAX_PDF_PAGE_POINT_DIM = 200_000.0
MAX_PDF_RENDER_PIXELS = 12_000_000.0

MAX_XLSX_ENTRIES = 500
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 120.0
MAX_XLSX_XML_CHECK_BYTES = 10 * 1024 * 1024

_PDF_DANGEROUS_KEYS = frozenset(
    {
        "/JS",
        "/JavaScript",
        "/Launch",
        "/RichMedia",
        "/EmbeddedFiles",
        "/EmbeddedFile",
        "/SubmitForm",
        "/ImportData",
        "/GoToR",
        "/GoToE",
        "/Sound",
        "/Movie",
        "/EF",
    }
)
_PDF_DANGEROUS_ACTIONS = frozenset(
    {
        "/JavaScript",
        "/JS",
        "/Launch",
        "/SubmitForm",
        "/ImportData",
        "/GoToR",
        "/GoToE",
        "/RichMedia",
        "/Sound",
        "/Movie",
    }
)
_EXEC_MAGIC_PREFIXES: tuple[bytes, ...] = (
    b"MZ",  # PE / Windows EXE / DLL
    b"\x7fELF",  # Linux ELF
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit
    b"\xcf\xfa\xed\xfe",  # Mach-O LE 64-bit
    b"\xca\xfe\xba\xbe",  # Mach-O Universal / Java class
    b"#!",  # Script shebang
)
_XLSX_DANGEROUS_EXTS: tuple[str, ...] = (
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".hta",
    ".scr",
    ".msi",
    ".lnk",
    ".bin",
)
_CLEAN_ENV_ALLOWLIST = (
    "PATH",
    "SYSTEMROOT",
    "COMSPEC",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "LANG",
    "LC_ALL",
    "TESSDATA_PREFIX",
    "OMP_THREAD_LIMIT",
)


def _format_max_mb_error(max_bytes: int) -> str:
    max_mb = max(1, max_bytes // (1024 * 1024))
    return f"El archivo supera el límite máximo permitido de {max_mb} MB."


def read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Lee un UploadFile por bloques acotados (hasta max_bytes + 1) aplicando límite Fail-Closed."""
    content = file.file.read(max_bytes + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo subido está vacío.",
        )
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=_format_max_mb_error(max_bytes),
        )
    return content


def assert_not_executable_payload(file_bytes: bytes) -> None:
    """Bloquea firmas binarias ejecutables o scripts embebidos al inicio del archivo."""
    if not file_bytes:
        raise ValueError("El archivo está vacío.")
    head_raw = file_bytes[:64]
    head_stripped = head_raw.lstrip().lower()
    if any(head_raw.startswith(sig) for sig in _EXEC_MAGIC_PREFIXES) or head_stripped.startswith(b"<?php"):
        raise ValueError("Archivo rechazado: firma de binario ejecutable o payload inválido.")


def _safe_resolve_pdf_obj(obj: Any) -> Any:
    if isinstance(obj, IndirectObject):
        return obj.get_object()
    return obj


def _scan_pdf_object_tree(reader: PdfReader) -> None:
    """Recorre de forma iterativa y acotada los objetos del PDF buscando código activo o adjuntos."""
    root = reader.trailer.get("/Root")
    if root is None:
        return

    stack: list[tuple[PdfObject | Any, int]] = [(root, 0)]
    visited: set[tuple[int, int]] = set()
    inspected = 0

    while stack and inspected < MAX_PDF_SCAN_OBJECTS:
        current, depth = stack.pop()
        if depth > MAX_PDF_SCAN_DEPTH:
            continue

        if isinstance(current, IndirectObject):
            obj_key = (current.idnum, current.generation)
            if obj_key in visited:
                continue
            visited.add(obj_key)
            try:
                resolved = current.get_object()
            except (PdfReadError, RecursionError, KeyError, ValueError, TypeError, AttributeError, IndexError):
                continue
        else:
            resolved = current

        inspected += 1

        if isinstance(resolved, DictionaryObject):
            action_type = str(_safe_resolve_pdf_obj(resolved.get("/S")) or "")
            if action_type in _PDF_DANGEROUS_ACTIONS:
                raise ValueError(
                    f"PDF rechazado por seguridad: acción activa no permitida ({action_type})."
                )
            for key, val in resolved.items():
                key_s = str(key)
                if key_s in _PDF_DANGEROUS_KEYS:
                    raise ValueError(
                        f"PDF rechazado por seguridad: contiene elementos activos o embebidos ({key_s})."
                    )
                if key_s in ("/Parent", "/Prev", "/Next", "/First", "/Last"):
                    continue
                stack.append((val, depth + 1))
        elif isinstance(resolved, ArrayObject):
            for item in resolved[:2000]:
                stack.append((item, depth + 1))


def validate_pdf_safety(file_bytes: bytes) -> None:
    """Verifica firma PDF, integridad estructural básica y ausencia de JS/Launch/EmbeddedFiles."""
    if not file_bytes or not file_bytes[:64].lstrip().startswith(b"%PDF-"):
        raise ValueError("El archivo PDF tiene cabecera o firma inválida (Fail-closed).")

    try:
        reader = PdfReader(io.BytesIO(file_bytes), strict=False)
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise ValueError(f"No se pudo abrir o verificar la seguridad del PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ValueError(
                    "El PDF está protegido con contraseña. Descárgalo sin clave para importarlo."
                )
        except (PdfReadError, ValueError) as exc:
            raise ValueError("El PDF está protegido con contraseña.") from exc

    _scan_pdf_object_tree(reader)

    for page in reader.pages[:150]:
        try:
            box = page.mediabox
            w_pt = abs(float(box.width))
            h_pt = abs(float(box.height))
        except (PdfReadError, ValueError, TypeError, AttributeError):
            continue
        if w_pt > MAX_PDF_PAGE_POINT_DIM or h_pt > MAX_PDF_PAGE_POINT_DIM:
            raise ValueError(
                "PDF rechazado por seguridad: dimensiones físicas de página anómalas."
            )


def compute_safe_pdf_render_scale(
    width_pt: float,
    height_pt: float,
    target_scale: float = 2.2,
) -> float | None:
    """Calcula escala segura para PDFium acotando memoria en páginas de gran formato."""
    if (
        width_pt <= 0.0
        or height_pt <= 0.0
        or width_pt > MAX_PDF_PAGE_POINT_DIM
        or height_pt > MAX_PDF_PAGE_POINT_DIM
    ):
        return None
    area_pt = width_pt * height_pt
    max_scale = math.sqrt(MAX_PDF_RENDER_PIXELS / max(1.0, area_pt))
    return max(0.15, min(target_scale, max_scale))


def validate_xlsx_zip_safety(file_bytes: bytes) -> None:
    """Inspecciona contenedores .xlsx antes de openpyxl/pandas bloqueando macros, XXE y ZIP-bombs."""
    if not file_bytes[:4].startswith(b"PK\x03\x04"):
        raise ValueError("El archivo Excel .xlsx no posee estructura ZIP válida.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ValueError(f"El archivo Excel .xlsx está corrupto: {exc}") from exc

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_XLSX_ENTRIES:
            raise ValueError(
                "Archivo Excel .xlsx rechazado: supera el límite de componentes internos permitido."
            )

        total_uncompressed = 0
        for info in infos:
            norm_name = info.filename.replace("\\", "/").lstrip("./").lower()
            if ".." in norm_name.split("/") or info.filename.startswith(("/", "\\")):
                raise ValueError("Archivo Excel .xlsx rechazado: ruta interna insegura (path traversal).")

            if (
                "vbaproject.bin" in norm_name
                or "vbadata.xml" in norm_name
                or "/activex/" in norm_name
                or norm_name.startswith("activex/")
                or "xl/embeddings/" in norm_name
                or norm_name.endswith(_XLSX_DANGEROUS_EXTS)
            ):
                raise ValueError(
                    "Archivo Excel .xlsx rechazado: contiene macros o elementos activos no permitidos."
                )

            total_uncompressed += max(0, int(info.file_size))
            if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "Archivo Excel .xlsx rechazado: tamaño descomprimido excesivo (protección ZIP-bomb)."
                )

            if info.file_size > 64 * 1024:
                ratio = float(info.file_size) / float(max(1, info.compress_size))
                if ratio > MAX_XLSX_COMPRESSION_RATIO:
                    raise ValueError(
                        "Archivo Excel .xlsx rechazado: ratio de compresión anómalo (protección ZIP-bomb)."
                    )

            if norm_name.endswith((".xml", ".rels")) and 0 < info.file_size <= MAX_XLSX_XML_CHECK_BYTES:
                sample = zf.read(info)
                lower_xml = sample.lower()
                if b"<!doctype" in lower_xml or b"<!entity" in lower_xml:
                    raise ValueError(
                        "Archivo Excel .xlsx rechazado: contiene declaraciones XML/XXE o entidades peligrosas."
                    )


def validate_xls_safety(file_bytes: bytes) -> Literal["OLE2", "XLSX", "HTML"]:
    """Valida .xls aceptando BIFF OLE2, OOXML renombrado o tablas HTML bancarias sin scripts."""
    assert_not_executable_payload(file_bytes)

    if file_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "OLE2"
    if file_bytes[:4].startswith(b"PK\x03\x04"):
        validate_xlsx_zip_safety(file_bytes)
        return "XLSX"

    head = file_bytes[:4096].lstrip().lower()
    if any(tag in head for tag in (b"<html", b"<table", b"<?xml", b"<tbody", b"<tr")):
        lower_body = file_bytes.lower()
        if any(
            bad in lower_body
            for bad in (b"<script", b"javascript:", b"vbscript:", b"<!doctype", b"<!entity", b"onerror=", b"onload=")
        ):
            raise ValueError(
                "Archivo Excel .xls rechazado: contiene código <script> o XML potencialmente malicioso."
            )
        return "HTML"

    raise ValueError("Archivo rechazado: el .xls no posee firma Excel ni tabla HTML bancaria válida.")


class _StdlibHtmlTableParser(HTMLParser):
    """Parser minimalista sin dependencias externas para exportes .xls basados en HTML bancario."""

    def __init__(self, max_rows: int = 5050) -> None:
        super().__init__(convert_charrefs=True)
        self.max_rows = max_rows
        self.rows: list[list[str]] = []
        self._in_tr = False
        self._in_cell = False
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "tr" and len(self.rows) < self.max_rows:
            self._in_tr = True
            self._cur_row = []
        elif t in ("td", "th") and self._in_tr:
            self._in_cell = True
            self._cur_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cur_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._cur_row.append("".join(self._cur_cell).strip())
        elif t == "tr" and self._in_tr:
            self._in_tr = False
            if any(self._cur_row):
                self.rows.append(self._cur_row)


def parse_html_table_rows(file_bytes: bytes, max_rows: int = 5050) -> list[list[str]]:
    """Extrae filas de tablas HTML exportadas como .xls usando solo html.parser estándar."""
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = file_bytes.decode("latin-1", errors="replace")

    parser = _StdlibHtmlTableParser(max_rows=max_rows)
    parser.feed(text)
    parser.close()
    return parser.rows


def validate_image_magic_bytes(file_bytes: bytes, filename_or_mime: str = "") -> Literal["PNG", "JPEG", "WEBP"]:
    """Verifica magic bytes reales de PNG, JPEG o WEBP (Fail-Closed frente a SVG/HTML/EXE camuflados)."""
    assert_not_executable_payload(file_bytes)
    hint = (filename_or_mime or "").strip().lower()

    is_png = file_bytes[:8].startswith(b"\x89PNG\r\n\x1a\n")
    is_jpg = file_bytes[:3].startswith(b"\xff\xd8\xff")
    is_webp = len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"

    if ".png" in hint or hint == "image/png":
        if not is_png:
            raise ValueError("La imagen PNG tiene firma inválida (Fail-closed).")
        return "PNG"
    if any(k in hint for k in (".jpg", ".jpeg", "image/jpeg", "image/jpg")):
        if not is_jpg:
            raise ValueError("La imagen JPEG tiene firma inválida (Fail-closed).")
        return "JPEG"
    if ".webp" in hint or hint == "image/webp":
        if not is_webp:
            raise ValueError("La imagen WEBP tiene firma inválida (Fail-closed).")
        return "WEBP"

    if is_png:
        return "PNG"
    if is_jpg:
        return "JPEG"
    if is_webp:
        return "WEBP"
    raise ValueError("La imagen subida no tiene firma válida PNG, JPEG ni WEBP (Fail-closed).")


def sanitize_and_load_image(file_bytes: bytes, filename_or_mime: str = "") -> Image.Image:
    """Decodifica imágenes validando bombas de megapíxeles y realizando Pixel-Wash sin metadatos."""
    validate_image_magic_bytes(file_bytes, filename_or_mime)

    try:
        with Image.open(io.BytesIO(file_bytes)) as opened:
            w_px, h_px = opened.size
            if (
                w_px <= 0
                or h_px <= 0
                or w_px > MAX_OCR_IMAGE_LONG_EDGE
                or h_px > MAX_OCR_IMAGE_LONG_EDGE
                or (w_px * h_px) > MAX_OCR_IMAGE_PIXELS
            ):
                raise ValueError(
                    f"Dimensiones de imagen fuera del límite de seguridad ({w_px}x{h_px} px)."
                )
            opened.load()
            oriented = ImageOps.exif_transpose(opened)
            rgb = oriented if oriented.mode == "RGB" else oriented.convert("RGB")
            # Pixel-wash (CDR): reconstruye bitmap RGB puro sin chunks EXIF, XMP, ICC ni comentarios
            return Image.frombytes("RGB", rgb.size, rgb.tobytes())
    except (Image.DecompressionBombError, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"No se pudo decodificar la imagen de forma segura: {exc}") from exc


def image_to_clean_png_bytes(img: Image.Image) -> bytes:
    """Serializa una imagen RGB ya lavada a bytes PNG limpios en memoria."""
    rgb = img if img.mode == "RGB" else img.convert("RGB")
    clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())
    out = io.BytesIO()
    clean.save(out, format="PNG")
    return out.getvalue()


def build_clean_ocr_env() -> dict[str, str]:
    """Construye un entorno mínimo para subprocesos OCR sin secretos ni variables de configuración."""
    cleaned: dict[str, str] = {}
    for key in _CLEAN_ENV_ALLOWLIST:
        val = os.environ.get(key)
        if val is not None:
            cleaned[key] = val
    cleaned.setdefault("LC_ALL", "C.UTF-8")
    cleaned.setdefault("OMP_THREAD_LIMIT", "2")
    return cleaned
