"""Centro interactivo de comprobantes bancarios y uploader OCR en memoria (SPEC-013)."""

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from src.data.models import BankVoucher
from src.integrations.receipt_ocr import process_and_save_voucher
from src.reporting.dashboard.theme import render_status_badge


def render_receipt_center(db: Session, st_module: Any = None) -> None:
    """Renderiza el centro interactivo de comprobantes bancarios y OCR."""
    try:
        import streamlit as st
        ui = st_module or st
    except (ImportError, RuntimeError):
        ui = st_module

    if ui is None:
        return

    ui.subheader(":material/receipt_long: Centro de Comprobantes Bancarios (OCR)")

    # 1. Widget de Carga Directa (Memory-only)
    with ui.container(border=True):
        ui.markdown("#### :material/add_photo_alternate: Procesar Nueva Captura de Pago")
        uploaded_file = ui.file_uploader(
            "Arrastra o selecciona el capture del comprobante (Pago Móvil / Transferencia):",
            type=["png", "jpg", "jpeg", "webp"],
            help="Procesamiento en memoria volátil con Gemini Vision. Máximo 10MB.",
        )

        if uploaded_file is not None:
            img_bytes = uploaded_file.getvalue()
            if len(img_bytes) > 10 * 1024 * 1024:
                ui.error("El archivo excede el tamaño máximo permitido de 10 MB.")
            else:
                if ui.button(":material/document_scanner: Analizar y Conciliar Comprobante", width="stretch"):
                    with ui.spinner("Ejecutando OCR multimodal con Gemini Vision..."):
                        try:
                            voucher, _matched_order = process_and_save_voucher(
                                img_bytes,
                                db,
                                mime_type=uploaded_file.type or "image/jpeg",
                            )
                            if voucher:
                                status_badge = (
                                    render_status_badge("VINCULADO", "success")
                                    if voucher.verification_status == "MATCHED"
                                    else render_status_badge("REGISTRADO (Sin orden coincidente)", "warning")
                                )
                                ui.success("¡Comprobante procesado y registrado con éxito en base de datos!")
                                ui.markdown(
                                    f"• **Banco**: `{voucher.bank_name}`\n"
                                    f"• **Referencia**: `{voucher.reference_number}`\n"
                                    f"• **Monto**: `{voucher.amount_ves:,.2f} VES`\n"
                                    f"• **Emisor**: `{voucher.sender_name or '-'} ({voucher.sender_id or '-'})`\n"
                                    f"• **Orden P2P**: `{voucher.associated_order_number or 'Ninguna coincidente'}`\n"
                                    f"• **Estado**: {status_badge}",
                                    unsafe_allow_html=True,
                                )
                            else:
                                ui.warning("No se pudo extraer la información del comprobante. Intenta con una imagen más nítida.")
                        except (ValueError, KeyError, RuntimeError, OSError) as e:
                            ui.error(f"Error procesando el comprobante: {e}")

    # 2. Historial de Comprobantes Registrados
    vouchers = db.query(BankVoucher).order_by(BankVoucher.id.desc()).limit(200).all()

    total_v = len(vouchers)
    matched_v = sum(1 for v in vouchers if v.verification_status == "MATCHED")
    unmatched_v = total_v - matched_v

    c1, c2, c3 = ui.columns(3)
    with c1:
        ui.metric("Total Comprobantes", total_v)
    with c2:
        ui.metric("Conciliados con Éxito", matched_v)
    with c3:
        ui.metric("Pendientes por Conciliar", unmatched_v)

    if not vouchers:
        ui.info("No hay comprobantes bancarios registrados aún. Puedes subir capturas desde este panel o enviarlas al bot de Telegram.")
        return

    # Filtros
    filter_col1, filter_col2 = ui.columns(2)
    with filter_col1:
        status_filter = ui.selectbox(
            "Filtrar por Estado",
            ["TODOS", "MATCHED (Vinculados)", "UNMATCHED (Sin Vincular)"],
        )
    with filter_col2:
        all_banks = sorted({v.bank_name for v in vouchers if v.bank_name})
        bank_filter = ui.selectbox("Filtrar por Banco", ["TODOS"] + all_banks)


    filtered = vouchers
    if status_filter == "MATCHED (Vinculados)":
        filtered = [v for v in filtered if v.verification_status == "MATCHED"]
    elif status_filter == "UNMATCHED (Sin Vincular)":
        filtered = [v for v in filtered if v.verification_status != "MATCHED"]

    if bank_filter != "TODOS":
        filtered = [v for v in filtered if v.bank_name == bank_filter]

    table_data = [
        {
            "Fecha": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "-",
            "Banco": v.bank_name,
            "Referencia": v.reference_number,
            "Monto (VES)": f"{v.amount_ves:,.2f}",
            "Cédula": v.sender_id or "-",
            "Titular": v.sender_name or "-",
            "Método": v.payment_method,
            "Orden P2P": v.associated_order_number or "-",
            "Estatus": v.verification_status,
        }
        for v in filtered
    ]

    ui.dataframe(pd.DataFrame(table_data), width="stretch")
