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
    SaveBinanceKeysRequest,
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
    user_sheet_id = current_user.google_sheet_id or settings.GOOGLE_SHEET_ID
    is_connected = bool(user_sheet_id)
    sheet_url = SheetsExporter.get_sheet_url(user_sheet_id) if user_sheet_id else None

    return GoogleSheetsConfigResponse(
        google_sheet_id=user_sheet_id,
        google_sheet_url=sheet_url,
        google_auth_type=current_user.google_auth_type or "SERVICE_ACCOUNT",
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

    return GoogleSheetsConfigResponse(
        google_sheet_id=sheet_id,
        google_sheet_url=sheet_url,
        google_auth_type=current_user.google_auth_type or "SERVICE_ACCOUNT",
        service_account_email=exporter.client_email,
        is_connected=bool(sheet_id),
        message="Configuración de Google Sheets guardada exitosamente.",
    )

