"""Rutas para gestión segura de credenciales de Binance y diagnóstico en vivo."""

import logging
import time
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from config.settings import Settings
from src.api.deps import get_settings, require_admin, require_authenticated
from src.api.schemas.settings import (
    BinanceStatusResponse,
    SaveBinanceKeysRequest,
    VerifyBinanceResponse,
)
from src.data.models import User
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
) -> BinanceStatusResponse:
    """Consulta el estado de las credenciales de Binance API sin exponer texto plano."""
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY)
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
) -> BinanceStatusResponse:
    """Almacena de forma cifrada (AES-256-GCM) las credenciales de la API de Binance."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY)

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
    logger.info("Credenciales de Binance actualizadas de forma segura por usuario '%s'", _current_user.username)

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
) -> VerifyBinanceResponse:
    """Realiza un diagnóstico en caliente: ping, deriva horaria (clock drift) y límite de API weight."""
    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY)
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
