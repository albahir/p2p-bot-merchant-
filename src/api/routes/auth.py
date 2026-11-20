"""Rutas de autenticación, generación de tokens JWT y Telegram SSO."""

import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.settings import Settings
from src.api.deps import get_current_user, get_db, get_settings
from src.api.schemas.auth import (
    EmailSendCodeRequest,
    EmailVerifyCodeRequest,
    LoginRequest,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    RecoveryOptionsResponse,
    RecoveryProfileUpdateRequest,
    RegisterRequest,
    TelegramAuthData,
    TelegramWebAppAuthData,
    TokenResponse,
    UserPublicResponse,
)
from src.api.security import (
    create_access_token,
    decode_access_token,
    verify_telegram_auth_data,
    verify_telegram_webapp_data,
)
from src.data.models import User
from src.data.repositories import UserRepository
from src.security.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# Almacén de códigos OTP de recuperación (sincronizado con Neon PostgreSQL SystemState para Render + Local)
_RECOVERY_CODES: dict[str, dict[str, Any]] = {}
_BOT_PROFILE_CACHE: dict[str, Any] = {"expires_at": 0.0, "data": None}


def _hash_otp(username: str, otp: str) -> str:
    """Calcula un hash HMAC-SHA256 del código OTP para no almacenarlo jamás en texto plano."""
    import hashlib
    import hmac

    try:
        secret = get_settings().jwt_secret.encode("utf-8")
    except (RuntimeError, ValueError, OSError):
        secret = b"p2p-otp-fallback-key"
    msg = f"{username.strip().lower()}:{otp.strip()}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def save_shared_recovery_otp(
    db: Session,
    username: str,
    user_id: int,
    otp: str | None = None,
    expires_at: float = 0.0,
    attempts: int = 0,
    otp_hash: str | None = None,
) -> None:
    """Persiste el hash del código OTP en SystemState (PostgreSQL/SQLite) para compartirlo entre Local y Render."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    clean_user = username.strip().lower()
    key_str = f"recovery_otp:{clean_user}"[:64]
    final_hash = otp_hash or _hash_otp(clean_user, str(otp or ""))
    payload = json.dumps(
        {"h": final_hash, "e": int(expires_at), "u": int(user_id), "a": int(attempts)},
        separators=(",", ":"),
    )
    _RECOVERY_CODES[clean_user] = {
        "code_hash": final_hash,
        "expires_at": float(expires_at),
        "user_id": int(user_id),
        "attempts": int(attempts),
    }
    try:
        row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if row is not None:
            row.value = payload  # type: ignore[assignment]
        else:
            db.add(SystemState(key=key_str, value=payload))
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def load_shared_recovery_otp(db: Session, username: str) -> dict[str, Any] | None:
    """Carga el registro hasheado del OTP activo desde la base de datos compartida (o memoria local)."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    clean_user = username.strip().lower()
    key_str = f"recovery_otp:{clean_user}"[:64]
    try:
        row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if row is not None and row.value:
            data = json.loads(str(row.value))
            record = {
                "code_hash": str(data["h"]),
                "expires_at": float(data["e"]),
                "user_id": int(data["u"]),
                "attempts": int(data.get("a", 0)),
            }
            _RECOVERY_CODES[clean_user] = record
            return record
    except (SQLAlchemyError, ValueError, KeyError, TypeError):
        pass
    return _RECOVERY_CODES.get(clean_user)


def delete_shared_recovery_otp(db: Session, username: str) -> None:
    """Elimina un código OTP consumido o expirado de memoria y de la base de datos compartida."""
    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    clean_user = username.strip().lower()
    _RECOVERY_CODES.pop(clean_user, None)
    key_str = f"recovery_otp:{clean_user}"[:64]
    try:
        row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if row is not None:
            db.delete(row)
            db.commit()
    except SQLAlchemyError:
        db.rollback()


