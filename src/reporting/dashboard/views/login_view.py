"""Vista de autenticación y control de acceso (Obsidian Glassmorphism)."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.data.database import SessionLocal
from src.reporting.dashboard.theme import STITCH_TOKENS
from src.security.auth_service import AuthService


def render_login_view() -> None:
    """Renderiza el formulario de inicio de sesión con estética Glassmorphism."""
    # Contenedor centrado para el formulario de login
    _col1, col2, _col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div class="fintech-card" style="text-align: center; margin-top: 1.5rem;">
                <div style="font-size: 2.2rem; margin-bottom: 0.25rem;">🛡️</div>
                <h2 style="margin: 0; color: {STITCH_TOKENS['text_primary']};">P2P Merchant Bot</h2>
                <p style="color: {STITCH_TOKENS['text_secondary']}; font-size: 0.88rem; margin-top: 0.25rem;">
                    Terminal Operativa & Fiscal — Acceso Autorizado
                </p>
                <div style="margin-top: 0.75rem; display: flex; justify-content: center; gap: 0.5rem;">
                    <span class="badge-pill badge-matched">FAIL-CLOSED</span>
                    <span class="badge-pill" style="background: rgba(6, 182, 212, 0.15); color: #06B6D4; border: 1px solid rgba(6, 182, 212, 0.3);">PBKDF2-SHA256</span>
                    <span class="badge-pill" style="background: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3);">RBAC</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Trader"])

        with login_tab, st.form("login_form", clear_on_submit=False):
            st.markdown(
                f"<div style='color: {STITCH_TOKENS['text_secondary']}; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem;'>Autenticación de Operador</div>",
                unsafe_allow_html=True,
            )
            username = st.text_input("Usuario", placeholder="admin / trader / invitado", autocomplete="username")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••••••", autocomplete="current-password")
            submitted = st.form_submit_button("🔑 Iniciar Sesión", use_container_width=True)

            if submitted:
                if not username.strip() or not password.strip():
                    st.warning("Por favor ingrese usuario y contraseña.")
                else:
                    db = SessionLocal()
                    try:
                        auth = AuthService(db_session=db)
                        auth.ensure_default_admin()
                        user = auth.authenticate_user(username.strip(), password.strip())
                        if user:
                            token = auth.create_session_token(user, secret_key="p2p_bot_merchant_session_key")
                            st.session_state["authenticated"] = True
                            st.session_state["user_id"] = user.id
                            st.session_state["username"] = user.username
                            st.session_state["role"] = user.role
                            st.session_state["session_token"] = token
                            st.success(f"Bienvenido, {user.username} ({user.role}).")
                            st.rerun()
                        else:
                            st.error("⛔ Credenciales inválidas o cuenta desactivada. Contacte al Administrador.")
                    except (SQLAlchemyError, ValueError, RuntimeError, OSError, KeyError) as e:
                        st.error(f"Error durante la autenticación: {e}")
                    finally:
                        db.close()

        with register_tab:
            st.markdown(
                f"<div style='color: {STITCH_TOKENS['text_secondary']}; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem;'>Registro para Nuevos Traders</div>",
                unsafe_allow_html=True,
            )
            with st.form("trader_register_form", clear_on_submit=True):
                new_user = st.text_input("Nombre de Usuario deseado", placeholder="Ej: trader_p2p")
                new_tg = st.text_input("ID o Usuario de Telegram (opcional)", placeholder="Ej: 6326947793 o @usuario")
                new_pass = st.text_input("Contraseña", type="password", placeholder="Mínimo 6 caracteres")
                confirm_pass = st.text_input("Confirmar Contraseña", type="password", placeholder="Repite la contraseña")
                reg_submitted = st.form_submit_button("📝 Solicitar Registro como Trader", use_container_width=True)

                if reg_submitted:
                    if not new_user.strip() or not new_pass.strip():
                        st.warning("Por favor completa el usuario y la contraseña.")
                    elif len(new_pass.strip()) < 6:
                        st.warning("La contraseña debe tener al menos 6 caracteres.")
                    elif new_pass != confirm_pass:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        db = SessionLocal()
                        try:
                            from src.data.repositories import UserRepository
                            repo = UserRepository(db)
                            existing = repo.get_by_username(new_user.strip())
                            if existing:
                                st.error("⚠️ Este nombre de usuario ya está registrado.")
                            else:
                                pass_hash = AuthService.hash_password(new_pass.strip())
                                # Por seguridad, los nuevos traders registrados vía web se crean activos con rol TRADER
                                created = repo.create_user(
                                    username=new_user.strip(),
                                    password_hash=pass_hash,
                                    role="TRADER",
                                    telegram_id=new_tg.strip() if new_tg.strip() else None,
                                    is_active=True,
                                )
                                st.success(f"✅ ¡Cuenta de Trader '{created.username}' creada exitosamente! Ahora puedes iniciar sesión en la pestaña '🔑 Iniciar Sesión'.")
                        except (SQLAlchemyError, ValueError, OSError, RuntimeError) as e:
                            st.error(f"Error registrando cuenta: {e}")
                        finally:
                            db.close()

        with st.expander("ℹ️ Ayuda de acceso"):
            st.markdown(
                """
                - **Administrador**: Acceso maestro predeterminado (`admin`).
                - **Registro de Traders**: Completa la pestaña *📝 Registro de Trader* para crear una cuenta operativa.
                - **Invitados**: Puedes consultar spreads y tasa BCV directamente a través del bot en Telegram.
                """
            )
