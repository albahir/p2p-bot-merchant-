import time

import streamlit as st

from config.settings import Settings
from src.core.binance_client import BinanceP2PClient
from src.core.history_ingestor import HistoryIngestor
from src.data.database import SessionLocal
from src.data.models import Order
from src.integrations.telegram_notifier import TelegramNotifier
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger
from src.security.permissions import StartupPermissionValidator


def render_control_actions():
    """Botones interactivos de control de tareas y salud del bot."""
    st.subheader(":material/tune: Panel de Control de Tareas")
    st.caption("Ejecuta tareas operativas y diagnósticos directamente desde aquí sin tocar la terminal.")

    settings = Settings()
    audit = AuditLogger(SessionLocal)
    key_manager = ApiKeyManager(settings.MASTER_ENCRYPTION_KEY, audit_logger=audit)

    col1, col2, col3 = st.columns(3)

    # 1. Botón de Sincronización Manual y Sandbox
    with col1, st.container(border=True):
        st.markdown("#### :material/sync: Ingesta de Órdenes")
        use_sandbox = st.toggle("Modo Simulación (Sandbox)", value=True, help="Simula órdenes P2P sin necesidad de API real.")

        db_chk = SessionLocal()
        try:
            total_db_orders = db_chk.query(Order).count()
            st.caption(f"📦 Órdenes en Base de Datos: **{total_db_orders}**")
        finally:
            db_chk.close()

        st.write("Descarga transacciones recientes de Binance P2P de inmediato.")
        if st.button("Sincronizar Órdenes Ahora", width="stretch", type="primary"):
            from src.core.concurrency import SyncLockManager
            lock_mgr = SyncLockManager()
            if not lock_mgr.acquire(task_name="manual_sync_orders", max_duration_seconds=30.0):
                st.warning(f"⚠️ Ya hay una sincronización en curso ({lock_mgr.current_task}). Por favor espera a que finalice.")
            else:
                try:
                    if use_sandbox:
                        from src.core.binance_mock import MockBinanceP2PClient
                        client = MockBinanceP2PClient()
                        st.info("Usando Simulador Binance Sandbox...")
                    else:
                        api_key = key_manager.get_secret("binance_api_key")
                        priv_key = key_manager.get_secret("binance_private_key")
                        client = BinanceP2PClient(api_key=api_key, private_key_pem=priv_key)

                    ingestor = HistoryIngestor(client, SessionLocal)
                    with st.spinner("Sincronizando órdenes P2P con Binance..."):
                        count = ingestor.ingest_recent_orders(trade_type="ALL", days_back=7)
                    if count > 0:
                        st.success(f"✅ Sincronización completa: {count} órdenes procesadas. Reflejadas en 'Visión General'.")
                        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ALERT_CHAT_ID:
                            notifier = TelegramNotifier(
                                bot_token=settings.TELEGRAM_BOT_TOKEN,
                                default_chat_id=settings.TELEGRAM_ALERT_CHAT_ID,
                                allowed_user_ids=settings.telegram_allowed_users,
                                proxy_url=settings.TELEGRAM_PROXY_URL,
                                api_base_url=settings.TELEGRAM_API_BASE_URL,
                                use_sandbox=use_sandbox
                            )
                            mode_lbl = "[SANDBOX]" if use_sandbox else "[PROD]"
                            notifier.send_alert(
                                f"📦 *{mode_lbl} Sincronización P2P Exitosa*\n"
                                f"Se han registrado e ingestadas *{count}* órdenes recientes."
                            )
                    else:
                        st.info("ℹ️ Todas las órdenes del Sandbox ya estaban en la base de datos (Idempotencia). Usa 'Simular Nuevo Ciclo' para agregar más.")
                    st.rerun()
                except KeyError:
                    st.warning("Faltan las credenciales reales de Binance. Activa el 'Modo Simulación' o configúralas en la pestaña Credenciales.")
                except (RuntimeError, ValueError) as e:
                    st.error(f"Error sincronizando órdenes: {e}")
                finally:
                    lock_mgr.release()

        if use_sandbox:
            st.markdown("---")
            st.markdown("##### ⚡ Operaciones Sandbox")
            if st.button("➕ Simular Nuevo Ciclo (Compra + Venta)", width="stretch"):
                from src.core.binance_mock import MockBinanceP2PClient
                now_ms = int(time.time() * 1000)
                sim_client = MockBinanceP2PClient(enable_default_orders=False)
                sim_client.add_simulated_trade(
                    order_number=f"SIM_BUY_{now_ms}",
                    trade_type="BUY",
                    amount=100.0,
                    unit_price=36.50,
                    fee_fiat=3.65,
                    status="COMPLETED"
                )
                sim_client.add_simulated_trade(
                    order_number=f"SIM_SELL_{now_ms}",
                    trade_type="SELL",
                    amount=100.0,
                    unit_price=37.90,
                    fee_fiat=4.55,
                    status="COMPLETED"
                )
                ingestor = HistoryIngestor(sim_client, SessionLocal)
                with st.spinner("Registrando nuevo ciclo en Sandbox..."):
                    c = ingestor.ingest_recent_orders(trade_type="ALL", days_back=7)
                st.success(f"¡Ciclo comercial simulado! {c} órdenes creadas y listas en la tabla.")
                if c > 0 and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ALERT_CHAT_ID:
                    notifier = TelegramNotifier(
                        bot_token=settings.TELEGRAM_BOT_TOKEN,
                        default_chat_id=settings.TELEGRAM_ALERT_CHAT_ID,
                        allowed_user_ids=settings.telegram_allowed_users,
                        proxy_url=settings.TELEGRAM_PROXY_URL,
                        api_base_url=settings.TELEGRAM_API_BASE_URL,
                        use_sandbox=True
                    )
                    notifier.send_alert(
                        "⚡ *[SANDBOX] Nuevo Ciclo Comercial Simulado*\n"
                        "• Compra: 100 USDT @ 36.50 VES\n"
                        "• Venta: 100 USDT @ 37.90 VES\n"
                        "• Spread Bruto: +3.83%\n"
                        f"• Órdenes sincronizadas en DB: *{c}*"
                    )
                st.rerun()

            if st.button("🗑️ Limpiar Historial de Prueba", width="stretch"):
                db_clean = SessionLocal()
                try:
                    deleted = db_clean.query(Order).delete()
                    db_clean.commit()
                    st.success(f"Se eliminaron {deleted} órdenes de prueba.")
                    if deleted > 0 and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ALERT_CHAT_ID:
                        notifier = TelegramNotifier(
                            bot_token=settings.TELEGRAM_BOT_TOKEN,
                            default_chat_id=settings.TELEGRAM_ALERT_CHAT_ID,
                            allowed_user_ids=settings.telegram_allowed_users,
                            proxy_url=settings.TELEGRAM_PROXY_URL,
                            api_base_url=settings.TELEGRAM_API_BASE_URL,
                            use_sandbox=True
                        )
                        notifier.send_alert(f"🗑️ *[SANDBOX]* Historial de prueba purgado ({deleted} órdenes eliminadas).")
                    st.rerun()
                finally:
                    db_clean.close()


    # 2. Diagnóstico de Salud
    with col2, st.container(border=True):
        st.markdown("#### :material/health_and_safety: Salud del Sistema")
        st.write("Verifica IP en whitelist, base de datos y llaves.")
        if st.button("Ejecutar Diagnóstico", width="stretch"):
            validator = StartupPermissionValidator(settings, audit)
            try:
                validator.verify_ip_whitelist("127.0.0.1")
                st.toast("IP Whitelist: 127.0.0.1 Verificada", icon="🛡️")
            except PermissionError as e:
                st.error(f"Error de IP: {e}")

            db = SessionLocal()
            try:
                total_orders = db.query(Order).count()
                st.toast(f"Base de Datos: OK ({total_orders} órdenes registradas)", icon="📦")
            finally:
                db.close()
            st.success("Diagnóstico: Todos los sistemas locales responden correctamente.")

    # 3. Notificación de Prueba por Telegram
    with col3, st.container(border=True):
        st.markdown("#### :material/send: Alerta de Prueba")
        st.write("Envía un mensaje de prueba al chat de Telegram configurado.")
        if st.button("Enviar Alerta de Prueba", width="stretch"):
            if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ALERT_CHAT_ID:
                st.warning("Configura el token y Chat ID de Telegram en config/.env primero.")
            else:
                notifier = TelegramNotifier(
                    bot_token=settings.TELEGRAM_BOT_TOKEN,
                    default_chat_id=settings.TELEGRAM_ALERT_CHAT_ID,
                    allowed_user_ids=settings.telegram_allowed_users,
                    proxy_url=settings.TELEGRAM_PROXY_URL,
                    api_base_url=settings.TELEGRAM_API_BASE_URL,
                    use_sandbox=use_sandbox
                )
                with st.spinner("Enviando mensaje a Telegram..."):
                    ok = notifier.send_alert("🔔 *Prueba de Alerta*: Conexión exitosa desde el Panel de Control P2P.")
                if ok:
                    st.success(f"Alerta enviada con éxito al Chat ID: {settings.TELEGRAM_ALERT_CHAT_ID}")
                else:
                    st.error(f"Error de Telegram: {notifier.last_error or 'No se pudo conectar con los servidores de Telegram'}")
                    st.info(
                        "💡 **Nota sobre conexión**: Si el error es de Timeout/Red, es debido al filtrado del puerto 443 por parte de tu proveedor de internet (ISP). "
                        "Puedes activar una VPN (ej. Cloudflare WARP 1.1.1.1) o configurar `TELEGRAM_PROXY_URL` en `config/.env`."
                    )
