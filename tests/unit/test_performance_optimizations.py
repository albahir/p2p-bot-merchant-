"""Pruebas unitarias TDD para optimizaciones de latencia, caché segura y concurrencia en API y SpreadMonitor."""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import Settings
from src.api.deps import get_current_user, invalidate_user_auth_cache
from src.api.routes.auth import register
from src.api.schemas.auth import RegisterRequest
from src.api.security import create_access_token
from src.core.spread_monitor import (
    _ORDERBOOK_CACHE,
    _VOLUME_QUOTES_CACHE,
    BankRateQuote,
    SpreadMonitor,
)
from src.data.database import Base
from src.data.repositories import UserRepository
from src.security.auth_service import AuthService

TEST_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def clear_caches():
    _VOLUME_QUOTES_CACHE.clear()
    _ORDERBOOK_CACHE.clear()
    invalidate_user_auth_cache()
    yield
    _VOLUME_QUOTES_CACHE.clear()
    _ORDERBOOK_CACHE.clear()
    invalidate_user_auth_cache()


def test_spread_monitor_caches_base_quotes_and_avoids_duplicate_pitbull_calls(monkeypatch):
    """Verifica que fetch_live_quotes guarde en caché la consulta base (100 USDT) y no repita llamadas HTTP."""
    monitor = SpreadMonitor()
    call_count = 0

    def fake_pitbull(self, exchange="binance", timeout=6.0):
        nonlocal call_count
        call_count += 1
        return [
            BankRateQuote(bank_name="Banesco", buy_rate=1005.0, sell_rate=1015.0, total_ads=20),
            BankRateQuote(bank_name="Mercantil", buy_rate=1004.0, sell_rate=1016.0, total_ads=15),
        ]

    monkeypatch.setattr(SpreadMonitor, "fetch_pitbullchain_quotes", fake_pitbull)

    q1 = monitor.fetch_live_quotes()
    q2 = monitor.fetch_live_quotes()

    assert len(q1) == 2
    assert len(q2) == 2
    assert call_count == 1, f"Se esperaba 1 sola llamada a PitbullChain gracias a la caché base, hubo {call_count}"


def test_fetch_filtered_orderbook_hits_cache_before_yadio_network_call(monkeypatch):
    """Verifica que fetch_filtered_orderbook revise _ORDERBOOK_CACHE antes de invocar fetch_yadio_rate."""
    from src.core.binance_mock import MockBinanceP2PClient

    monitor = SpreadMonitor()
    yadio_calls = 0

    def slow_yadio(self, fiat="VES", timeout=5.0):
        nonlocal yadio_calls
        yadio_calls += 1
        return 1005.0

    monkeypatch.setattr(SpreadMonitor, "fetch_yadio_rate", slow_yadio)
    monkeypatch.setattr(
        "src.core.binance_client.BinanceP2PClient.search_p2p_ads",
        lambda self, **kw: MockBinanceP2PClient().search_p2p_ads(**kw),
    )

    # 1ra llamada (fría)
    res1 = monitor.fetch_filtered_orderbook(amount_usdt=100.0, bank="Banesco", rows=5)
    initial_yadio_calls = yadio_calls
    assert res1["best_buy_price"] > 0

    # 2da llamada (caliente en caché): NO debe volver a llamar a fetch_yadio_rate
    res2 = monitor.fetch_filtered_orderbook(amount_usdt=100.0, bank="Banesco", rows=5)
    assert res2["best_buy_price"] == res1["best_buy_price"]
    assert yadio_calls == initial_yadio_calls, "La llamada en caché caliente NO debe consultar Yadio por red"


