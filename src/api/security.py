"""Seguridad criptográfica para la API REST: JWT (encode, decode, validate) y Telegram SSO."""

import base64
import hashlib
import hmac
import json
import logging
import re
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWKSet

logger = logging.getLogger("api_security")

_DANGEROUS_HEADER_KEYS = {"jku", "jwk", "x5u"}
_SENSITIVE_CLAIM_PATTERN = re.compile(
    r"(password|passwd|pwd|secret|api_key|apikey|private_key|bot_token|master_key|otp|credit_card|cvv)",
    re.IGNORECASE,
)
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")


def _b64url_decode(segment: str) -> bytes:
    """Decodifica un segmento base64url validando caracteres permitidos."""
    if not _B64URL_RE.match(segment):
        raise ValueError("Invalid base64url characters in segment")
    padding = len(segment) % 4
    if padding == 1:
        raise ValueError("Invalid base64url segment length")
    if padding:
        segment += "=" * (4 - padding)
    return base64.urlsafe_b64decode(segment.encode("ascii"))


def _ts_to_iso(value: Any) -> str | None:
    """Convierte un timestamp Unix numérico a cadena ISO-8601 UTC."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    return None


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    expires_delta: timedelta | None = None,
    algorithm: str = "HS256",
    headers: dict[str, Any] | None = None,
) -> str:
    """Genera un JWT firmado con payload de usuario, iat y fecha de expiración (jwt-encode)."""
    if not secret_key or not str(secret_key).strip():
        raise ValueError("El parámetro secret_key no puede estar vacío.")
    if not algorithm or algorithm.strip().lower() == "none":
        raise ValueError("El algoritmo 'none' está prohibido por seguridad (CVE-2015-9235).")

    to_encode = data.copy()
    now = datetime.now(UTC)
    if "iat" not in to_encode:
        to_encode["iat"] = int(now.timestamp())
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=60)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, secret_key, algorithm=algorithm, headers=headers)


def inspect_jwt_token(token: str, _depth: int = 0) -> dict[str, Any]:
    """Decodifica e inspecciona un JWT sin verificar su firma ejecutando auditoría estática (jwt-decode)."""
    if not isinstance(token, str) or not token.strip():
        return {
            "valid_structure": False,
            "error": "Empty token string",
            "signature_verified": False,
        }

    parts = token.strip().split(".")
    if len(parts) != 3:
        return {
            "valid_structure": False,
            "error": f"Wrong segment count: expected 3 dot-separated parts, got {len(parts)}",
            "signature_verified": False,
        }

    header_b64, payload_b64, signature_b64 = parts
    try:
        raw_header = _b64url_decode(header_b64)
        raw_payload = _b64url_decode(payload_b64)
    except (ValueError, TypeError) as exc:
        return {
            "valid_structure": False,
            "error": f"Malformed base64url encoding: {exc}",
            "signature_verified": False,
        }

    try:
        header = json.loads(raw_header.decode("utf-8"))
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "valid_structure": False,
            "error": f"Invalid JSON in token segment: {exc}",
            "signature_verified": False,
        }

    if not isinstance(header, dict) or not isinstance(payload, dict):
        return {
            "valid_structure": False,
            "error": "Invalid JSON structure: header and payload must be JSON objects",
            "signature_verified": False,
        }

    risk_flags: list[str] = []
    warnings: list[str] = []

    alg = str(header.get("alg", "")).strip()
    if not alg or alg.lower() == "none":
        risk_flags.append("ALG_NONE")
        warnings.append(
            "This token has no signature (alg: none) and cannot be trusted (CVE-2015-9235)."
        )

    dangerous_found = sorted(_DANGEROUS_HEADER_KEYS.intersection(header.keys()))
    if dangerous_found:
        risk_flags.append("DANGEROUS_HEADER_KEY")
        warnings.append(
            f"Header contains external key parameters ({', '.join(dangerous_found)}) that can enable SSRF or key injection."
        )

    now_ts = time.time()
    timestamps: dict[str, str] = {}
    for claim_name in ("exp", "nbf", "iat"):
        iso_val = _ts_to_iso(payload.get(claim_name))
        if iso_val:
            timestamps[f"{claim_name}_iso"] = iso_val

    is_expired = False
    if "exp" not in payload:
        risk_flags.append("MISSING_EXP")
        warnings.append("Token has no 'exp' claim and never expires.")
    else:
        exp_val = payload.get("exp")
        if isinstance(exp_val, (int, float)) and not isinstance(exp_val, bool):
            is_expired = now_ts > float(exp_val)

    sensitive_keys = [k for k in payload if _SENSITIVE_CLAIM_PATTERN.search(str(k))]
    if sensitive_keys:
        risk_flags.append("SENSITIVE_DATA_IN_PAYLOAD")
        warnings.append(
            f"Sensitive claim names detected in unencrypted JWT payload: {', '.join(sensitive_keys)}"
        )

    nested_jwt: dict[str, Any] | None = None
    if str(header.get("cty", "")).upper() == "JWT" and _depth < 3:
        candidate = payload.get("jwt") or payload.get("token") or payload.get("sub")
        if isinstance(candidate, str) and candidate.count(".") == 2:
            nested_jwt = inspect_jwt_token(candidate, _depth=_depth + 1)

    return {
        "valid_structure": True,
        "header": header,
        "payload": payload,
        "signature": signature_b64,
        "timestamps": timestamps,
        "is_expired": is_expired,
        "risk_flags": risk_flags,
        "warnings": warnings,
        "nested_jwt": nested_jwt,
        "signature_verified": False,
    }


def validate_jwt_token(
    token: str,
    key: str | bytes | None = None,
    algorithms: list[str] | None = None,
    jwks: dict[str, Any] | None = None,
    clock_skew_seconds: int = 60,
    expected_issuer: str | None = None,
    expected_audience: str | None = None,
    expected_subject: str | None = None,
    max_iat_age_days: int = 30,
) -> dict[str, Any]:
    """Verifica la estructura, claims temporales y firma criptográfica de un JWT (jwt-validate)."""
    inspected = inspect_jwt_token(token)
    if not inspected.get("valid_structure"):
        return {
            "valid": False,
            "structure_status": "FAIL",
            "claims_status": "SKIPPED",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": f"INVALID — {inspected.get('error', 'malformed structure')}",
            "message": str(inspected.get("error", "Malformed JWT")),
            "warnings": [],
        }

    header: dict[str, Any] = inspected["header"]
    payload: dict[str, Any] = inspected["payload"]
    warnings: list[str] = list(inspected.get("warnings", []))

    # 1. Validación estricta de estructura y cabecera
    alg = str(header.get("alg", "")).strip()
    if not alg or alg.lower() == "none":
        return {
            "valid": False,
            "structure_status": "FAIL",
            "claims_status": "SKIPPED",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — alg: none is forbidden (CVE-2015-9235)",
            "message": "Token uses alg: none and cannot be trusted.",
            "warnings": warnings,
        }

    if "DANGEROUS_HEADER_KEY" in inspected.get("risk_flags", []):
        return {
            "valid": False,
            "structure_status": "FAIL",
            "claims_status": "SKIPPED",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — untrusted key header parameter (jku/jwk/x5u)",
            "message": "Token contains dangerous header key injection parameters.",
            "warnings": warnings,
        }

    # 2. Validación de Claims (exp, nbf, iat, iss, aud, sub) con tolerancia de clock skew
    now_ts = time.time()
    exp_val = payload.get("exp")
    if not isinstance(exp_val, (int, float)) or isinstance(exp_val, bool):
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "FAIL",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — missing or non-numeric exp claim",
            "message": "Missing required 'exp' claim.",
            "warnings": warnings,
        }

    if now_ts > (float(exp_val) + clock_skew_seconds):
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "FAIL",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — token expired",
            "message": f"Token expired at {_ts_to_iso(exp_val)}",
            "warnings": warnings,
        }

    if "nbf" in payload:
        nbf_val = payload.get("nbf")
        if not isinstance(nbf_val, (int, float)) or isinstance(nbf_val, bool) or (now_ts + clock_skew_seconds) < float(nbf_val):
            return {
                "valid": False,
                "structure_status": "PASS",
                "claims_status": "FAIL",
                "signature_status": "SKIPPED",
                "signature_verified": False,
                "result": "INVALID — token not yet valid (nbf in future)",
                "message": "Token nbf claim is in the future.",
                "warnings": warnings,
            }

    if "iat" in payload:
        iat_val = payload.get("iat")
        if not isinstance(iat_val, (int, float)) or isinstance(iat_val, bool) or float(iat_val) > (now_ts + clock_skew_seconds):
            return {
                "valid": False,
                "structure_status": "PASS",
                "claims_status": "FAIL",
                "signature_status": "SKIPPED",
                "signature_verified": False,
                "result": "INVALID — iat claim is in the future",
                "message": "Token iat claim is in the future.",
                "warnings": warnings,
            }
        if (now_ts - float(iat_val)) > (max_iat_age_days * 86400):
            warnings.append("IAT_OLDER_THAN_30_DAYS")

    if expected_issuer is not None and payload.get("iss") != expected_issuer:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "FAIL",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — issuer (iss) mismatch",
            "message": "Token issuer does not match expected_issuer.",
            "warnings": warnings,
        }

    if expected_audience is not None:
        aud_claim = payload.get("aud")
        aud_ok = (aud_claim == expected_audience) or (
            isinstance(aud_claim, list) and expected_audience in aud_claim
        )
        if not aud_ok:
            return {
                "valid": False,
                "structure_status": "PASS",
                "claims_status": "FAIL",
                "signature_status": "SKIPPED",
                "signature_verified": False,
                "result": "INVALID — audience (aud) mismatch",
                "message": "Token audience does not match expected_audience.",
                "warnings": warnings,
            }

    if expected_subject is not None and payload.get("sub") != expected_subject:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "FAIL",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "result": "INVALID — subject (sub) mismatch",
            "message": "Token subject does not match expected_subject.",
            "warnings": warnings,
        }

    # 3. Verificación criptográfica de firma (nunca confiar en el header alg sin allowlist)
    allowed_algs = [a.strip() for a in (algorithms or ["HS256"]) if a and a.strip().lower() != "none"]
    if not allowed_algs:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "PASS",
            "signature_status": "FAIL",
            "signature_verified": False,
            "result": "INVALID — no safe algorithms configured in allowlist",
            "message": "Algorithm allowlist cannot be empty or 'none'.",
            "warnings": warnings,
        }

    if key is None and jwks is None:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "PASS",
            "signature_status": "SKIPPED",
            "signature_verified": False,
            "payload": payload,
            "result": "UNVERIFIED — Signature was NOT verified",
            "message": "Signature was NOT verified — token authenticity is unknown.",
            "warnings": warnings,
        }

    if alg not in allowed_algs:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "PASS",
            "signature_status": "FAIL",
            "signature_verified": False,
            "result": f"INVALID — algorithm '{alg}' not in allowlist {allowed_algs}",
            "message": f"Algorithm '{alg}' is not permitted by allowlist.",
            "warnings": warnings,
        }

    verification_key: Any = key
    kid = header.get("kid")
    if jwks is not None:
        try:
            jwk_set = PyJWKSet.from_dict(jwks)
            selected_jwk = None
            for item in jwk_set.keys:
                if kid and item.key_id == kid:
                    selected_jwk = item
                    break
            if selected_jwk is None and len(jwk_set.keys) == 1:
                selected_jwk = jwk_set.keys[0]
            if selected_jwk is None:
                return {
                    "valid": False,
                    "structure_status": "PASS",
                    "claims_status": "PASS",
                    "signature_status": "FAIL",
                    "signature_verified": False,
                    "result": "INVALID — matching key not found in JWKS",
                    "message": "No matching key found in JWKS.",
                    "warnings": warnings,
                }
            verification_key = selected_jwk.key
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            return {
                "valid": False,
                "structure_status": "PASS",
                "claims_status": "PASS",
                "signature_status": "FAIL",
                "signature_verified": False,
                "result": f"INVALID — JWKS error: {exc}",
                "message": str(exc),
                "warnings": warnings,
            }

    try:
        verified_payload = jwt.decode(
            token,
            verification_key,
            algorithms=allowed_algs,
            leeway=clock_skew_seconds,
            options={
                "require": ["exp"],
                "verify_aud": expected_audience is not None,
                "verify_iss": expected_issuer is not None,
            },
            audience=expected_audience,
            issuer=expected_issuer,
        )
        return {
            "valid": True,
            "structure_status": "PASS",
            "claims_status": "PASS",
            "signature_status": "PASS",
            "signature_verified": True,
            "algorithm": alg,
            "kid": kid,
            "payload": verified_payload,
            "result": "VALID",
            "message": "Token structure, claims, and cryptographic signature verified.",
            "warnings": warnings,
        }
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        return {
            "valid": False,
            "structure_status": "PASS",
            "claims_status": "PASS",
            "signature_status": "FAIL",
            "signature_verified": False,
            "result": f"INVALID — {exc}",
            "message": str(exc),
            "warnings": warnings,
        }


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any] | None:
    """Verifica y decodifica un JWT con validación Fail-closed de cabecera, exp y algoritmo."""
    if not token or not secret_key or not algorithm or algorithm.strip().lower() == "none":
        return None
    try:
        unverified_header = jwt.get_unverified_header(token)
        header_alg = str(unverified_header.get("alg", "")).strip()
        if not header_alg or header_alg.lower() == "none" or header_alg != algorithm:
            return None
        if _DANGEROUS_HEADER_KEYS.intersection(unverified_header.keys()):
            return None
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"require": ["exp"]},
        )
        return payload
    except (jwt.PyJWTError, ValueError, TypeError) as err:
        logger.debug("Token JWT inválido o expirado: %s", err)
        return None


def verify_telegram_auth_data(
    data: dict[str, Any],
    bot_token: str,
    max_age_seconds: int = 86400,
) -> bool:
    """Valida los datos y la firma HMAC-SHA256 del widget oficial de Telegram Login."""
    if "hash" not in data or not bot_token:
        return False

    received_hash = str(data["hash"])
    auth_date_str = str(data.get("auth_date", "0"))
    try:
        auth_date = int(auth_date_str)
        if (time.time() - auth_date) > max_age_seconds:
            return False
    except (ValueError, TypeError):
        return False

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    data_check_list = [f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"]
    data_check_string = "\n".join(data_check_list)
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)


def verify_telegram_webapp_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, Any] | None:
    """Valida los datos `initData` de Telegram Mini App (TMA). Retorna los parámetros verificados."""
    if not init_data or not bot_token:
        return None

    try:
        parsed_qsl = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        params = dict(parsed_qsl)
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None

        auth_date_str = params.get("auth_date", "0")
        try:
            auth_date = int(auth_date_str)
            if (time.time() - auth_date) > max_age_seconds:
                return None
        except (ValueError, TypeError):
            return None

        # Mini App: secret_key = HMAC_SHA256(b"WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        data_check_list = [f"{k}={v}" for k, v in sorted(params.items())]
        data_check_string = "\n".join(data_check_list)
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        result: dict[str, Any] = dict(params)
        if "user" in result and isinstance(result["user"], str):
            try:
                result["user"] = json.loads(result["user"])
            except json.JSONDecodeError:
                pass
        return result
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as err:
        logger.debug("Error procesando Telegram WebApp initData: %s", err)
        return None