def enqueue_render_otp_outbox(
    db: Session,
    username: str,
    chat_id: str,
    otp: str,
    expires_at: float,
) -> bool:
    """Encola el envío del OTP en SystemState para que el Bot alojado en Render lo despache a Telegram."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    clean_user = username.strip().lower()
    key_str = f"tg_outbox:{clean_user}"[:64]
    payload = json.dumps(
        {
            "c": str(chat_id).strip(),
            "u": username.strip()[:30],
            "o": str(otp),
            "e": int(expires_at),
        },
        separators=(",", ":"),
    )
    try:
        row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if row is not None:
            row.value = payload  # type: ignore[assignment]
        else:
            db.add(SystemState(key=key_str, value=payload))
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        return False


def _email_otp_state_key(clean_email: str) -> str:
    import hashlib

    digest = hashlib.sha256(clean_email.encode()).hexdigest()[:24]
    return f"email_otp:{digest}"


@router.post("/email/send-code")
def send_email_verification_code(
    req: EmailSendCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Envía un código OTP de 6 dígitos al correo vía SMTP durante el registro."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState
    from src.integrations.email_verifier import EmailVerificationService

    clean_email = _validate_and_normalize_email(req.email)
    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ingresa un correo electrónico válido.",
        )

    existing = UserRepository(db).get_by_email(clean_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este correo electrónico ya está asociado a otra cuenta.",
        )

    mailer = EmailVerificationService(settings)
    if not mailer.is_configured:
        return {
            "sent": False,
            "smtp_configured": False,
            "message": (
                "SMTP no configurado aún en el servidor. "
                "Agrega SMTP_USER y SMTP_PASSWORD (App Password de Gmail) en config/.env."
            ),
        }

    key_str = _email_otp_state_key(clean_email)
    now_ts = time.time()
    try:
        existing_row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if existing_row is not None and existing_row.value:
            prev = json.loads(str(existing_row.value))
            locked_until = float(prev.get("l", 0))
            if locked_until > now_ts:
                rem_min = max(1, int((locked_until - now_ts) // 60) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Demasiados intentos fallidos. Espera {rem_min} minuto(s).",
                )
            last_sent = float(prev.get("s", 0))
            if last_sent > 0 and (now_ts - last_sent) < 30:
                wait_s = max(1, int(30 - (now_ts - last_sent)))
                return {
                    "sent": True,
                    "smtp_configured": True,
                    "cooldown_seconds": wait_s,
                    "message": f"Ya enviamos un código hace unos segundos. Revisa tu bandeja o espera {wait_s}s.",
                }
    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError, TypeError, KeyError):
        existing_row = None

    otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    otp_hash = _hash_otp(clean_email, otp)
    sent_ok, err_msg = mailer.send_verification_code(to_email=clean_email, code=otp)
    if not sent_ok:
        return {
            "sent": False,
            "smtp_configured": True,
            "message": err_msg or "No se pudo enviar el código de verificación por SMTP.",
        }

    payload = json.dumps(
        {
            "h": otp_hash,
            "e": int(now_ts + 900),
            "a": 0,
            "s": int(now_ts),
            "l": 0,
        },
        separators=(",", ":"),
    )
    try:
        row = db.query(SystemState).filter(SystemState.key == key_str).first()
        if row is not None:
            row.value = payload  # type: ignore[assignment]
        else:
            db.add(SystemState(key=key_str, value=payload))
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    return {
        "sent": True,
        "smtp_configured": True,
        "message": f"Código de 6 dígitos enviado a {clean_email}.",
    }


@router.post("/email/verify-code")
def verify_email_code(
    req: EmailVerifyCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Valida el código OTP de 6 dígitos enviado al correo con límite anti-fuerza bruta."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    clean_email = _validate_and_normalize_email(req.email)
    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Correo inválido.",
        )

    key_str = _email_otp_state_key(clean_email)
    now_ts = time.time()
    row = db.query(SystemState).filter(SystemState.key == key_str).first()
    if row is None or not row.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay ningún código pendiente para este correo. Solicita uno nuevo.",
        )

    try:
        data = json.loads(str(row.value))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solicitud de verificación inválida. Solicita un código nuevo.",
        )

    locked_until = float(data.get("l", 0))
    if locked_until > now_ts:
        rem_min = max(1, int((locked_until - now_ts) // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos incorrectos. Intenta en {rem_min} minuto(s).",
        )

    if now_ts > float(data.get("e", 0)):
        db.delete(row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código de verificación expiró (15 min). Solicita uno nuevo.",
        )

    submitted_hash = _hash_otp(clean_email, req.code.strip())
    if not secrets.compare_digest(str(data.get("h", "")), submitted_hash):
        attempts = int(data.get("a", 0)) + 1
        data["a"] = attempts
        if attempts >= 5:
            data["l"] = int(now_ts + 900)
            row.value = json.dumps(data, separators=(",", ":"))  # type: ignore[assignment]
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Has superado 5 intentos fallidos. Espera 15 minutos antes de reintentar.",
            )
        row.value = json.dumps(data, separators=(",", ":"))  # type: ignore[assignment]
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificación incorrecto.",
        )

    try:
        db.delete(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    ver_token = create_access_token(
        data={"sub": clean_email, "purpose": "email_verified"},
        secret_key=settings.jwt_secret,
        expires_delta=timedelta(minutes=25),
        algorithm=settings.JWT_ALGORITHM,
    )
    return {
        "verified": True,
        "email": clean_email,
        "verification_token": ver_token,
        "message": "Correo verificado correctamente.",
    }


@router.get("/telegram-bot-info")
def get_telegram_bot_info(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Retorna el @username público y enlace directo https://t.me/<bot>?start=id sin exponer secretos."""
    import json

    from sqlalchemy.exc import SQLAlchemyError

    from src.data.models import SystemState

    # 1. Prioridad máxima: variable explícita en .env / Render
    env_username = str(getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").strip().lstrip("@")
    if env_username:
        return {
            "available": True,
            "bot_username": env_username,
            "bot_mention": f"@{env_username}",
            "bot_name": "P2P Merchant Bot",
            "bot_url": f"https://t.me/{env_username}?start=id",
            "command": "/id",
        }

    # 2. Caché en memoria (TTL 5 min)
    now_ts = time.monotonic()
    cached_data = _BOT_PROFILE_CACHE.get("data")
    if cached_data and now_ts < float(_BOT_PROFILE_CACHE.get("expires_at", 0.0)):
        return dict(cached_data)

    # 3. Perfil público publicado por el Bot en Render dentro de Neon PostgreSQL (SystemState)
    try:
        row = db.query(SystemState).filter(SystemState.key == "telegram_bot_profile").first()
        if row is not None and row.value:
            parsed = json.loads(str(row.value))
            uname = str(parsed.get("username") or "").strip().lstrip("@")
            fname = str(parsed.get("first_name") or "P2P Merchant Bot").strip()
            if uname:
                payload = {
                    "available": True,
                    "bot_username": uname,
                    "bot_mention": f"@{uname}",
                    "bot_name": fname,
                    "bot_url": f"https://t.me/{uname}?start=id",
                    "command": "/id",
                }
                _BOT_PROFILE_CACHE["data"] = payload
                _BOT_PROFILE_CACHE["expires_at"] = now_ts + 300.0
                return dict(payload)
    except (SQLAlchemyError, ValueError, TypeError, KeyError):
        pass

    # 4. Consulta directa puntual getMe si el backend actual tiene conectividad hacia Telegram / Worker
    if (settings.TELEGRAM_BOT_TOKEN or "").strip():
        try:
            from src.integrations.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier(
                bot_token=settings.TELEGRAM_BOT_TOKEN,
                proxy_url=settings.TELEGRAM_PROXY_URL,
                api_base_url=settings.TELEGRAM_API_BASE_URL,
            )
            profile = notifier.sync_bot_profile_to_db(db=db)
            if profile and profile.get("username"):
                uname = profile["username"].lstrip("@")
                payload = {
                    "available": True,
                    "bot_username": uname,
                    "bot_mention": f"@{uname}",
                    "bot_name": profile.get("first_name") or "P2P Merchant Bot",
                    "bot_url": f"https://t.me/{uname}?start=id",
                    "command": "/id",
                }
                _BOT_PROFILE_CACHE["data"] = payload
                _BOT_PROFILE_CACHE["expires_at"] = now_ts + 300.0
                return dict(payload)
        except (RuntimeError, ValueError, OSError, TypeError):
            pass

    return {
        "available": False,
        "bot_username": None,
        "bot_mention": None,
        "bot_name": "P2P Merchant Bot",
        "bot_url": None,
        "command": "/id",
    }


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Inicia sesión con credenciales tradicionales de usuario y contraseña."""
    auth_svc = AuthService(db_session=db)
    user = auth_svc.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


def _validate_and_normalize_email(raw_email: str | None) -> str | None:
    if raw_email is None:
        return None
    cleaned = raw_email.strip().lower()
    if not cleaned:
        return None
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El formato del correo electrónico de recuperación no es válido.",
        )
    return cleaned


def _validate_and_normalize_tax_id(raw_tax_id: str | None) -> str | None:
    """Valida y normaliza una Cédula de Identidad (V-/E-) o RIF venezolano (V-/E-/J-/G-/P-)."""
    if not raw_tax_id or not raw_tax_id.strip():
        return None
    cleaned = raw_tax_id.strip().upper().replace(".", "").replace(" ", "")
    if re.fullmatch(r"\d{6,9}", cleaned):
        return f"V-{cleaned}"
    match = re.fullmatch(r"([VEJGP])-?(\d{6,9})(?:-?(\d))?", cleaned)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Formato inválido de Cédula o RIF. Usa ej. V-12345678 o J-12345678-9.",
        )
    prefix, digits, dv = match.groups()
    return f"{prefix}-{digits}-{dv}" if dv is not None else f"{prefix}-{digits}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Registra una nueva cuenta de usuario en el sistema con datos de recuperación segura."""
    user_repo = UserRepository(db)
    existing_user = user_repo.get_by_username(req.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre de usuario '{req.username}' ya está registrado.",
        )

    clean_email = _validate_and_normalize_email(req.email)
    email_verified = False
    if clean_email:
        existing_email_user = user_repo.get_by_email(clean_email)
        if existing_email_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este correo electrónico ya está asociado a otra cuenta.",
            )
        if req.email_verification_token:
            ver_payload = decode_access_token(
                token=req.email_verification_token,
                secret_key=settings.jwt_secret,
                algorithm=settings.JWT_ALGORITHM,
            )
            if (
                ver_payload
                and ver_payload.get("purpose") == "email_verified"
                and ver_payload.get("sub") == clean_email
            ):
                email_verified = True

    clean_question = req.security_question.strip() if req.security_question and req.security_question.strip() else None
    clean_answer = req.security_answer.strip() if req.security_answer and req.security_answer.strip() else None
    if (clean_question and not clean_answer) or (clean_answer and not clean_question):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Debes indicar tanto la pregunta de seguridad como su respuesta secreta.",
        )
    if clean_answer and len(clean_answer) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La respuesta secreta debe tener al menos 3 caracteres.",
        )

    sec_answer_hash = AuthService.hash_secret_answer(clean_answer) if clean_answer else None
    plain_recovery_key = AuthService.generate_recovery_key()
    recovery_key_hash = AuthService.hash_password(plain_recovery_key)
    clean_full_name = req.full_name.strip() if req.full_name and req.full_name.strip() else None
    clean_tax_id = _validate_and_normalize_tax_id(req.tax_id)

    # Evaluar si el Telegram ID está en la whitelist de administradores o traders
    is_admin = False
    is_trader = False
    tg_id_str = str(req.telegram_id).strip() if req.telegram_id else None
    if tg_id_str:
        try:
            tg_int = int(tg_id_str)
            is_admin = tg_int in settings.telegram_allowed_users
            is_trader = tg_int in settings.telegram_trader_users
        except (ValueError, TypeError):
            pass

    assigned_role = "ADMIN" if is_admin else ("TRADER" if is_trader else "INVITADO")
    password_hash = AuthService.hash_password(req.password)

    existing_tg_user = user_repo.get_by_telegram_id(tg_id_str) if tg_id_str else None
    if existing_tg_user is not None:
        # Si es una cuenta pre-autorizada (placeholder tg_/trader_/admin_), permitir reclamarla con clave propia
        if str(existing_tg_user.username).startswith(("tg_", "trader_", "admin_")):
            existing_tg_user.username = req.username  # type: ignore[assignment]
            existing_tg_user.password_hash = password_hash  # type: ignore[assignment]
            if clean_full_name:
                existing_tg_user.full_name = clean_full_name  # type: ignore[assignment]
            if clean_tax_id:
                existing_tg_user.tax_id = clean_tax_id  # type: ignore[assignment]
            if clean_email:
                existing_tg_user.email = clean_email  # type: ignore[assignment]
            if clean_question and sec_answer_hash:
                existing_tg_user.security_question = clean_question  # type: ignore[assignment]
                existing_tg_user.security_answer_hash = sec_answer_hash  # type: ignore[assignment]
            existing_tg_user.recovery_key_hash = recovery_key_hash  # type: ignore[assignment]
            current_role = str(existing_tg_user.role or "INVITADO").upper()
            if assigned_role == "ADMIN" or current_role not in ("ADMIN", "TRADER"):
                existing_tg_user.role = assigned_role  # type: ignore[assignment]
            existing_tg_user.is_active = True  # type: ignore[assignment]
            db.commit()
            db.refresh(existing_tg_user)
            new_user = existing_tg_user
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este ID de Telegram ya está vinculado a otra cuenta activa. Inicia sesión o recupera tu contraseña.",
            )
    else:
        new_user = user_repo.create_user(
            username=req.username,
            password_hash=password_hash,
            role=assigned_role,
            telegram_id=tg_id_str,
            is_active=True,
            full_name=clean_full_name,
            tax_id=clean_tax_id,
            email=clean_email,
            security_question=clean_question,
            security_answer_hash=sec_answer_hash,
            recovery_key_hash=recovery_key_hash,
        )

    if email_verified and not getattr(new_user, "email_verified", False):
        new_user.email_verified = True  # type: ignore[assignment]
        db.commit()
        db.refresh(new_user)

    if req.google_sheet_id and req.google_sheet_id.strip():
        raw_sheet = req.google_sheet_id.strip()
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw_sheet)
        new_user.google_sheet_id = match.group(1) if match else raw_sheet  # type: ignore[assignment]
        db.commit()
        db.refresh(new_user)

    if req.preferred_banks:
        import json

        from src.core.spread_monitor import SpreadMonitor

        clean_banks: list[str] = []
        for raw_b in req.preferred_banks:
            canon = SpreadMonitor.canonical_user_bank_name(raw_b)
            if canon and canon not in clean_banks:
                clean_banks.append(canon)
        if clean_banks:
            new_user.preferred_banks_json = json.dumps(clean_banks, ensure_ascii=False)  # type: ignore[assignment]
            new_user.bank_balances_json = json.dumps({b: 0.0 for b in clean_banks}, ensure_ascii=False)  # type: ignore[assignment]
            db.commit()
            db.refresh(new_user)

    # Notificar al administrador por Telegram en segundo plano sin bloquear la respuesta HTTP
    try:
        from src.integrations.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_alert_async(
            "👤 *Nuevo Usuario Registrado*\n\n"
            f"• Usuario: `{new_user.username}`\n"
            f"• Rol Asignado: `{new_user.role}`\n"
            f"• Telegram ID: `{new_user.telegram_id or 'No vinculado'}`\n"
            "Accede a /admin en la web para promover o ajustar permisos."
        )
    except (RuntimeError, ValueError, OSError, TypeError):
        pass

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(new_user.id), "username": new_user.username, "role": new_user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(new_user),
        recovery_key=plain_recovery_key,
    )