def test_get_current_user_short_ttl_cache_and_instant_invalidation_on_revocation():
    """Verifica que get_current_user evite SELECTs repetitivos al cambiar de pestaña pero invalide al instante si se revoca el usuario."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    try:
        settings = Settings(MASTER_ENCRYPTION_KEY=TEST_SECRET, JWT_SECRET_KEY=TEST_SECRET)
        auth_svc = AuthService(db_session=db)
        user = auth_svc.ensure_default_admin(default_username="fast_admin", default_password="Password123!")
        token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role},
            secret_key=settings.jwt_secret,
        )

        select_queries = 0

        def count_selects(conn, cursor, statement, parameters, context, executemany):
            nonlocal select_queries
            if "app_users" in statement.lower() and statement.strip().upper().startswith("SELECT"):
                select_queries += 1

        event.listen(engine, "before_cursor_execute", count_selects)

        # Primera resolución carga de BD y guarda en caché
        u1 = get_current_user(token=token, db=db, settings=settings)
        assert u1.username == "fast_admin"
        assert select_queries == 1

        # Segunda y tercera resolución (simulando cambio rápido de pestañas) usan caché con 0 SELECTs adicionales
        u2 = get_current_user(token=token, db=db, settings=settings)
        u3 = get_current_user(token=token, db=db, settings=settings)
        assert u2.id == u1.id and u3.id == u1.id
        assert select_queries == 1, f"Se esperaba 1 solo SELECT a app_users, hubo {select_queries}"

        # Si el administrador suspende la cuenta (Fail-closed), la caché se invalida de inmediato
        repo = UserRepository(db)
        repo.set_active_status(int(user.id), False)

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token, db=db, settings=settings)
        assert exc_info.value.status_code == 403
    finally:
        db.close()


def test_register_dispatches_telegram_alert_asynchronously_without_blocking():
    """Verifica que POST /api/auth/register utilice envío asíncrono a Telegram sin bloquear por 13s la petición HTTP."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        settings = Settings(MASTER_ENCRYPTION_KEY=TEST_SECRET, JWT_SECRET_KEY=TEST_SECRET)

        def slow_sync_send(*args, **kwargs):
            time.sleep(5.0)
            return True

        mock_async = MagicMock(return_value=True)
        with (
            patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", side_effect=slow_sync_send),
            patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert_async", mock_async),
        ):
            t0 = time.perf_counter()
            resp = register(
                req=RegisterRequest(username="instant_user", password="StrongPassword123!"),
                db=db,
                settings=settings,
            )
            elapsed = time.perf_counter() - t0

        assert resp.user.username == "instant_user"
        assert mock_async.called, "register debe usar send_alert_async para no bloquear el hilo HTTP"
        assert elapsed < 1.5, f"El registro tardó demasiado ({elapsed:.2f}s)"
    finally:
        db.close()


def test_login_immediately_hydrates_existing_google_sheets_connection():
    """Verifica que al iniciar sesión (POST /api/auth/login), la respuesta incluya de inmediato
    el estado real de conexión a Google Sheets (google_sheet_configured, google_auth_type,
    google_oauth_connected y google_account_email) sin esperar a abrir /sheets.
    """
    from src.api.routes.auth import login
    from src.api.schemas.auth import LoginRequest

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        settings = Settings(MASTER_ENCRYPTION_KEY=TEST_SECRET, JWT_SECRET_KEY=TEST_SECRET)
        auth_svc = AuthService(db_session=db)
        user = auth_svc.ensure_default_admin(
            default_username="sheets_trader", default_password="Password123!"
        )
        user.google_sheet_id = "1AbCdEfGhIjKlMnOpQrStUvWxYz"  # type: ignore[assignment]
        user.google_auth_type = "OAUTH2"  # type: ignore[assignment]
        user.google_refresh_token_enc = "vault:trader@gmail.com"  # type: ignore[assignment]
        db.commit()

        res = login(
            req=LoginRequest(username="sheets_trader", password="Password123!"),
            db=db,
            settings=settings,
        )
        assert res.user.google_sheet_id == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
        assert res.user.google_sheet_configured is True
        assert res.user.google_auth_type == "OAUTH2"
        assert res.user.google_oauth_connected is True
        assert res.user.google_account_email == "trader@gmail.com"
    finally:
        db.close()


