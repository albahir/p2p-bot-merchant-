"""Vista de Reconstrucción Contable P2P de 6 Piezas y OCR Bancario en Streamlit.
Permite carga masiva de archivos de Binance (.csv/.xlsx), escaneo inteligente de
comprobantes bancarios vía Gemini Vision y balance de consistencia patrimonial.
"""

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from config.settings import Settings
from src.core.file_parser import BinanceFileParser
from src.data.database import SessionLocal
from src.data.models import BankVoucher
from src.data.repositories import FiscalSnapshotRepository
from src.integrations.receipt_ocr import BankReceiptOCR, process_and_save_voucher
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.fiscal_reconciler import FiscalReconciler
from src.reporting.sheets_exporter import SheetsExporter


def render_fiscal_reconstruction() -> None:
    """Renderiza el panel de Reconstrucción Contable de 6 Piezas y OCR Bancario."""
    st.subheader(":material/account_balance: Reconstrucción Contable P2P de 6 Piezas")
    st.caption(
        "Auditoría y consistencia patrimonial: "
        "Saldo Inicial + Entradas (Depósitos + Compras) - Salidas (Retiros + Ventas) - Comisiones = Saldo Final Teórico."
    )

    db = SessionLocal()
    try:
        # -------------------------------------------------------------
        # SECCIÓN 1: Ingesta de Archivos de Binance (.csv / .xlsx)
        # -------------------------------------------------------------
        with st.expander(":material/upload_file: Cargar Archivos Históricos de Binance (C2C, Depósitos, Retiros)", expanded=False):
            st.write(
                "Sube los archivos exportados desde Binance (Historial de órdenes C2C, Depósitos y Retiros). "
                "El sistema omite automáticamente filas de metadatos en Excel y detecta columnas en español o inglés."
            )
            uploaded_binance_files = st.file_uploader(
                "Selecciona uno o varios archivos (.csv o .xlsx)",
                type=["csv", "xlsx"],
                accept_multiple_files=True,
                key="binance_file_uploader",
            )

            if uploaded_binance_files and st.button("Procesar Archivos de Binance", key="btn_process_binance", width="stretch"):
                total_orders = 0
                total_movements = 0
                for u_file in uploaded_binance_files:
                    content_bytes = u_file.read()
                    res = BinanceFileParser.import_into_database(
                        content=content_bytes,
                        file_name=u_file.name,
                        db=db,
                    )
                    orders_added = res.get("orders_imported", 0)
                    movs_added = res.get("movements_imported", 0)
                    total_orders += orders_added
                    total_movements += movs_added
                    st.write(f"• **{u_file.name}**: {orders_added} órdenes importadas, {movs_added} movimientos importados.")

                st.success(f"¡Procesamiento finalizado! Total órdenes: {total_orders}, Total movimientos: {total_movements}")

        # -------------------------------------------------------------
        # SECCIÓN 2: OCR Bancario Multimodal con Gemini Vision
        # -------------------------------------------------------------
        with st.expander(":material/document_scanner: OCR de Comprobantes Bancarios (Pago Móvil / Transferencias)", expanded=False):
            st.write(
                "Sube capturas de pantalla de comprobantes bancarios venezolanos. "
                "Gemini Vision extraerá la referencia, banco, monto en bolívares y titular, auto-vinculándolos con las órdenes P2P."
            )
            uploaded_receipts = st.file_uploader(
                "Selecciona comprobantes (PNG, JPG, JPEG)",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="receipt_file_uploader",
            )

            if uploaded_receipts and st.button("Escanear y Conciliar Comprobantes", key="btn_process_receipts", width="stretch"):
                ocr = BankReceiptOCR()
                for r_file in uploaded_receipts:
                    img_bytes = r_file.read()
                    voucher, matched_order = process_and_save_voucher(
                        image_bytes=img_bytes,
                        db=db,
                        ocr_service=ocr,
                    )
                    match_info = (
                        f"🟢 Vinculado a orden `{matched_order.order_number}`"
                        if matched_order
                        else "🟡 Guardado sin orden coincidente"
                    )
                    st.write(
                        f"• **{r_file.name}**: Banco *{voucher.bank_name}*, "
                        f"Ref: `{voucher.reference_number}`, "
                        f"Monto: `{voucher.amount_ves:,.2f} VES` — {match_info}"
                    )
                st.success("¡Comprobantes procesados e insertados con éxito!")

            # Mostrar últimos comprobantes registrados
            recent_vouchers = (
                db.query(BankVoucher)
                .order_by(BankVoucher.id.desc())
                .limit(20)
                .all()
            )
            if recent_vouchers:
                st.markdown("##### Comprobantes Registrados Recientes")
                v_data = [
                    {
                        "ID": v.id,
                        "Banco": v.bank_name,
                        "Referencia": v.reference_number,
                        "Monto (VES)": f"{v.amount_ves:,.2f}",
                        "Titular": v.sender_name or "-",
                        "Cédula": v.sender_id or "-",
                        "Orden P2P": v.associated_order_number or "-",
                        "Estado": v.verification_status,
                        "Fecha": v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "-",
                    }
                    for v in recent_vouchers
                ]
                st.dataframe(pd.DataFrame(v_data), width="stretch")

        # -------------------------------------------------------------
        # SECCIÓN 3: Reconciliación Mensual de 6 Piezas
        # -------------------------------------------------------------
        st.write("---")
        st.markdown("#### :material/sync_alt: Cálculo de Consistencia Patrimonial")

        now = datetime.now(UTC)
        col_period, col_init, col_actual = st.columns(3)

        with col_period:
            period_val = st.text_input("Período (YYYY-MM):", value=f"{now.year:04d}-{now.month:02d}")

        # Consultar snapshot anterior o existente para pre-llenar valores
        snap_repo = FiscalSnapshotRepository(db)
        existing_snap = snap_repo.get_by_period(period_val)

        default_init = float(existing_snap.initial_balance) if existing_snap else 0.0
        default_actual = float(existing_snap.actual_final_balance) if existing_snap else 0.0

        with col_init:
            init_balance = st.number_input(
                "1. Saldo Inicial USDT (Apertura):",
                min_value=0.0,
                value=default_init,
                step=10.0,
                format="%.2f",
            )

        with col_actual:
            actual_balance = st.number_input(
                "6. Saldo Final Real USDT (Snapshot):",
                min_value=0.0,
                value=default_actual,
                step=10.0,
                format="%.2f",
            )

        if st.button("Ejecutar Reconstrucción Contable", type="primary", width="stretch"):
            reconciler = FiscalReconciler(db_session=db)
            recon = reconciler.reconcile_period(
                period=period_val,
                initial_balance=init_balance,
                actual_final_balance=actual_balance if actual_balance > 0 else None,
            )

            # Estatus de consistencia
            if recon.status == "BALANCED":
                st.success(f"🟢 **CONSISTENCIA PATRIMONIAL CONFIRMADA**: {recon.message}")
            else:
                st.error(f"🔴 **DISCREPANCIA DETECTADA**: {recon.message}")

            # Mostrar las 6 Piezas en tarjetas
            st.markdown("##### Las 6 Piezas de Reconstrucción Contable")
            c1, c2, c3 = st.columns(3)
            with c1, st.container(border=True):
                st.metric("1. Saldo Inicial", f"{recon.initial_balance:,.2f} USDT")
                st.caption("Apertura patrimonial del período")
            with c2, st.container(border=True):
                st.metric("2. Total Entradas", f"{recon.total_inflows:,.2f} USDT")
                st.caption(f"Depósitos: {recon.inflows_deposits:,.2f} | Compras P2P: {recon.inflows_p2p_buys:,.2f}")
            with c3, st.container(border=True):
                st.metric("3. Total Salidas", f"{recon.total_outflows:,.2f} USDT")
                st.caption(f"Retiros: {recon.outflows_withdrawals:,.2f} | Ventas P2P: {recon.outflows_p2p_sells:,.2f}")

            c4, c5, c6 = st.columns(3)
            with c4, st.container(border=True):
                st.metric("4. Volumen Operado", f"{recon.volume_operated:,.2f} USDT")
                st.caption(f"{recon.orders_count} órdenes procesadas")
            with c5, st.container(border=True):
                st.metric("5. Comisiones Totales", f"{recon.total_fees:,.4f} USDT")
                st.caption("Costos de red y retiros on-chain")
            with c6, st.container(border=True):
                delta_label = f"Dif: {recon.discrepancy:+.4f}" if recon.discrepancy != 0 else "0.00"
                st.metric(
                    "6. Saldo Final",
                    f"{recon.actual_final_balance:,.2f} USDT",
                    delta=delta_label if recon.discrepancy != 0 else None,
                    delta_color="inverse",
                )
                st.caption(f"Calculado Teórico: {recon.calculated_final_balance:,.2f} USDT")

            # Tarjetas de Liquidación Fiscal ISLR
            st.markdown("##### Liquidación Tributaria Estimada (ISLR - Método FIFO)")
            tax_c1, tax_c2, tax_c3, tax_c4 = st.columns(4)
            with tax_c1, st.container(border=True):
                st.metric("Ingresos Brutos", f"{recon.gross_revenue_ves:,.2f} VES")
            with tax_c2, st.container(border=True):
                st.metric("Costo de Adquisición", f"{recon.acquisition_cost_ves:,.2f} VES")
            with tax_c3, st.container(border=True):
                st.metric("Ganancia Fiscal (VES)", f"{recon.net_profit_ves:,.2f} VES")
            with tax_c4, st.container(border=True):
                st.metric("Ganancia Neta (USD)", f"${recon.net_profit_usd:,.2f}")

            # Guardar Snapshot en base de datos
            reconciler.save_snapshot(recon)
            st.info("💾 Snapshot de balance mensual registrado y actualizado en la base de datos.")

            # Descarga de Excel de 4 Pestañas
            st.write("---")
            st.markdown("##### Exportación Multi-Pestaña de Auditoría")

            # Consultar datos detallados para el reporte
            start_dt, end_dt = FiscalReconciler._parse_period_dates(recon.period)
            p2p_orders = reconciler.order_repo.list_completed(start_date=start_dt, end_date=end_dt)
            wallet_movements = reconciler.wallet_repo.list_completed(start_date=start_dt, end_date=end_dt)
            vouchers = (
                db.query(BankVoucher)
                .filter(BankVoucher.created_at >= start_dt, BankVoucher.created_at <= end_dt)
                .all()
            )

            excel_path = f"reporte_reconstruccion_fiscal_{recon.period}.xlsx"
            ExcelReporter.generate_fiscal_reconstruction_report(
                reconciliation=recon,
                p2p_orders=p2p_orders,
                wallet_movements=wallet_movements,
                vouchers=vouchers,
                output_path=excel_path,
            )

            col_down, col_sync = st.columns(2)
            with col_down, open(excel_path, "rb") as f_excel:
                st.download_button(
                    label="📥 Descargar Informe Integral de 4 Pestañas (.xlsx)",
                    data=f_excel.read(),
                    file_name=excel_path,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )

            with col_sync:
                try:
                    settings = Settings()
                    sheet_id = settings.GOOGLE_SHEET_ID
                    if sheet_id:
                        sheet_url = SheetsExporter.get_sheet_url(sheet_id)
                        if st.button("📊 Sincronizar 4 Pestañas con Google Sheets", key="btn_sync_sheets_4tabs", width="stretch"):
                            exporter = SheetsExporter(
                                credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
                                credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
                            )
                            sync_ok = exporter.export_fiscal_reconstruction(
                                sheet_id=sheet_id,
                                reconciliation=recon,
                                p2p_orders=p2p_orders,
                                wallet_movements=wallet_movements,
                                vouchers=vouchers,
                            )
                            if sync_ok:
                                st.success(f"¡Google Sheets actualizado con 4 pestañas! [Abrir Hoja]({sheet_url})")
                            else:
                                st.error(f"Error sincronizando: {exporter.last_error}")
                    else:
                        st.caption("Google Sheets no configurado (`GOOGLE_SHEET_ID`).")
                except (KeyError, ValueError, OSError, RuntimeError) as ex:
                    st.caption(f"Google Sheets no disponible: {ex}")

    finally:
        db.close()
