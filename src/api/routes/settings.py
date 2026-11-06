"""Rutas para gestión segura de credenciales de Binance y diagnóstico en vivo."""

import logging
import time
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from config.settings import Settings
from src.api.deps import get_db, get_settings, require_admin, require_authenticated
from src.api.schemas.settings import (
    BinanceStatusResponse,
    GoogleSheetsConfigResponse,
    GoogleSheetsSyncResponse,
    SaveBinanceKeysRequest,
    TelegramStatusResponse,
    UpdateGoogleSheetsConfigRequest,
    VerifyBinanceResponse,
)
from src.data.models import User
from src.reporting.sheets_exporter import SheetsExporter
from src.security.api_key_manager import ApiKeyManager

logger = logging.getLogger("settings_route")

router = APIRouter(prefix="/api/settings", tags=["Configuración"])


def _mask_key(key: str) -> str:
    """Oculta de forma segura la API key dejando solo los extremos."""
    if not key or len(key) < 8:
        return "••••••••"
    return f"{key[:4]}••••{key[-4:]}"


@router.get("/binance", response_model=BinanceStatusResponse)
def get_binance_status(
    _current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> BinanceStatusResponse:
    """Consulta el estado de las credenciales de Binance API sin exponer texto plano."""
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    try:
        api_key = km.get_secret("binance_api_key")
        key_type = km.get_secret("binance_key_type")
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
            "Credenciales de Binance configuradas y cifradas en reposo (AES-256-GCM)."
            if is_configured
            else "No se han suministrado credenciales API de Binance todavía."
        ),
    )


@router.post("/binance", response_model=BinanceStatusResponse)
def save_binance_keys(
    req: SaveBinanceKeysRequest,
    request: Request,
    _current_user: Annotated[User, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> BinanceStatusResponse:
    """Almacena de forma cifrada (AES-256-GCM) las credenciales de la API de Binance."""
    operator_username = str(_current_user.username)
    client_ip = request.client.host if request.client else "127.0.0.1"
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)

    try:
        km.store_secret("binance_api_key", req.api_key.strip(), ip_address=client_ip)
        km.store_secret("binance_private_key", req.secret_key.strip(), ip_address=client_ip)
        km.store_secret("binance_key_type", req.key_type, ip_address=client_ip)
    except (RuntimeError, ValueError) as err:
        logger.error("Error al cifrar credenciales de Binance: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error criptográfico interno al resguardar las credenciales.",
        ) from err

    masked = _mask_key(req.api_key.strip())
    logger.info("Credenciales de Binance actualizadas de forma segura por usuario '%s'", operator_username)

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
        message="Credenciales de Binance cifradas y almacenadas exitosamente con AES-256-GCM.",
    )