def test_recover_password_relays_otp_via_shared_db_to_render_bot_and_resets() -> None:
    """
    Si la red local en Venezuela sufre timeout hacia Telegram, recover_password persiste
    el OTP en SystemState (BD compartida con Render), lo encola en tg_outbox:<user>,
    el Bot en Render lo despacha vía flush_db_outbox() y reset_password valida desde la BD.
    """
    from typing import Any

    from src.api.routes.auth import (
        _RECOVERY_CODES,
        load_shared_recovery_otp,
        recover_password,
        reset_password,
    )
    from src.api.schemas.auth import PasswordRecoveryRequest, PasswordResetRequest
    from src.integrations.telegram_notifier import TelegramNotifier

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        auth_svc = AuthService(db_session=db)
        user = auth_svc.ensure_default_admin(
            default_username="tg_render_user", default_password="OldPassword123!"
        )
        user.telegram_id = "123456789"  # type: ignore[assignment]
        db.commit()

        # 1. En la PC local (Venezuela), send_alert directo da timeout
        def local_blocked_send_alert(self: Any, text: str, chat_id: str | None = None, **kwargs: Any) -> bool:
            self.last_error = "Error de conectividad con Telegram (timed out)"
            return False

        with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", local_blocked_send_alert):
            res = recover_password(
                req=PasswordRecoveryRequest(username="tg_render_user"),
                db=db,
            )

        assert res["success"] is True
        assert res["has_telegram"] is True
        assert res.get("relayed_via_render") is True

        # 2. El Bot en Render lee tg_outbox desde la misma BD y lo envía a Telegram sin bloqueo
        dispatched_messages: list[tuple[str, str | None]] = []

        def render_cloud_send_alert(self: Any, text: str, chat_id: str | None = None, **kwargs: Any) -> bool:
            dispatched_messages.append((text, chat_id))
            return True

        render_notifier = TelegramNotifier(
            bot_token="123456:ABCDEF",
            default_chat_id="123456789",
            session_factory=session_factory,
        )
        with patch.object(TelegramNotifier, "send_alert", render_cloud_send_alert):
            sent_count = render_notifier.flush_db_outbox(db)

        assert sent_count == 1
        assert len(dispatched_messages) == 1
        assert dispatched_messages[0][1] == "123456789"

        # 3. Incluso si la memoria local _RECOVERY_CODES se vacía, reset_password valida el hash desde la BD compartida
        import re

        _RECOVERY_CODES.clear()
        shared_record = load_shared_recovery_otp(db, "tg_render_user")
        assert shared_record is not None
        assert "code_hash" in shared_record
        otp_match = re.search(r"(\d{6})", dispatched_messages[0][0])
        assert otp_match is not None
        otp_code = otp_match.group(1)

        reset_res = reset_password(
            req=PasswordResetRequest(
                username="tg_render_user",
                reset_code=otp_code,
                new_password="NewPassword456!",
                method="telegram_otp",
            ),
            db=db,
        )
        assert reset_res["success"] is True
        assert auth_svc.authenticate("tg_render_user", "NewPassword456!") is not None
    finally:
        db.close()


def test_otp_is_stored_hashed_and_brute_force_locks_account_after_5_attempts() -> None:
    """
    El OTP debe almacenarse hasheado (nunca en texto plano) en SystemState y
    5 intentos fallidos de OTP deben incrementar failed_recovery_attempts y bloquear
    la cuenta por 15 minutos (HTTP 429) impidiendo pedir nuevos OTPs.
    """
    import pytest
    from fastapi import HTTPException

    from src.api.routes.auth import recover_password, reset_password
    from src.api.schemas.auth import PasswordRecoveryRequest, PasswordResetRequest
    from src.data.models import SystemState

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        auth_svc = AuthService(db_session=db)
        user = auth_svc.ensure_default_admin(
            default_username="brute_user", default_password="Password123!"
        )
        user.telegram_id = "987654321"  # type: ignore[assignment]
        db.commit()

        with patch("src.integrations.telegram_notifier.TelegramNotifier.send_alert", return_value=True):
            recover_password(req=PasswordRecoveryRequest(username="brute_user"), db=db)

        # Verificar que en SystemState no existe el OTP en claro, sino su hash SHA-256/HMAC
        row = db.query(SystemState).filter(SystemState.key == "recovery_otp:brute_user").first()
        assert row is not None
        assert '"h":' in str(row.value)
        assert '"c":' not in str(row.value)

        # Simular 4 intentos fallidos -> HTTP 400 y contador incrementa
        for _ in range(4):
            with pytest.raises(HTTPException) as exc_info:
                reset_password(
                    req=PasswordResetRequest(
                        username="brute_user",
                        reset_code="000000",
                        new_password="NewPassword123!",
                        method="telegram_otp",
                    ),
                    db=db,
                )
            assert exc_info.value.status_code == 400

        # 5to intento fallido -> HTTP 429 y bloqueo de 15 minutos
        with pytest.raises(HTTPException) as lock_exc:
            reset_password(
                req=PasswordResetRequest(
                    username="brute_user",
                    reset_code="000000",
                    new_password="NewPassword123!",
                    method="telegram_otp",
                ),
                db=db,
            )
        assert lock_exc.value.status_code == 429

        # Mientras esté bloqueado, no debe permitir solicitar un nuevo OTP
        with pytest.raises(HTTPException) as req_lock_exc:
            recover_password(req=PasswordRecoveryRequest(username="brute_user"), db=db)
        assert req_lock_exc.value.status_code == 429
    finally:
        db.close()


