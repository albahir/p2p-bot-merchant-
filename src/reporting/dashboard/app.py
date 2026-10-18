"""Dashboard y Panel de Control (Mission Control) para el Bot P2P Merchant.
Opera en modo seguro con autenticación RBAC y aislamiento estricto de roles.
"""

from typing import Any, cast

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.core.spread_monitor import SpreadMonitor
from src.data.database import SessionLocal
from src.data.models import BankVoucher, Order, SecurityEvent
from src.data.repositories import IdentityRepository, OrderRepository, UserRepository
from src.reporting.dashboard.components.ai_telemetry import render_ai_telemetry
from src.reporting.dashboard.components.arbitrage_matrix import (
    render_arbitrage_matrix,
    render_maker_calculator,
)
from src.reporting.dashboard.components.control_actions import render_control_actions
from src.reporting.dashboard.components.credential_manager import render_credential_manager
from src.reporting.dashboard.components.fiscal_reconstruction_view import (
    render_fiscal_reconstruction,
)
from src.reporting.dashboard.components.kpi_cards import render_fintech_kpis
from src.reporting.dashboard.components.receipt_center import render_receipt_center
from src.reporting.dashboard.components.terminal_header import render_terminal_header
from src.reporting.dashboard.components.test_runner_view import render_test_runner
from src.reporting.dashboard.theme import apply_stitch_theme
from src.reporting.dashboard.views.login_view import render_login_view
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod
from src.security.auth_service import AuthService
from src.security.identity_service import IdentityService


def get_visible_tabs_for_role(role: str) -> list[str]:
    """Retorna la lista de pestañas visibles en el Dashboard según el rol del usuario."""
    r = str(role).strip().upper()
    if r == "INVITADO":
        return ["📈 Monitor & Arbitraje P2P"]
    elif r == "TRADER":
        return [
            "📊 Visión General",
            "📈 Monitor & Arbitraje P2P",
            "👤 Directorio Cédulas",
            "🧾 Comprobantes OCR",
            "⚖️ Reconstrucción 6 Piezas",
            "📑 Motor Fiscal (ISLR)",
            "🤖 Telemetría IA",
            "🧪 Suite de Tests",
            "🛡️ Auditoría",
        ]
    else:  # ADMIN
        return [
            "📊 Visión General",
            "📈 Monitor & Arbitraje P2P",
            "👤 Directorio Cédulas",
            "🧾 Comprobantes OCR",
            "⚖️ Reconstrucción 6 Piezas",
            "📑 Motor Fiscal (ISLR)",
            "🕹️ Panel de Tareas",
            "🤖 Telemetría IA",
            "🔑 Credenciales",
            "🧪 Suite de Tests",
            "🛡️ Auditoría",
        ]