def _ensure_not_recovery_locked(user: User) -> None:
    locked_until = user.recovery_locked_until
    if locked_until is None:
        return
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    locked_naive = locked_until.replace(tzinfo=None)
    if locked_naive > now_naive:
        remaining_min = max(1, int((locked_naive - now_naive).total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Recuperación bloqueada temporalmente por múltiples intentos fallidos. Intenta en {remaining_min} minuto(s).",
        )


def _register_failed_recovery(user: User, db: Session) -> None:
    attempts = int(user.failed_recovery_attempts or 0) + 1
    user.failed_recovery_attempts = attempts  # type: ignore[assignment]
    if attempts >= 5:
        user.recovery_locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15)  # type: ignore[assignment]
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has superado el máximo de 5 intentos fallidos. Recuperación bloqueada por 15 minutos.",
        )
    db.commit()


@router.post("/recover-options", response_model=RecoveryOptionsResponse)
def get_recovery_options(
    req: PasswordRecoveryRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RecoveryOptionsResponse:
    """Consulta qué métodos de recuperación están habilitados para un alias, correo o Telegram ID."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_identifier(req.username)
    if not user or not user.is_active:
        return RecoveryOptionsResponse()

    now_naive = datetime.now(UTC).replace(tzinfo=None)
    is_locked = bool(
        user.recovery_locked_until is not None
        and user.recovery_locked_until.replace(tzinfo=None) > now_naive
    )

    return RecoveryOptionsResponse(
        has_email=bool(user.email),
        has_telegram=bool(user.telegram_id),
        has_security_question=bool(user.security_question and user.security_answer_hash),
        security_question=str(user.security_question) if (user.security_question and user.security_answer_hash) else None,
        has_recovery_key=bool(user.recovery_key_hash),
        is_locked=is_locked,
    )


@router.post("/recover-password")
def recover_password(
    req: PasswordRecoveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings | None, Depends(get_settings)] = None,
) -> dict[str, Any]:
    """Genera y despacha un código OTP de recuperación al Telegram del usuario."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_identifier(req.username)

    if not user or not user.is_active:
        # Mensaje genérico para mitigar enumeración de cuentas
        return {
            "success": True,
            "message": "Si la cuenta existe y tiene Telegram vinculado, se ha enviado el código de recuperación.",
            "has_telegram": False,
        }

    _ensure_not_recovery_locked(user)

    otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = time.time() + 900  # 15 minutos
    uid_int = int(user.id) if user.id is not None else 0

    if req.channel == "email":
        if not user.email:
            return {
                "success": False,
                "message": "Esta cuenta no tiene un correo electrónico vinculado.",
                "has_email": False,
            }
        from src.integrations.email_verifier import EmailVerificationService

        effective_settings = settings or get_settings()
        mailer = EmailVerificationService(effective_settings)
        if not mailer.is_configured:
            return {
                "success": False,
                "has_email": True,
                "message": "SMTP no configurado en el servidor para enviar códigos por correo.",
            }
        save_shared_recovery_otp(
            db=db,
            username=str(user.username),
            user_id=uid_int,
            otp=otp,
            expires_at=expires_at,
        )
        sent_ok, err_msg = mailer.send_verification_code(to_email=str(user.email), code=otp)
        if not sent_ok:
            return {
                "success": False,
                "has_email": True,
                "message": err_msg or "No se pudo enviar el código de recuperación al correo.",
            }
        return {
            "success": True,
            "has_email": True,
            "message": "Código OTP de 6 dígitos enviado a tu correo vinculado.",
        }

    if not user.telegram_id:
        return {
            "success": False,
            "message": "Esta cuenta no tiene un Chat ID de Telegram vinculado. Usa tu Pregunta Secreta o tu Llave Maestra.",
            "has_telegram": False,
        }

    # Persistir inmediatamente en Neon PostgreSQL / SQLite compartido con el Bot en Render
    save_shared_recovery_otp(
        db=db,
        username=str(user.username),
        user_id=uid_int,
        otp=otp,
        expires_at=expires_at,
    )

    sent_to_telegram = False
    if user.telegram_id:
        try:
            from src.integrations.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier()
            sent_to_telegram = bool(
                notifier.send_alert(
                    "🔐 *Recuperación de Contraseña*\n\n"
                    f"Hola `{user.username}`, tu código de seguridad es:\n"
                    f"👉 `{otp}`\n\n"
                    "Válido por 15 minutos. Si no solicitaste este código, ignora este mensaje.",
                    chat_id=str(user.telegram_id),
                    max_retries=1,
                    timeout_override=3.5,
                )
            )
        except (RuntimeError, ValueError, OSError, TypeError):
            sent_to_telegram = False

    if sent_to_telegram:
        return {
            "success": True,
            "message": "Código OTP de 6 dígitos enviado exitosamente a tu Telegram vinculado.",
            "has_telegram": True,
            "relayed_via_render": False,
        }

    # Si la red local bloquea Telegram (ISP Venezuela), encolar en la BD compartida para que el Bot en Render lo envíe
    queued_for_render = enqueue_render_otp_outbox(
        db=db,
        username=str(user.username),
        chat_id=str(user.telegram_id),
        otp=otp,
        expires_at=expires_at,
    )
    return {
        "success": True,
        "has_telegram": True,
        "relayed_via_render": queued_for_render,
        "message": (
            "Código OTP generado y despachado a través de tu Bot en Render (vía base de datos compartida). "
            "Revisa tu Telegram en unos segundos o envíale /otp directamente a tu bot en Telegram."
        ),
    }


@router.post("/reset-password")
def reset_password(
    req: PasswordResetRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Restablece la contraseña mediante OTP de Telegram, Pregunta de Seguridad o Llave Maestra."""
    user_repo = UserRepository(db)
    target_user = user_repo.get_by_identifier(req.username)

    if req.method in ("telegram_otp", "email_otp"):
        if target_user:
            _ensure_not_recovery_locked(target_user)

        lookup_key = str(target_user.username).lower() if target_user else req.username.strip().lower()
        record = load_shared_recovery_otp(db, lookup_key)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay ninguna solicitud de recuperación activa para este usuario o ha expirado.",
            )

        if time.time() > record["expires_at"]:
            delete_shared_recovery_otp(db, lookup_key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El código de recuperación ha expirado (límite de 15 minutos).",
            )

        submitted_hash = _hash_otp(lookup_key, req.reset_code.strip())
        if not secrets.compare_digest(str(record["code_hash"]), submitted_hash):
            new_attempts = int(record.get("attempts", 0)) + 1
            record["attempts"] = new_attempts
            if new_attempts >= 5:
                delete_shared_recovery_otp(db, lookup_key)
            else:
                save_shared_recovery_otp(
                    db=db,
                    username=lookup_key,
                    user_id=int(record["user_id"]),
                    expires_at=float(record["expires_at"]),
                    attempts=new_attempts,
                    otp_hash=str(record["code_hash"]),
                )
            if target_user:
                _register_failed_recovery(target_user, db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de recuperación inválido.",
            )

        user = user_repo.get_by_id(int(record["user_id"]))
        if not user:
            delete_shared_recovery_otp(db, lookup_key)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

        user.password_hash = AuthService.hash_password(req.new_password)  # type: ignore[assignment]
        user.failed_recovery_attempts = 0  # type: ignore[assignment]
        user.recovery_locked_until = None  # type: ignore[assignment]
        db.commit()
        delete_shared_recovery_otp(db, lookup_key)

        return {
            "success": True,
            "message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña.",
        }

    # Métodos offline basados en el perfil (Pregunta de Seguridad o Llave Maestra)
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo verificar la identidad del perfil indicado.",
        )

    _ensure_not_recovery_locked(target_user)

    new_rotated_key: str | None = None
    if req.method == "security_question":
        if not target_user.security_answer_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este perfil no tiene configurada una pregunta de seguridad.",
            )
        if not AuthService.verify_secret_answer(req.reset_code, str(target_user.security_answer_hash)):
            _register_failed_recovery(target_user, db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La respuesta secreta es incorrecta.",
            )
    elif req.method == "recovery_key":
        if not target_user.recovery_key_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este perfil no posee una Llave Maestra de Recuperación activa.",
            )
        normalized_key = req.reset_code.strip().upper()
        if not AuthService.verify_password(normalized_key, str(target_user.recovery_key_hash)):
            _register_failed_recovery(target_user, db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La Llave Maestra de Recuperación es inválida.",
            )
        # Rotación obligatoria tras uso único: invalidar llave consumida y emitir una nueva
        new_rotated_key = AuthService.generate_recovery_key()
        target_user.recovery_key_hash = AuthService.hash_password(new_rotated_key)  # type: ignore[assignment]

    target_user.password_hash = AuthService.hash_password(req.new_password)  # type: ignore[assignment]
    target_user.failed_recovery_attempts = 0  # type: ignore[assignment]
    target_user.recovery_locked_until = None  # type: ignore[assignment]
    db.commit()

    response_payload: dict[str, Any] = {
        "success": True,
        "message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña.",
    }
    if new_rotated_key:
        response_payload["new_recovery_key"] = new_rotated_key
    return response_payload


@router.post("/telegram", response_model=TokenResponse)
def login_telegram(
    data: TelegramAuthData,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Autentica a un usuario mediante el widget oficial de Telegram Login (SSO)."""
    payload_dict = data.model_dump(exclude_none=True)
    is_valid = verify_telegram_auth_data(
        data=payload_dict,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de Telegram inválida o datos adulterados.",
        )

    user_repo = UserRepository(db)
    telegram_id_str = str(data.id)
    user = user_repo.get_by_telegram_id(telegram_id_str)

    # Evaluar si el ID de Telegram está en la lista de administradores o traders autorizados
    is_admin_allowed = False
    is_trader_allowed = False
    try:
        tg_int = int(data.id)
        is_admin_allowed = tg_int in settings.telegram_allowed_users
        is_trader_allowed = tg_int in settings.telegram_trader_users
    except (ValueError, TypeError):
        pass

    if not user:
        # Registrar nuevo usuario con rol según whitelist
        assigned_role = "ADMIN" if is_admin_allowed else ("TRADER" if is_trader_allowed else "INVITADO")
        username = data.username or f"tg_{data.id}"
        # Generar hash aleatorio criptográfico para contraseñas de cuentas SSO puras
        random_pass = AuthService.hash_password(secrets.token_urlsafe(32))
        user = user_repo.create_user(
            username=username,
            password_hash=random_pass,
            role=assigned_role,
            telegram_id=telegram_id_str,
            is_active=True,
        )
    elif is_admin_allowed and user.role != "ADMIN":
        user_repo.update_role(int(user.id), "ADMIN")
        user = user_repo.get_by_id(int(user.id))
    elif is_trader_allowed and user.role not in ("ADMIN", "TRADER"):
        user_repo.update_role(int(user.id), "TRADER")
        user = user_repo.get_by_id(int(user.id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra inactiva o suspendida.",
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


@router.post("/telegram-webapp", response_model=TokenResponse)
def login_telegram_webapp(
    data: TelegramWebAppAuthData,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Autentica a un usuario que abre la aplicación como Telegram Mini App (TMA)."""
    parsed = verify_telegram_webapp_data(
        init_data=data.init_data,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
    )
    if not parsed or "user" not in parsed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma initData de Telegram Mini App inválida.",
        )

    tg_user = parsed["user"]
    tg_id = str(tg_user.get("id"))
    username = tg_user.get("username") or f"tg_{tg_id}"

    user_repo = UserRepository(db)
    user = user_repo.get_by_telegram_id(tg_id)

    is_admin_allowed = False
    is_trader_allowed = False
    try:
        tg_int = int(tg_id)
        is_admin_allowed = tg_int in settings.telegram_allowed_users
        is_trader_allowed = tg_int in settings.telegram_trader_users
    except (ValueError, TypeError):
        pass

    if not user:
        assigned_role = "ADMIN" if is_admin_allowed else ("TRADER" if is_trader_allowed else "INVITADO")
        random_pass = AuthService.hash_password(secrets.token_urlsafe(32))
        user = user_repo.create_user(
            username=username,
            password_hash=random_pass,
            role=assigned_role,
            telegram_id=tg_id,
            is_active=True,
        )
    elif is_admin_allowed and user.role != "ADMIN":
        user_repo.update_role(int(user.id), "ADMIN")
        user = user_repo.get_by_id(int(user.id))
    elif is_trader_allowed and user.role not in ("ADMIN", "TRADER"):
        user_repo.update_role(int(user.id), "TRADER")
        user = user_repo.get_by_id(int(user.id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva.",
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(user),
    )


@router.get("/me", response_model=UserPublicResponse)
def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPublicResponse:
    """Retorna los datos de perfil del usuario que posee la sesión activa."""
    return UserPublicResponse.model_validate(current_user)


@router.post("/recovery-profile")
def update_recovery_profile(
    req: RecoveryProfileUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Configura o actualiza correo de respaldo, nombre, pregunta secreta y Llave Maestra del usuario autenticado."""
    user_repo = UserRepository(db)

    if req.full_name is not None:
        current_user.full_name = req.full_name.strip() or None  # type: ignore[assignment]

    if req.tax_id is not None:
        current_user.tax_id = _validate_and_normalize_tax_id(req.tax_id)  # type: ignore[assignment]

    if req.email is not None:
        clean_email = _validate_and_normalize_email(req.email)
        if clean_email:
            owner = user_repo.get_by_email(clean_email)
            if owner is not None and int(owner.id) != int(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este correo electrónico ya está en uso por otro operador.",
                )
        current_user.email = clean_email  # type: ignore[assignment]

    clean_q = req.security_question.strip() if req.security_question and req.security_question.strip() else None
    clean_a = req.security_answer.strip() if req.security_answer and req.security_answer.strip() else None
    if clean_q and not clean_a and not current_user.security_answer_hash:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Debes proporcionar una respuesta secreta al definir la pregunta de seguridad.",
        )
    if clean_a:
        if len(clean_a) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="La respuesta secreta debe tener al menos 3 caracteres.",
            )
        if not clean_q and not current_user.security_question:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Debes seleccionar o escribir una pregunta de seguridad.",
            )
        if clean_q:
            current_user.security_question = clean_q  # type: ignore[assignment]
        current_user.security_answer_hash = AuthService.hash_secret_answer(clean_a)  # type: ignore[assignment]
    elif clean_q:
        current_user.security_question = clean_q  # type: ignore[assignment]

    new_plain_key: str | None = None
    if req.regenerate_recovery_key or not current_user.recovery_key_hash:
        new_plain_key = AuthService.generate_recovery_key()
        current_user.recovery_key_hash = AuthService.hash_password(new_plain_key)  # type: ignore[assignment]

    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Datos de recuperación de perfil actualizados de forma segura.",
        "user": UserPublicResponse.model_validate(current_user),
        "recovery_key": new_plain_key,
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Renueva el token de acceso para la sesión en curso."""
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(current_user.id), "username": current_user.username, "role": current_user.role},
        secret_key=settings.jwt_secret,
        expires_delta=expires_delta,
        algorithm=settings.JWT_ALGORITHM,
    )
    return TokenResponse(
        access_token=token,
        expires_in_seconds=int(expires_delta.total_seconds()),
        user=UserPublicResponse.model_validate(current_user),
    )