def test_telegram_bot_info_endpoint_and_id_command() -> None:
    """
    Verifica que GET /api/auth/telegram-bot-info devuelva el @username y enlace https://t.me/<bot>?start=id
    sin filtrar el token, y que /id en el bot devuelva el ID numérico para cualquier usuario.
    """
    import json

    from src.api.routes.auth import get_telegram_bot_info
    from src.data.models import SystemState
    from src.integrations.telegram_notifier import TelegramNotifier

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        # Simular perfil de bot publicado en SystemState por el bot de Render
        db.add(
            SystemState(
                key="telegram_bot_profile",
                value=json.dumps({"username": "P2P_Merchant_VE_bot", "first_name": "P2P Merchant Bot"}),
            )
        )
        db.commit()

        settings = Settings(MASTER_ENCRYPTION_KEY=TEST_SECRET, JWT_SECRET_KEY=TEST_SECRET)
        info = get_telegram_bot_info(db=db, settings=settings)

        assert info["available"] is True
        assert info["bot_username"] == "P2P_Merchant_VE_bot"
        assert info["bot_mention"] == "@P2P_Merchant_VE_bot"
        assert info["bot_url"] == "https://t.me/P2P_Merchant_VE_bot?start=id"
        assert "123456" not in str(info)

        # Verificar que el comando /id funcione incluso para un Invitado recién registrado
        notifier = TelegramNotifier(
            bot_token="123456:fake",
            default_chat_id="999",
            session_factory=sessionmaker(autocommit=False, autoflush=False, bind=engine),
        )
        auth_svc = AuthService(db_session=db)
        guest = auth_svc.ensure_default_admin(default_username="guest_id", default_password="Password123!")
        guest.role = "INVITADO"  # type: ignore[assignment]
        guest.telegram_id = "771122334"  # type: ignore[assignment]
        db.commit()

        reply = notifier.handle_command(user_id="771122334", command="/id")
        assert "771122334" in reply
    finally:
        db.close()


def test_telegram_notifier_respects_custom_api_base_url_from_settings() -> None:
    """
    TelegramNotifier() sin argumentos debe cargar TELEGRAM_API_BASE_URL desde Settings
    (ej. el Cloudflare Worker proxy https://p2p-telegram-proxy.*.workers.dev) en lugar de
    pisarlo con el default truthy 'https://api.telegram.org'.
    """
    from src.integrations.telegram_notifier import TelegramNotifier

    fake_settings = Settings(
        MASTER_ENCRYPTION_KEY=TEST_SECRET,
        JWT_SECRET_KEY=TEST_SECRET,
        TELEGRAM_BOT_TOKEN="123456:ABCDEF",
        TELEGRAM_ALERT_CHAT_ID="999999",
        TELEGRAM_API_BASE_URL="https://p2p-telegram-proxy.m17m5franc.workers.dev/",
    )
    with patch("config.settings.Settings", return_value=fake_settings):
        notifier = TelegramNotifier()
        assert notifier.api_base_url == "https://p2p-telegram-proxy.m17m5franc.workers.dev"
        assert notifier.base_url.startswith(
            "https://p2p-telegram-proxy.m17m5franc.workers.dev/bot"
        )