def render_overview_tab() -> None:
    """1. Visión General de Órdenes y KPIs."""
    st.subheader(":material/monitoring: Métricas Operativas de la Terminal")
    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        completed_orders = repo.list_completed()
        all_orders = db.query(Order).order_by(Order.id.desc()).limit(100).all()

        if not all_orders:
            st.info("No hay órdenes registradas en el sistema. Ejecuta una sincronización o simulación desde el Panel de Tareas.")
        else:
            if completed_orders:
                total_vol = sum(o.fiat_amount for o in completed_orders)
                fifo_engine = FIFOCostMethod()
                results = fifo_engine.process_orders(completed_orders)
                profit_ves = sum(r.net_profit_fiat for r in results)
                profit_usd = sum(r.net_profit_usd for r in results)

                vouchers = db.query(BankVoucher).all()
                tot_v = len(vouchers)
                mat_v = sum(1 for v in vouchers if v.verification_status == "MATCHED")
                ratio_str = f"{mat_v}/{tot_v}" if tot_v > 0 else "0/0"

                render_fintech_kpis(
                    orders_count=len(completed_orders),
                    volume_ves=total_vol,
                    net_profit_ves=profit_ves,
                    net_profit_usd=profit_usd,
                    vouchers_ratio=ratio_str,
                    bcv_spread="+4.5%",
                    st_module=st,
                )
            else:
                st.warning("Hay órdenes registradas pero ninguna en estado COMPLETED.")

            st.write("---")
            st.markdown(f"#### Historial de Transacciones (Mostrando {len(all_orders)} más recientes)")
            data = [
                {
                    "ID": o.id,
                    "Orden": o.order_number,
                    "Tipo": o.trade_type,
                    "Contraparte": o.counterparty_name or "-",
                    "Estado": o.order_status,
                    "Activo": o.asset,
                    "Monto Fíat (VES)": f"{o.fiat_amount:,.2f}",
                    "Monto Cripto": f"{o.crypto_amount:,.2f}",
                    "Precio Unitario": f"{o.unit_price:,.4f}",
                    "Comisión (VES)": f"{o.fee_fiat:,.2f}",
                    "Tasa BCV": f"{o.bcv_rate:,.2f}",
                    "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for o in all_orders
            ]
            st.dataframe(pd.DataFrame(data), width="stretch")
    finally:
        db.close()


def render_spread_tab() -> None:
    """2. Monitor de Spreads Bancarios y Calculadora Maker."""
    monitor = SpreadMonitor()
    market_quotes = monitor.get_market_quotes()
    bcv_rate = 820.0
    db = SessionLocal()
    try:
        latest_order = db.query(Order).filter(cast(Any, Order.bcv_rate > 0)).order_by(Order.id.desc()).first()
        if latest_order and latest_order.bcv_rate:
            bcv_rate = float(latest_order.bcv_rate)
    finally:
        db.close()

    p2p_ref = market_quotes[0].buy_rate if market_quotes else 0.0
    bcv_gap = monitor.calculate_bcv_gap(p2p_price=p2p_ref, bcv_rate=bcv_rate)

    render_arbitrage_matrix(quotes=market_quotes, bcv_rate=bcv_rate, bcv_gap_pct=bcv_gap, st_module=st)
    st.divider()
    render_maker_calculator(st_module=st)


def render_identity_tab() -> None:
    """Directorio y Verificación Oficial de Cédulas (MetaP2P + Base de Datos Permanente)."""
    st.subheader(":material/badge: Directorio y Verificación de Cédulas")
    st.caption("Verificación de identidades oficiales en MetaP2P y almacenamiento permanente para debida diligencia.")

    db = SessionLocal()
    try:
        service = IdentityService(db=db)
        repo = IdentityRepository(db)

        st.markdown("##### 🔍 Consultar Titular Oficial")
        col_in, col_btn = st.columns([3, 1])
        with col_in:
            query_cedula = st.text_input(
                "Documento de Identidad (V / E / J):",
                placeholder="Ej: V12345678, E-81234567 o 12345678",
                key="id_lookup_input",
                label_visibility="collapsed",
            )
        with col_btn:
            search_btn = st.button("🔎 Consultar", type="primary", use_container_width=True)

        active_user = str(st.session_state.get("username", "Operador Web"))
        if search_btn and query_cedula.strip():
            with st.spinner("Consultando MetaP2P y Base de Datos..."):
                res = service.resolve_identity(query_cedula.strip(), queried_by=active_user)
                if res.get("full_name"):
                    st.success(f"✅ Titular Oficial: **{res['full_name']}**")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Documento", f"{res.get('nationality', 'V')}-{res.get('cedula', '')}")
                    m2.metric("Fuente", res.get("source", "MetaP2P"))
                    m3.metric("Almacenamiento", f"💾 Guardado (por {active_user})")
                else:
                    st.error(f"❌ {res.get('error', 'Cédula no localizada en MetaP2P ni en base de datos local')}")

        st.divider()
        st.markdown("##### 📇 Directorio Permanente de Cédulas Registradas")

        filtro = st.text_input("Filtrar por nombre o cédula:", placeholder="Escribe para buscar...", key="filter_cedulas_input")
        if filtro.strip():
            records = repo.search(filtro.strip())
        else:
            records = repo.list_all()

        st.caption(f"Total registros permanentes en base de datos: **{len(records)}**")
        if records:
            data = [
                {
                    "ID": r.id,
                    "Nacionalidad": r.nationality,
                    "Cédula": r.cedula,
                    "Nombre Completo": r.full_name,
                    "Fuente": r.source,
                    "Consultado Por": getattr(r, "queried_by", "-") or "Sistema",
                    "Fecha Registro": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "-",
                }
                for r in records
            ]
            st.dataframe(pd.DataFrame(data), width="stretch")
        else:
            st.info("No hay identidades registradas en el directorio permanente.")
    finally:
        db.close()


def render_receipts_tab() -> None:
    """3. Centro de Comprobantes Bancarios OCR."""
    db = SessionLocal()
    try:
        render_receipt_center(db=db)
    finally:
        db.close()


def render_reconcile_tab() -> None:
    """4. Reconstrucción Contable de 6 Piezas y Consistencia."""
    render_fiscal_reconstruction()


def render_tax_tab() -> None:
    """5. Motor Fiscal con Descarga Directa."""
    st.subheader(":material/calculate: Cálculo y Declaración Fiscal")
    method_choice = st.segmented_control("Método Contable:", ["FIFO", "Costo Promedio Ponderado"], default="FIFO")

    db = SessionLocal()
    try:
        repo = OrderRepository(db)
        orders = repo.list_completed()
        if not orders:
            st.info("No hay órdenes completadas para calcular impuestos.")
        else:
            engine = FIFOCostMethod() if method_choice == "FIFO" else WeightedAverageCostMethod()
            tax_results = engine.process_orders(orders)

            if not tax_results:
                st.info("No se han registrado ventas (SELL) aún para liquidar inventario.")
            else:
                tax_data = [
                    {
                        "Orden Venta": r.order_number,
                        "Cripto Vendida": f"{r.crypto_amount:,.2f} USDT",
                        "Ingreso Bruto (VES)": f"{r.total_revenue_fiat:,.2f} Bs.",
                        "Costo Adquisición (VES)": f"{r.acquisition_cost_fiat:,.2f} Bs.",
                        "Comisión (VES)": f"{r.fee_fiat:,.2f} Bs.",
                        "Ganancia Neta (VES)": f"{r.net_profit_fiat:,.2f} Bs.",
                        "Tasa BCV Oficial": f"{r.bcv_rate:,.2f}",
                        "Ganancia Neta (USD)": f"${r.net_profit_usd:,.2f}",
                    }
                    for r in tax_results
                ]
                st.dataframe(pd.DataFrame(tax_data), width="stretch")

                # Botones de Descarga Excel (Fiscal y Compliance Bancario)
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    report_file = "reporte_fiscal_p2p.xlsx"
                    ExcelReporter.generate_tax_report(tax_results, report_file)
                    with open(report_file, "rb") as f:
                        st.download_button(
                            label="📥 Descargar Reporte Fiscal (.xlsx)",
                            data=f.read(),
                            file_name="reporte_fiscal_p2p.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch",
                        )

                with col_dl2:
                    all_vouchers = db.query(BankVoucher).all()
                    compliance_file = "certificacion_origen_fondos.xlsx"
                    ExcelReporter.generate_compliance_report(
                        orders=orders,
                        vouchers=all_vouchers,
                        account_holder="COMERCIANTE P2P REGISTRADO",
                        rif="V-00000000-0",
                        period="Período Actual",
                        output_path=compliance_file,
                    )
                    with open(compliance_file, "rb") as cf:
                        st.download_button(
                            label="🏛️ Descargar Certificación Bancaria / Compliance (.xlsx)",
                            data=cf.read(),
                            file_name="certificacion_origen_fondos_p2p.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch",
                            help="Genera el informe institucional para prevención de bloqueos bancarios en Venezuela.",
                        )

                # Sincronización con Google Sheets
                st.write("---")
                st.markdown("#### :material/table_chart: Sincronización con Google Sheets")
                from config.settings import Settings
                from src.reporting.sheets_exporter import SheetsExporter

                try:
                    dashboard_settings = Settings()
                    sheet_id = dashboard_settings.GOOGLE_SHEET_ID
                    if sheet_id:
                        sheet_url = SheetsExporter.get_sheet_url(sheet_id)
                        st.markdown(f"🔗 **Documento vinculado**: [{sheet_id}]({sheet_url})")
                        if st.button("📊 Sincronizar Ahora con Google Sheets", width="stretch"):
                            exporter = SheetsExporter(
                                credentials_path=dashboard_settings.GOOGLE_CREDENTIALS_FILE,
                                credentials_json=dashboard_settings.GOOGLE_SERVICE_ACCOUNT_JSON,
                            )
                            if exporter.export(sheet_id, tax_results):
                                st.success(f"¡Sincronizado exitosamente! [Abrir Google Sheets]({sheet_url})")
                            else:
                                err_msg = exporter.last_error or "Revisa credenciales o permisos de la hoja."
                                st.error(f"Error al sincronizar con Google Sheets: {err_msg}")
                    else:
                        st.info("💡 Para activar la sincronización con Google Sheets, define `GOOGLE_SHEET_ID` en `config/.env` o variables de entorno.")
                except (ValueError, KeyError, OSError, RuntimeError) as ex:
                    st.warning(f"Configuración de Google Sheets no disponible: {ex}")
    finally:
        db.close()


def render_control_tab() -> None:
    """6. Panel de Control de Tareas Operativas."""
    render_control_actions()


def render_ai_tab() -> None:
    """7. Telemetría del Pool de Claves de IA (Gemini Vision)."""
    render_ai_telemetry()


def render_credentials_tab() -> None:
    """8. Gestor de Credenciales Cifradas y Usuarios del Sistema."""
    render_credential_manager()

    st.write("---")
    st.subheader(":material/group: Gestión de Usuarios y Roles (RBAC)")
    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        users = user_repo.list_all()
        if not users:
            st.info("No hay usuarios registrados en el sistema.")
        else:
            users_data = [
                {
                    "ID": u.id,
                    "Usuario": u.username,
                    "Rol": u.role,
                    "Telegram ID": u.telegram_id or "-",
                    "Estado": "🟢 Activo" if u.is_active else "🔴 Inactivo",
                    "Fecha Creación": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-",
                }
                for u in users
            ]
            st.dataframe(pd.DataFrame(users_data), width="stretch")
    finally:
        db.close()


def render_tests_tab() -> None:
    """9. Suite de Tests Automatizados."""
    render_test_runner()


def render_security_tab() -> None:
    """10. Auditoría de Seguridad (SHA-256)."""
    st.subheader(":material/security: Eventos de Auditoría (Append-Only SHA-256)")
    db = SessionLocal()
    try:
        events = db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(100).all()
        if not events:
            st.info("No se han registrado eventos de seguridad aún.")
        else:
            events_data = [
                {
                    "ID": e.id,
                    "Timestamp (UTC)": e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo de Evento": e.event_type,
                    "Identificador": e.key_identifier,
                    "IP": e.ip_address,
                    "Estado": e.status,
                    "Hash Evento": e.event_hash[:16] + "...",
                }
                for e in events
            ]
            st.dataframe(pd.DataFrame(events_data), width="stretch")
    finally:
        db.close()


# =========================================================================
# CONFIGURACIÓN Y PUNTO DE ENTRADA DEL DASHBOARD
# =========================================================================

st.set_page_config(
    page_title="P2P Merchant Bot — Terminal & Mission Control",
    page_icon=":material/terminal:",
    layout="wide",
)

# Inyectar estilos Stitch Glassmorphism
apply_stitch_theme(st)

# Control de Autenticación Fail-Closed
if not st.session_state.get("authenticated", False):
    render_login_view()
    st.stop()

# Usuario autenticado
active_role = str(st.session_state.get("role", "INVITADO")).upper()
active_username = str(st.session_state.get("username", "Operador"))

# Mapeo de renderers por nombre de pestaña/panel
TAB_RENDERERS: dict[str, Any] = {
    "📊 Visión General": render_overview_tab,
    "📈 Monitor & Arbitraje P2P": render_spread_tab,
    "👤 Directorio Cédulas": render_identity_tab,
    "🧾 Comprobantes OCR": render_receipts_tab,
    "⚖️ Reconstrucción 6 Piezas": render_reconcile_tab,
    "📑 Motor Fiscal (ISLR)": render_tax_tab,
    "🕹️ Panel de Tareas": render_control_tab,
    "🤖 Telemetría IA": render_ai_tab,
    "🔑 Credenciales": render_credentials_tab,
    "🧪 Suite de Tests": render_tests_tab,
    "🛡️ Auditoría": render_security_tab,
}

visible_tab_names = get_visible_tabs_for_role(active_role)

# Barra lateral de perfil, navegación y control de sesión
with st.sidebar:
    badge_class = "badge-matched" if active_role == "ADMIN" else "badge-unmatched" if active_role == "TRADER" else "badge-warning"
    st.markdown(
        f"""
        <div class="fintech-card" style="padding: 0.85rem; margin-bottom: 0.75rem;">
            <div style="font-size: 0.72rem; color: #8B949E; text-transform: uppercase; font-weight: 600;">Operador Activo</div>
            <div style="font-size: 1.05rem; font-weight: 700; color: #F0F6FC; margin: 0.2rem 0;">👤 {active_username}</div>
            <span class="badge-pill {badge_class}">{active_role}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("<div style='font-size: 0.75rem; color: #8B949E; text-transform: uppercase; font-weight: 600; margin-bottom: 0.4rem;'>Paneles del Sistema</div>", unsafe_allow_html=True)

    # Navegación lateral entre los paneles permitidos según rol
    selected_panel = st.radio(
        "Navegación de Paneles",
        options=visible_tab_names,
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Opción 1: Cambio de Contraseña de la cuenta activa
    with st.expander("🔒 Cambiar mi Contraseña"), st.form("sidebar_change_password_form", clear_on_submit=True):
        curr_pass = st.text_input("Contraseña Actual", type="password")
        new_pass = st.text_input("Nueva Contraseña", type="password")
        conf_pass = st.text_input("Confirmar Nueva Contraseña", type="password")
        btn_ch_pass = st.form_submit_button("Actualizar Clave", use_container_width=True)

        if btn_ch_pass:
            if not curr_pass.strip() or not new_pass.strip():
                st.warning("Completa todos los campos.")
            elif len(new_pass.strip()) < 6:
                st.warning("La nueva clave debe tener al menos 6 caracteres.")
            elif new_pass != conf_pass:
                st.error("Las contraseñas no coinciden.")
            else:
                db = SessionLocal()
                try:
                    auth = AuthService(db_session=db)
                    user = auth.authenticate_user(active_username, curr_pass)
                    if not user:
                        st.error("La contraseña actual es incorrecta.")
                    else:
                        from src.data.repositories import UserRepository
                        repo = UserRepository(db)
                        new_hash = AuthService.hash_password(new_pass.strip())
                        repo.update_password(int(user.id), new_hash)
                        st.success("✅ Contraseña actualizada exitosamente.")
                except (SQLAlchemyError, ValueError, OSError, RuntimeError) as e:
                    st.error(f"Error al actualizar contraseña: {e}")
                finally:
                    db.close()

    # Opción 2: Registro rápido de nuevos Traders (Exclusivo para ADMIN)
    if active_role == "ADMIN":
        with st.expander("👤 Registrar Nuevo Trader"), st.form("sidebar_create_trader_form", clear_on_submit=True):
            trader_user = st.text_input("Usuario Trader", placeholder="Ej: trader_juan")
            trader_tg = st.text_input("Telegram ID (opcional)", placeholder="Ej: 6326947793")
            trader_pass = st.text_input("Contraseña Inicial", type="password", placeholder="Mínimo 6 caracteres")
            trader_role = st.selectbox("Rol Asignado", ["TRADER", "INVITADO"], index=0)
            btn_create_trader = st.form_submit_button("Crear Cuenta", use_container_width=True)

            if btn_create_trader:
                if not trader_user.strip() or not trader_pass.strip():
                    st.warning("Completa usuario y contraseña.")
                elif len(trader_pass.strip()) < 6:
                    st.warning("La contraseña debe tener mínimo 6 caracteres.")
                else:
                    db = SessionLocal()
                    try:
                        from src.data.repositories import UserRepository
                        repo = UserRepository(db)
                        if repo.get_by_username(trader_user.strip()):
                            st.error("Este usuario ya existe.")
                        else:
                            h = AuthService.hash_password(trader_pass.strip())
                            u = repo.create_user(
                                username=trader_user.strip(),
                                password_hash=h,
                                role=trader_role,
                                telegram_id=trader_tg.strip() if trader_tg.strip() else None,
                                is_active=True,
                            )
                            st.success(f"✅ ¡Usuario `{u.username}` creado como `{u.role}`!")
                    except (SQLAlchemyError, ValueError, OSError, RuntimeError) as e:
                        st.error(f"Error creando usuario: {e}")
                    finally:
                        db.close()

st.title(":material/terminal: P2P Merchant Bot — Terminal Operativa")

# Barra Superior de Telemetría
render_terminal_header(
    bot_mode="PRODUCTION",
    ip_address="Auto-detect",
    api_weight=120,
    fail_closed=True,
    st_module=st,
)

# Renderizado del panel seleccionado en la barra lateral
if active_role == "INVITADO" and selected_panel == "📈 Monitor & Arbitraje P2P":
    st.info("👁️ **Modo Invitado**: Visualización exclusiva de monitoreo de spreads y cotizaciones de mercado en tiempo real. Los libros de órdenes y datos contables están protegidos.")

renderer = TAB_RENDERERS.get(selected_panel)
if renderer:
    renderer()
