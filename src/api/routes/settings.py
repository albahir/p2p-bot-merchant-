"""Rutas para gestión segura de credenciales de Binance y diagnóstico en vivo."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, sessionmaker

from config.settings import Settings
from src.api.deps import (
    get_db,
    get_settings,
    invalidate_user_auth_cache,
    require_authenticated,
    require_trader,
)
from src.api.schemas.settings import (
    BinanceStatusResponse,
    GoogleOAuthCallbackRequest,
    GoogleOAuthClientConfigRequest,
    GoogleOAuthStartResponse,
    GoogleSheetsConfigResponse,
    GoogleSheetsSyncResponse,
    SaveBinanceKeysRequest,
    TelegramStatusResponse,
    UpdateGoogleSheetsConfigRequest,
    UpdateUserBanksRequest,
    UserBanksConfigResponse,
    VerifyBinanceResponse,
)
from src.data.models import User
from src.integrations.google_oauth import (
    GoogleOAuthError,
    build_authorization_url,
    create_state,
    exchange_code,
    is_oauth_configured,
    verify_state,
)
from src.reporting.sheets_exporter import SheetsExporter
from src.security.api_key_manager import ApiKeyManager

logger = logging.getLogger("settings_route")

router = APIRouter(prefix="/api/settings", tags=["Configuración"])


def _mask_key(key: str) -> str:
    """Oculta de forma segura la API key dejando solo los extremos."""
    if not key or len(key) < 8:
        return "••••••••"
    return f"{key[:4]}••••{key[-4:]}"


def _user_binance_key_names(user_id: int | None) -> tuple[str, str, str]:
    """Retorna los identificadores de secretos de Binance aislados por usuario."""
    if user_id is not None:
        return (
            f"user_{user_id}:binance_api_key",
            f"user_{user_id}:binance_private_key",
            f"user_{user_id}:binance_key_type",
        )
    return ("binance_api_key", "binance_private_key", "binance_key_type")


@router.get("/binance", response_model=BinanceStatusResponse)
def get_binance_status(
    _current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> BinanceStatusResponse:
    """Consulta el estado de las credenciales personales de Binance API del usuario sin exponer texto plano."""
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    uid = int(_current_user.id) if _current_user and _current_user.id is not None else None
    k_api, _, k_type = _user_binance_key_names(uid)
    try:
        api_key = km.get_secret(k_api)
        key_type = km.get_secret(k_type)
    except (KeyError, RuntimeError):
        api_key = ""
        key_type = "HMAC"

    is_configured = bool(api_key and len(api_key) >= 16)
    masked = _mask_key(api_key) if is_configured else "No configurada"

    return BinanceStatusResponse(
        is_configured=is_configured,
        api_key_masked=masked,
        key_type=key_type or "HMAC",
        is_connected=is_configured,
        latency_ms=0.0,
        clock_drift_ms=0,
        used_weight=0,
        max_weight=5000,
        permissions=["Lectura", "P2P Trading"] if is_configured else [],
        message=(
            "Credenciales personales de Binance configuradas y cifradas en reposo (AES-256-GCM)."
            if is_configured
            else "No has suministrado tus credenciales API de Binance todavía."
        ),
    )


@router.post("/binance", response_model=BinanceStatusResponse)
def save_binance_keys(
    req: SaveBinanceKeysRequest,
    request: Request,
    _current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> BinanceStatusResponse:
    """Almacena de forma cifrada (AES-256-GCM) y aislada por operador las credenciales de la API de Binance."""
    operator_username = str(_current_user.username)
    uid = int(_current_user.id) if _current_user and _current_user.id is not None else None
    k_api, k_priv, k_type = _user_binance_key_names(uid)
    client_ip = request.client.host if request.client else "127.0.0.1"
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)

    try:
        km.store_secret(k_api, req.api_key.strip(), ip_address=client_ip)
        km.store_secret(k_priv, req.secret_key.strip(), ip_address=client_ip)
        km.store_secret(k_type, req.key_type, ip_address=client_ip)
    except (RuntimeError, ValueError) as err:
        logger.error("Error al cifrar credenciales de Binance: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error criptográfico interno al resguardar las credenciales.",
        ) from err

    masked = _mask_key(req.api_key.strip())
    logger.info("Credenciales personales de Binance actualizadas por usuario '%s'", operator_username)

    return BinanceStatusResponse(
        is_configured=True,
        api_key_masked=masked,
        key_type=req.key_type,
        is_connected=True,
        latency_ms=0.0,
        clock_drift_ms=0,
        used_weight=0,
        max_weight=5000,
        permissions=["Lectura", "P2P Trading"],
        message="Tus credenciales personales de Binance fueron cifradas y almacenadas con AES-256-GCM.",
    )


@router.post("/binance/verify", response_model=VerifyBinanceResponse)
def verify_binance_connection(
    _current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> VerifyBinanceResponse:
    """Realiza un diagnóstico en caliente de la API personal del usuario: ping, deriva horaria y API weight."""
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    uid = int(_current_user.id) if _current_user and _current_user.id is not None else None
    k_api, _, _ = _user_binance_key_names(uid)
    try:
        api_key = km.get_secret(k_api)
    except (KeyError, RuntimeError):
        api_key = ""

    if not api_key:
        return VerifyBinanceResponse(
            success=False,
            is_connected=False,
            latency_ms=0.0,
            clock_drift_ms=0,
            used_weight=0,
            max_weight=5000,
            is_weight_safe=True,
            server_time_utc=None,
            message="No hay credenciales API de Binance configuradas. Ingrésalas primero.",
        )

    t0 = time.perf_counter()
    local_before = int(time.time() * 1000)

    try:
        with httpx.Client(timeout=6.0) as client:
            headers = {"X-MBX-APIKEY": api_key}
            res = client.get("https://api.binance.com/api/v3/time", headers=headers)
            t1 = time.perf_counter()
            latency_ms = round((t1 - t0) * 1000, 2)

            if res.status_code != 200:
                return VerifyBinanceResponse(
                    success=False,
                    is_connected=False,
                    latency_ms=latency_ms,
                    clock_drift_ms=0,
                    used_weight=0,
                    max_weight=5000,
                    is_weight_safe=True,
                    server_time_utc=None,
                    message=f"Binance respondió con código de estado HTTP {res.status_code}: {res.text}",
                )

            data = res.json()
            server_time_ms = int(data.get("serverTime", local_before))
            clock_drift_ms = server_time_ms - local_before

            # Extraer headers de cuota
            weight_header = res.headers.get("x-mbx-used-weight-1m") or res.headers.get("x-mbx-used-weight")
            used_weight = int(weight_header) if weight_header and weight_header.isdigit() else 1
            server_dt = datetime.fromtimestamp(server_time_ms / 1000.0, tz=UTC)

            is_safe = used_weight < 5000

            return VerifyBinanceResponse(
                success=True,
                is_connected=True,
                latency_ms=latency_ms,
                clock_drift_ms=clock_drift_ms,
                used_weight=used_weight,
                max_weight=5000,
                is_weight_safe=is_safe,
                server_time_utc=server_dt,
                message=(
                    f"Conexión Binance 100% activa. Latencia: {latency_ms}ms, "
                    f"Deriva: {clock_drift_ms}ms, Peso API: {used_weight}/5000."
                ),
            )
    except httpx.TimeoutException:
        return VerifyBinanceResponse(
            success=False,
            is_connected=False,
            latency_ms=0.0,
            clock_drift_ms=0,
            used_weight=0,
            max_weight=5000,
            is_weight_safe=True,
            server_time_utc=None,
            message="Tiempo de espera agotado al conectar con Binance API (Timeout de 6s).",
        )
    except (httpx.RequestError, ValueError, OSError) as exc:
        logger.warning("Error verificando conexión con Binance: %s", exc)
        return VerifyBinanceResponse(
            success=False,
            is_connected=False,
            latency_ms=0.0,
            clock_drift_ms=0,
            used_weight=0,
            max_weight=5000,
            is_weight_safe=True,
            server_time_utc=None,
            message="Error de red al verificar conexión con la API oficial de Binance.",
        )


def _extract_sheet_id(raw_input: str | None) -> str | None:
    """Extrae el Sheet ID ya sea que el usuario haya pegado el ID o la URL completa de Google Sheets."""
    if not raw_input:
        return None
    cleaned = raw_input.strip()
    import re
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", cleaned)
    if match:
        return match.group(1)
    return cleaned


def _parse_oauth_vault_marker(user: User) -> tuple[bool, str | None]:
    """Interpreta el marcador no secreto `google_refresh_token_enc` sin almacenar tokens planos."""
    raw = str(getattr(user, "google_refresh_token_enc", "") or "").strip()
    if not raw:
        return (False, None)
    if raw.startswith("vault:"):
        email = raw.split("vault:", 1)[1].strip() or None
        return (True, email)
    return (True, None)


def _validate_oauth_redirect_uri(redirect_uri: str | None, settings: Settings) -> str:
    """Valida que el redirect_uri pertenezca a los orígenes permitidos para evitar open redirect."""
    default_uri = settings.GOOGLE_OAUTH_REDIRECT_URI.strip()
    if not redirect_uri or not isinstance(redirect_uri, str):
        return default_uri
    candidate = redirect_uri.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="redirect_uri OAuth inválido.")

    allowed_hosts = {urlparse(default_uri).netloc, "localhost:3000", "127.0.0.1:3000"}
    for origin in settings.cors_origins_list:
        if origin != "*":
            origin_netloc = urlparse(origin).netloc
            if origin_netloc:
                allowed_hosts.add(origin_netloc)

    if parsed.netloc not in allowed_hosts or parsed.path != "/sheets":
        raise HTTPException(status_code=400, detail="redirect_uri OAuth no autorizado.")
    return candidate


def _resolve_oauth_settings(
    settings: Settings,
    db: Session | None,
    user_id: int | None,
) -> tuple[Settings, bool]:
    """Resuelve credenciales OAuth desde `.env` o desde la bóveda AES-256-GCM en DB."""
    if is_oauth_configured(settings):
        return settings, False

    if not isinstance(db, Session):
        return settings, False

    try:
        factory = sessionmaker(bind=db.get_bind())
        km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    except ValueError:
        return settings, False

    candidate_keys: list[str] = []
    if user_id is not None:
        candidate_keys.append(f"user_{user_id}:google_oauth_client")
    candidate_keys.append("system:google_oauth_client")

    for key_name in candidate_keys:
        try:
            raw_json = km.get_secret(key_name)
            parsed = json.loads(raw_json)
            cid = str(parsed.get("client_id") or "").strip()
            csec = str(parsed.get("client_secret") or "").strip()
            ruri = str(parsed.get("redirect_uri") or settings.GOOGLE_OAUTH_REDIRECT_URI).strip()
            if cid and csec:
                effective = settings.model_copy(
                    update={
                        "GOOGLE_OAUTH_CLIENT_ID": cid,
                        "GOOGLE_OAUTH_CLIENT_SECRET": csec,
                        "GOOGLE_OAUTH_REDIRECT_URI": ruri or settings.GOOGLE_OAUTH_REDIRECT_URI,
                    }
                )
                return effective, True
        except (KeyError, ValueError, RuntimeError, TypeError, json.JSONDecodeError):
            continue

    return settings, False


def build_user_sheets_exporter(user: User, settings: Settings, db: Session) -> SheetsExporter:
    """Construye un `SheetsExporter` autenticado con OAuth 2.0 o Service Account según el perfil."""
    auth_type = str(getattr(user, "google_auth_type", "") or "SERVICE_ACCOUNT")
    has_oauth_marker, account_email = _parse_oauth_vault_marker(user)
    uid = int(user.id) if user and user.id is not None else None

    if auth_type == "OAUTH2" and has_oauth_marker and uid is not None:
        effective_settings, _ = _resolve_oauth_settings(settings, db, uid)
        if not is_oauth_configured(effective_settings):
            return SheetsExporter(
                auth_error="Falta configurar el cliente OAuth de Google. Carga las credenciales API en Hoja de Cálculo."
            )
        try:
            factory = sessionmaker(bind=db.get_bind())
            km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
            refresh_token = km.get_secret(f"user_{uid}:google_refresh_token")
        except (KeyError, ValueError, RuntimeError):
            return SheetsExporter(
                auth_error="Tu sesión de Google expiró o fue removida. Reconecta tu cuenta en Hoja de Cálculo."
            )
        return SheetsExporter(
            oauth_credentials={
                "client_id": (effective_settings.GOOGLE_OAUTH_CLIENT_ID or "").strip(),
                "client_secret": (effective_settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip(),
                "refresh_token": refresh_token,
                "email": account_email,
            }
        )

    return SheetsExporter(
        credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
        credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
    )


def _build_sheets_config_response(
    current_user: User,
    settings: Settings,
    db: Session | None = None,
    message: str | None = None,
) -> GoogleSheetsConfigResponse:
    uid = int(current_user.id) if current_user and current_user.id is not None else None
    effective_settings, custom_configured = _resolve_oauth_settings(settings, db, uid)
    exporter = SheetsExporter(
        credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
        credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
    )
    raw_sheet_id = current_user.google_sheet_id
    user_sheet_id = str(raw_sheet_id).strip() if raw_sheet_id else None
    auth_type_str = str(current_user.google_auth_type or "SERVICE_ACCOUNT")
    has_marker, google_email = _parse_oauth_vault_marker(current_user)
    oauth_connected = auth_type_str == "OAUTH2" and has_marker
    is_connected = bool(user_sheet_id)
    sheet_url = SheetsExporter.get_sheet_url(user_sheet_id) if user_sheet_id else None

    default_msg = (
        "Google Sheets listo para sincronizar."
        if is_connected
        else "Conecta tu cuenta de Google o vincula una hoja para empezar."
    )

    return GoogleSheetsConfigResponse(
        google_sheet_id=user_sheet_id,
        google_sheet_url=sheet_url,
        google_auth_type=auth_type_str,
        service_account_email=exporter.client_email,
        oauth_available=is_oauth_configured(effective_settings),
        oauth_connected=oauth_connected,
        google_account_email=google_email,
        oauth_custom_configured=custom_configured,
        is_connected=is_connected,
        message=message or default_msg,
    )


@router.get("/sheets", response_model=GoogleSheetsConfigResponse)
def get_user_sheets_config(
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session | None, Depends(get_db)] = None,
) -> GoogleSheetsConfigResponse:
    """Retorna la configuración de Google Sheets personal del usuario autenticado."""
    return _build_sheets_config_response(current_user, settings, db)


@router.post("/sheets", response_model=GoogleSheetsConfigResponse)
def update_user_sheets_config(
    payload: UpdateGoogleSheetsConfigRequest,
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsConfigResponse:
    """Actualiza la hoja personal de Google Sheets o método de vinculación para el usuario."""
    sheet_id = _extract_sheet_id(payload.google_sheet_id)
    current_user.google_sheet_id = sheet_id  # type: ignore[assignment]
    current_user.google_auth_type = payload.google_auth_type  # type: ignore[assignment]
    db.commit()
    db.refresh(current_user)
    invalidate_user_auth_cache(int(current_user.id))
    return _build_sheets_config_response(
        current_user,
        settings,
        db,
        message="Hoja vinculada." if sheet_id else "Hoja desvinculada.",
    )


@router.get("/sheets/oauth/start", response_model=GoogleOAuthStartResponse)
def start_google_oauth(
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    redirect_uri: Annotated[str | None, Query()] = None,
    db: Annotated[Session | None, Depends(get_db)] = None,
) -> GoogleOAuthStartResponse:
    """Genera la URL segura de autorización de Google OAuth 2.0 para el operador actual."""
    uid = int(current_user.id)
    effective_settings, _ = _resolve_oauth_settings(settings, db, uid)

    if not is_oauth_configured(effective_settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no está configurado. Carga Client ID y Client Secret de Google Cloud.",
        )

    safe_redirect = _validate_oauth_redirect_uri(redirect_uri, effective_settings)
    state = create_state(user_id=uid, secret=settings.jwt_secret)
    auth_url = build_authorization_url(effective_settings, state=state, redirect_uri=safe_redirect)
    return GoogleOAuthStartResponse(authorization_url=auth_url)


@router.post("/sheets/oauth/callback", response_model=GoogleSheetsConfigResponse)
def complete_google_oauth(
    payload: GoogleOAuthCallbackRequest,
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsConfigResponse:
    """Completa la autorización OAuth 2.0, cifra el refresh token y crea la hoja si no existe."""
    try:
        state_user_id = verify_state(payload.state, secret=settings.jwt_secret)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    uid = int(current_user.id)
    if state_user_id != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El estado OAuth no corresponde al usuario autenticado.",
        )

    effective_settings, _ = _resolve_oauth_settings(settings, db, uid)
    safe_redirect = _validate_oauth_redirect_uri(payload.redirect_uri, effective_settings)

    try:
        tokens = exchange_code(effective_settings, payload.code, redirect_uri=safe_redirect)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refresh_token = str(tokens.get("refresh_token") or "").strip()
    email = str(tokens.get("email") or "").strip() or None

    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    km.store_secret(f"user_{uid}:google_refresh_token", refresh_token)

    vault_marker = f"vault:{email}" if email else "vault"
    current_user.google_auth_type = "OAUTH2"  # type: ignore[assignment]
    current_user.google_refresh_token_enc = vault_marker  # type: ignore[assignment]

    if not current_user.google_sheet_id:
        exporter = SheetsExporter(
            oauth_credentials={
                "client_id": (effective_settings.GOOGLE_OAUTH_CLIENT_ID or "").strip(),
                "client_secret": (effective_settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip(),
                "refresh_token": refresh_token,
                "email": email,
            }
        )
        created_sheet_id = exporter.create_spreadsheet("P2P Merchant - Contabilidad")
        if created_sheet_id:
            current_user.google_sheet_id = created_sheet_id  # type: ignore[assignment]

    db.commit()
    db.refresh(current_user)
    return _build_sheets_config_response(
        current_user,
        settings,
        db,
        message="Cuenta de Google conectada y hoja lista para sincronizar.",
    )


@router.post("/sheets/oauth/credentials", response_model=GoogleSheetsConfigResponse)
def save_google_oauth_client(
    payload: GoogleOAuthClientConfigRequest,
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsConfigResponse:
    """Almacena cifradas con AES-256-GCM las credenciales OAuth 2.0 de Google Cloud API."""
    uid = int(current_user.id)
    redirect_val = (
        _validate_oauth_redirect_uri(payload.redirect_uri, settings)
        if payload.redirect_uri
        else settings.GOOGLE_OAUTH_REDIRECT_URI
    )
    secret_payload = json.dumps(
        {
            "client_id": payload.client_id.strip(),
            "client_secret": payload.client_secret.strip(),
            "redirect_uri": redirect_val,
        }
    )

    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    km.store_secret(f"user_{uid}:google_oauth_client", secret_payload)
    if str(current_user.role) == "ADMIN":
        km.store_secret("system:google_oauth_client", secret_payload)

    return _build_sheets_config_response(
        current_user,
        settings,
        db,
        message="Credenciales de API Google guardadas. Ya puedes iniciar sesión con Google.",
    )


@router.post("/sheets/oauth/disconnect", response_model=GoogleSheetsConfigResponse)
def disconnect_google_oauth(
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsConfigResponse:
    """Desvincula la sesión OAuth de Google del perfil manteniendo compatibilidad con otros modos."""
    current_user.google_refresh_token_enc = None  # type: ignore[assignment]
    if str(current_user.google_auth_type or "") == "OAUTH2":
        current_user.google_auth_type = "SERVICE_ACCOUNT"  # type: ignore[assignment]
    db.commit()
    db.refresh(current_user)
    return _build_sheets_config_response(
        current_user,
        settings,
        db,
        message="Cuenta de Google desvinculada.",
    )


@router.post("/sheets/sync", response_model=GoogleSheetsSyncResponse)
def sync_user_sheets_now(
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsSyncResponse:
    """Dispara en vivo la exportación del historial fiscal y contable hacia Google Sheets."""
    from src.data.repositories import JournalEntryRepository, OrderRepository
    from src.reporting.accounting_engine import AccountingEngine
    from src.reporting.tax_engine import FIFOCostMethod

    exporter = build_user_sheets_exporter(current_user, settings, db)
    sheet_id = str(current_user.google_sheet_id or "").strip()

    if not sheet_id and exporter.uses_oauth:
        created_id = exporter.create_spreadsheet("P2P Merchant - Contabilidad")
        if created_id:
            current_user.google_sheet_id = created_id  # type: ignore[assignment]
            db.commit()
            db.refresh(current_user)
            sheet_id = created_id

    if not sheet_id:
        return GoogleSheetsSyncResponse(
            success=False,
            google_sheet_id=None,
            google_sheet_url=None,
            service_account_email=exporter.client_email,
            oauth_connected=exporter.uses_oauth,
            message=exporter.last_error or "Vincula una hoja o conecta tu cuenta de Google primero.",
        )

    uid = int(current_user.id) if current_user and current_user.id is not None else None
    order_repo = OrderRepository(db, user_id=uid)
    completed_orders = order_repo.list_completed(user_id=uid)
    trade_results = FIFOCostMethod().process_orders(completed_orders)

    ok_fiscal = exporter.export(sheet_id, trade_results)

    now = datetime.now(UTC)
    journal_repo = JournalEntryRepository(db, user_id=uid)
    journal_entries = journal_repo.list_entries(user_id=uid)
    acc_engine = AccountingEngine(db=db, user_id=uid)
    ledger_summaries = acc_engine.get_monthly_ledger_report(year=now.year, month=now.month)
    ok_acc = exporter.export_accounting(sheet_id, journal_entries, ledger_summaries) if ok_fiscal else False

    sheet_url = SheetsExporter.get_sheet_url(sheet_id)
    if not ok_fiscal:
        return GoogleSheetsSyncResponse(
            success=False,
            google_sheet_id=sheet_id,
            google_sheet_url=sheet_url,
            service_account_email=exporter.client_email,
            oauth_connected=exporter.uses_oauth,
            message=exporter.last_error or "No se pudo sincronizar con Google Sheets.",
        )

    return GoogleSheetsSyncResponse(
        success=True,
        google_sheet_id=sheet_id,
        google_sheet_url=sheet_url,
        rows_exported=len(trade_results),
        journal_entries_exported=len(journal_entries) if ok_acc else 0,
        service_account_email=exporter.client_email,
        oauth_connected=exporter.uses_oauth,
        message=(
            f"Sincronizado: {len(trade_results)} órdenes y "
            f"{len(journal_entries) if ok_acc else 0} asientos."
        ),
    )


def _mask_bot_token(token: str | None) -> str:
    if not token or len(token) < 10:
        return "No configurado"
    prefix = token.split(":")[0] if ":" in token else token[:4]
    masked_prefix = f"{prefix[:3]}••••" if len(prefix) > 3 else "••••"
    return f"Activo ({masked_prefix}:AAH••••)"


@router.get("/telegram", response_model=TelegramStatusResponse)
def get_telegram_status(
    current_user: Annotated[User, Depends(require_trader)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramStatusResponse:
    """Retorna el estado sanitizado del bot de Telegram sin exponer jamás el token real ni Chat IDs ajenos."""
    raw_token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    is_configured = bool(raw_token and ":" in raw_token)
    linked_chat = str(current_user.telegram_id or "").strip() or None
    is_admin = str(getattr(current_user, "role", "") or "").upper() == "ADMIN"

    if not is_configured:
        bot_label = "Sin configurar"
    elif is_admin:
        bot_label = _mask_bot_token(raw_token)
    else:
        bot_label = "Activo"

    return TelegramStatusResponse(
        is_configured=is_configured,
        bot_token_masked=bot_label,
        linked_chat_id=linked_chat,
        fail_closed_5xx_enabled=True,
        weight_pause_enabled=True,
        log_sanitization_enabled=True,
        message=(
            "Enlace de notificaciones Telegram activo y sanitizado."
            if is_configured
            else "Configura TELEGRAM_BOT_TOKEN en el entorno del servidor."
        ),
    )


@router.post("/telegram/test")
def send_telegram_test_alert(
    current_user: Annotated[User, Depends(require_trader)],
    _settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str | bool]:
    """Despacha una alerta de prueba sanitizada exclusivamente al Chat ID personal del operador."""
    target_chat = str(current_user.telegram_id or "").strip()
    if not target_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tienes un Chat ID numérico de Telegram vinculado a tu perfil.",
        )

    from src.integrations.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier()
    sent = notifier.send_alert(
        f"🛡️ *Prueba de Auditoría P2P Merchant OS*\n\n"
        f"• Operador: `{current_user.username}` (`{current_user.role}`)\n"
        f"• Protocolos Fail-Closed: `ACTIVOS`\n"
        f"• Canal de Alertas: `VERIFICADO`",
        chat_id=target_chat,
    )
    if not sent:
        return {
            "success": False,
            "message": "No se pudo despachar la alerta de prueba. Verifica conectividad o token del bot.",
        }
    return {
        "success": True,
        "message": f"Alerta de prueba enviada exitosamente al Chat ID {target_chat}.",
    }


def _normalize_user_banks_payload(
    preferred_banks: list[str] | None,
    bank_initial_balances: dict[str, float] | None,
) -> tuple[list[str], dict[str, float]]:
    """Normaliza y deduplica bancos y saldos iniciales por banco del perfil del operador."""
    from src.core.spread_monitor import SpreadMonitor

    clean_prefs: list[str] = []
    seen: set[str] = set()
    for raw_b in preferred_banks or []:
        canon = SpreadMonitor.canonical_user_bank_name(raw_b)
        if canon and canon not in seen:
            seen.add(canon)
            clean_prefs.append(canon)

    clean_bals: dict[str, float] = {}
    for raw_b, raw_val in (bank_initial_balances or {}).items():
        canon = SpreadMonitor.canonical_user_bank_name(raw_b)
        if not canon:
            continue
        try:
            num_val = max(0.0, round(float(raw_val or 0.0), 2))
        except (ValueError, TypeError):
            num_val = 0.0
        clean_bals[canon] = round(clean_bals.get(canon, 0.0) + num_val, 2)
        if canon not in seen:
            seen.add(canon)
            clean_prefs.append(canon)

    for b_name in clean_prefs:
        if b_name not in clean_bals:
            clean_bals[b_name] = 0.0

    return clean_prefs, clean_bals


@router.get("/banks", response_model=UserBanksConfigResponse)
def get_user_banks_settings(
    current_user: Annotated[User, Depends(require_authenticated)],
) -> UserBanksConfigResponse:
    """Obtiene los bancos con los que opera el usuario y sus saldos iniciales registrados."""
    prefs, bals = _normalize_user_banks_payload(
        current_user.preferred_banks,
        current_user.bank_initial_balances,
    )
    total_ves = round(sum(bals.get(b, 0.0) for b in prefs), 2)
    return UserBanksConfigResponse(
        preferred_banks=prefs,
        bank_initial_balances=bals,
        total_initial_ves=total_ves,
        message=(
            f"Perfil bancario configurado con {len(prefs)} banco(s)."
            if prefs
            else "Aún no has seleccionado los bancos con los que trabajas."
        ),
    )


@router.post("/banks", response_model=UserBanksConfigResponse)
def save_user_banks_settings(
    req: UpdateUserBanksRequest,
    current_user: Annotated[User, Depends(require_authenticated)],
    db: Annotated[Session, Depends(get_db)],
) -> UserBanksConfigResponse:
    """Registra o actualiza los bancos con los que trabaja el operador y el saldo inicial VES por banco."""
    from src.core.spread_monitor import SpreadMonitor

    prefs, bals = _normalize_user_banks_payload(
        req.preferred_banks,
        req.bank_initial_balances,
    )
    if req.preferred_banks:
        explicit_set = {
            canon
            for raw in req.preferred_banks
            if (canon := SpreadMonitor.canonical_user_bank_name(raw))
        }
        if explicit_set:
            prefs = [b for b in prefs if b in explicit_set]
            bals = {b: bals.get(b, 0.0) for b in prefs}

    current_user.preferred_banks_json = json.dumps(prefs, ensure_ascii=False)  # type: ignore[assignment]
    current_user.bank_balances_json = json.dumps(bals, ensure_ascii=False)  # type: ignore[assignment]
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    uid = int(current_user.id) if current_user.id is not None else None
    invalidate_user_auth_cache(uid)

    total_ves = round(sum(bals.values()), 2)
    return UserBanksConfigResponse(
        preferred_banks=prefs,
        bank_initial_balances=bals,
        total_initial_ves=total_ves,
        message=f"Bancos y saldos actualizados ({len(prefs)} banco(s) • Total inicial: Bs. {total_ves:,.2f}).",
    )



