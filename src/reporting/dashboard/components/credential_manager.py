"""Componente para gestión visual de credenciales cifradas con AES-256-GCM."""

import streamlit as st

from config.settings import Settings
from src.data.database import SessionLocal
from src.data.models import EncryptedSecret
from src.security.api_key_manager import ApiKeyManager
from src.security.audit_logger import AuditLogger


def render_credential_manager():
    """Formulario seguro para configurar y almacenar claves cifradas sin mostrarlas en texto plano."""
    st.subheader(":material/key: Gestor de Credenciales Cifradas")
    st.caption("Las claves se cifran en memoria con **AES-256-GCM** antes de guardarse en la base de datos.")

    try:
        settings = Settings()
        audit = AuditLogger(SessionLocal)
        manager = ApiKeyManager(
            master_key=settings.MASTER_ENCRYPTION_KEY,
            audit_logger=audit,
            db_session_factory=SessionLocal
        )
    except (ValueError, ImportError) as e:
        st.error(f"Error cargando gestor de claves: {e}")
        return

    # Verificar qué claves ya están configuradas
    db = SessionLocal()
    has_binance_key = db.query(EncryptedSecret).filter_by(key_name="binance_api_key").first() is not None
    has_binance_priv = db.query(EncryptedSecret).filter_by(key_name="binance_private_key").first() is not None
    db.close()

    # Estado visual de credenciales
    col1, col2, col3 = st.columns(3)
    with col1, st.container(border=True):
        st.markdown("**Binance API Key**")
        if has_binance_key:
            st.badge("Configurada", icon=":material/check_circle:")
        else:
            st.badge("Pendiente", icon=":material/warning:")
    with col2, st.container(border=True):
        st.markdown("**Binance Private Key (Ed25519)**")
        if has_binance_priv:
            st.badge("Configurada", icon=":material/check_circle:")
        else:
            st.badge("Pendiente", icon=":material/warning:")
    with col3, st.container(border=True):
        st.markdown("**Telegram Bot Token**")
        if settings.TELEGRAM_BOT_TOKEN:
            st.badge("Configurado", icon=":material/check_circle:")
        else:
            st.badge("Pendiente", icon=":material/warning:")

    st.write("---")

    # Formulario de registro/actualización de credenciales
    with st.form("form_credentials", clear_on_submit=True):
        st.markdown("#### Actualizar Credenciales de Binance")
        new_api_key = st.text_input(
            "Binance API Key",
            type="password",
            placeholder="Pega tu API Key de Binance P2P",
            help="Permisos mínimos requeridos: Reading + P2P Trading."
        )
        new_private_key = st.text_area(
            "Binance Private Key (Ed25519 PEM)",
            placeholder="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
            help="Clave privada Ed25519 generada en Binance para firmar peticiones."
        )

        st.markdown("#### Configuración de Telegram")
        new_tg_token = st.text_input(
            "Telegram Bot Token",
            type="password",
            placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
            help="Token provisto por @BotFather."
        )

        submitted = st.form_submit_button("Guardar Credenciales Cifradas", width="stretch")

        if submitted:
            saved_any = False
            from src.security.key_validator import KeyValidationError, KeyValidator

            if new_api_key.strip():
                try:
                    valid_key = KeyValidator.validate_api_key(new_api_key)
                    manager.store_secret("binance_api_key", valid_key)
                    saved_any = True
                except KeyValidationError as e:
                    st.error(f"Error en API Key: {e}")
                    return

            if new_private_key.strip():
                try:
                    valid_pem = KeyValidator.validate_private_key_pem(new_private_key)
                    manager.store_secret("binance_private_key", valid_pem)
                    saved_any = True
                except KeyValidationError as e:
                    st.error(f"Error en Clave Privada PEM: {e}")
                    return

            if new_tg_token.strip():
                import re
                from pathlib import Path
                env_path = Path("config/.env")
                if env_path.exists():
                    content = env_path.read_text(encoding="utf-8")
                    updated = re.sub(r"TELEGRAM_BOT_TOKEN=.*", f"TELEGRAM_BOT_TOKEN={new_tg_token.strip()}", content)
                    env_path.write_text(updated, encoding="utf-8")
                    saved_any = True

            if saved_any:
                st.success("Credenciales validadas, cifradas y guardadas exitosamente.")
                st.rerun()
            else:
                st.warning("No ingresaste ninguna clave para guardar.")