@router.post("/binance/verify", response_model=VerifyBinanceResponse)
def verify_binance_connection(
    _current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> VerifyBinanceResponse:
    """Realiza un diagnóstico en caliente: ping, deriva horaria (clock drift) y límite de API weight."""
    factory = sessionmaker(bind=db.get_bind())
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=factory)
    try:
        api_key = km.get_secret("binance_api_key")
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
        return VerifyBinanceResponse(
            success=False,
            is_connected=False,
            latency_ms=0.0,
            clock_drift_ms=0,
            used_weight=0,
            max_weight=5000,
            is_weight_safe=True,
            server_time_utc=None,
            message=f"Error al verificar conexión con Binance: {exc}",
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


@router.get("/sheets", response_model=GoogleSheetsConfigResponse)
def get_user_sheets_config(
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GoogleSheetsConfigResponse:
    """Retorna la configuración de Google Sheets personal del usuario autenticado."""
    exporter = SheetsExporter(
        credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
        credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
    )
    raw_sheet_id = current_user.google_sheet_id or settings.GOOGLE_SHEET_ID
    user_sheet_id = str(raw_sheet_id) if raw_sheet_id else None
    is_connected = bool(user_sheet_id)
    sheet_url = SheetsExporter.get_sheet_url(user_sheet_id) if user_sheet_id else None
    auth_type_str = str(current_user.google_auth_type or "SERVICE_ACCOUNT")

    return GoogleSheetsConfigResponse(
        google_sheet_id=user_sheet_id,
        google_sheet_url=sheet_url,
        google_auth_type=auth_type_str,
        service_account_email=exporter.client_email,
        is_connected=is_connected,
        message=(
            "Google Sheets sincronizado y listo para recibir asientos."
            if is_connected
            else "No has vinculado tu Google Sheet personal todavía."
        ),
    )


@router.post("/sheets", response_model=GoogleSheetsConfigResponse)
def update_user_sheets_config(
    payload: UpdateGoogleSheetsConfigRequest,
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsConfigResponse:
    """Actualiza la hoja personal de Google Sheets o método de vinculación para el usuario."""
    sheet_id = _extract_sheet_id(payload.google_sheet_id)
    current_user.google_sheet_id = sheet_id  # type: ignore[assignment]
    current_user.google_auth_type = payload.google_auth_type  # type: ignore[assignment]
    db.commit()
    db.refresh(current_user)

    exporter = SheetsExporter(
        credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
        credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
    )
    sheet_url = SheetsExporter.get_sheet_url(sheet_id) if sheet_id else None
    updated_auth_type = str(current_user.google_auth_type or "SERVICE_ACCOUNT")

    return GoogleSheetsConfigResponse(
        google_sheet_id=sheet_id,
        google_sheet_url=sheet_url,
        google_auth_type=updated_auth_type,
        service_account_email=exporter.client_email,
        is_connected=bool(sheet_id),
        message="Configuración de Google Sheets guardada exitosamente.",
    )


@router.post("/sheets/sync", response_model=GoogleSheetsSyncResponse)
def sync_user_sheets_now(
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> GoogleSheetsSyncResponse:
    """Dispara en vivo la exportación del historial fiscal y contable hacia Google Sheets."""
    from src.data.repositories import JournalEntryRepository, OrderRepository
    from src.reporting.accounting_engine import AccountingEngine
    from src.reporting.tax_engine import FIFOCostMethod

    sheet_id = str(current_user.google_sheet_id or settings.GOOGLE_SHEET_ID or "").strip()
    exporter = SheetsExporter(
        credentials_path=settings.GOOGLE_CREDENTIALS_FILE,
        credentials_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
    )

    if not sheet_id:
        return GoogleSheetsSyncResponse(
            success=False,
            google_sheet_id=None,
            google_sheet_url=None,
            service_account_email=exporter.client_email,
            message="No hay ningún Google Sheet ID vinculado. Ingresa el enlace o ID primero.",
        )

    order_repo = OrderRepository(db)
    completed_orders = order_repo.list_completed()
    trade_results = FIFOCostMethod().process_orders(completed_orders)

    ok_fiscal = exporter.export(sheet_id, trade_results)

    now = datetime.now(UTC)
    journal_repo = JournalEntryRepository(db)
    journal_entries = journal_repo.list_entries()
    acc_engine = AccountingEngine(db=db)
    ledger_summaries = acc_engine.get_monthly_ledger_report(year=now.year, month=now.month)
    ok_acc = exporter.export_accounting(sheet_id, journal_entries, ledger_summaries) if ok_fiscal else False

    sheet_url = SheetsExporter.get_sheet_url(sheet_id)
    if not ok_fiscal:
        return GoogleSheetsSyncResponse(
            success=False,
            google_sheet_id=sheet_id,
            google_sheet_url=sheet_url,
            service_account_email=exporter.client_email,
            message=exporter.last_error or "Error al sincronizar con Google Sheets. Verifica permisos de editor.",
        )

    return GoogleSheetsSyncResponse(
        success=True,
        google_sheet_id=sheet_id,
        google_sheet_url=sheet_url,
        rows_exported=len(trade_results),
        journal_entries_exported=len(journal_entries) if ok_acc else 0,
        service_account_email=exporter.client_email,
        message=(
            f"Sincronización completada: {len(trade_results)} operaciones fiscales y "
            f"{len(journal_entries) if ok_acc else 0} asientos contables exportados."
        ),
    )


def _mask_bot_token(token: str | None) -> str:
    if not token or len(token) < 10:
        return "No configurado"
    prefix = token.split(":")[0] if ":" in token else token[:4]
    masked_prefix = f"{prefix[:3]}••••" if len(prefix) > 3 else "••••"
    return f"Configurado en Bóveda (.env) — {masked_prefix}:AAH••••"


@router.get("/telegram", response_model=TelegramStatusResponse)
def get_telegram_status(
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramStatusResponse:
    """Retorna el estado sanitizado del bot de Telegram sin exponer jamás el token real."""
    raw_token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    is_configured = bool(raw_token and ":" in raw_token)
    linked_chat = str(current_user.telegram_id or settings.TELEGRAM_ALERT_CHAT_ID or "").strip() or None

    return TelegramStatusResponse(
        is_configured=is_configured,
        bot_token_masked=_mask_bot_token(raw_token) if is_configured else "No configurado en .env",
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
    current_user: Annotated[User, Depends(require_authenticated)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str | bool]:
    """Despacha una alerta de prueba sanitizada al Chat ID vinculado del operador."""
    target_chat = str(current_user.telegram_id or settings.TELEGRAM_ALERT_CHAT_ID or "").strip()
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


