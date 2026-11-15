"""Suite TDD de auditoría criptográfica para las skills JWT (jwt-decode, jwt-encode, jwt-validate)
ejecutada bajo el protocolo del Security Reviewer (.github/agents/security.md).
"""

import base64
import json
import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from src.api.security import (
    create_access_token,
    decode_access_token,
    inspect_jwt_token,
    validate_jwt_token,
)

TEST_HMAC_SECRET = "super_secure_hmac_secret_key_for_jwt_testing_2026_32bytes!"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """Genera un par de claves RSA-2048 (PEM privado y público) en memoria para pruebas."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return priv_pem, pub_pem


@pytest.fixture(scope="module")
def ec_keypair() -> tuple[str, str]:
    """Genera un par de claves ECDSA P-256 (ES256) en memoria para pruebas."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return priv_pem, pub_pem


# =====================================================================
# 1. PRUEBAS DE SKILL: jwt-encode (HS256, RS256, ES256, kid, iat, exp)
# =====================================================================


def test_jwt_encode_hs256_includes_iat_exp_and_kid():
    """Verifica que create_access_token incluya siempre iat y exp por defecto y soporte kid."""
    token = create_access_token(
        data={"sub": "42", "username": "trader_pro", "role": "TRADER"},
        secret_key=TEST_HMAC_SECRET,
        expires_delta=timedelta(minutes=30),
        algorithm="HS256",
        headers={"kid": "hmac-key-2026"},
    )
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"
    assert header["typ"] == "JWT"
    assert header["kid"] == "hmac-key-2026"

    payload = decode_access_token(token, TEST_HMAC_SECRET, algorithm="HS256")
    assert payload is not None
    assert payload["sub"] == "42"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_jwt_encode_rs256_and_es256_asymmetric(rsa_keypair, ec_keypair):
    """Verifica codificación y validación con algoritmos asimétricos RS256 (RSA) y ES256 (ECDSA)."""
    rsa_priv, rsa_pub = rsa_keypair
    ec_priv, ec_pub = ec_keypair

    rsa_token = create_access_token(
        data={"sub": "100", "role": "ADMIN"},
        secret_key=rsa_priv,
        algorithm="RS256",
        headers={"kid": "rsa-key-1"},
    )
    rsa_decoded = decode_access_token(rsa_token, rsa_pub, algorithm="RS256")
    assert rsa_decoded is not None
    assert rsa_decoded["sub"] == "100"

    ec_token = create_access_token(
        data={"sub": "200", "role": "TRADER"},
        secret_key=ec_priv,
        algorithm="ES256",
        headers={"kid": "ec-key-1"},
    )
    ec_decoded = decode_access_token(ec_token, ec_pub, algorithm="ES256")
    assert ec_decoded is not None
    assert ec_decoded["sub"] == "200"


def test_jwt_encode_rejects_alg_none_and_empty_secret():
    """Garantiza que jwt-encode bloquee alg='none' (CVE-2015-9235) y secretos vacíos."""
    with pytest.raises(ValueError, match="algoritmo"):
        create_access_token({"sub": "1"}, secret_key=TEST_HMAC_SECRET, algorithm="none")

    with pytest.raises(ValueError, match="algoritmo"):
        create_access_token({"sub": "1"}, secret_key=TEST_HMAC_SECRET, algorithm="NONE")

    with pytest.raises(ValueError, match="secret_key"):
        create_access_token({"sub": "1"}, secret_key="", algorithm="HS256")


# =====================================================================
# 2. PRUEBAS DE SKILL: jwt-decode (Inspección, Nested JWT y Alertas)
# =====================================================================


def test_jwt_decode_valid_token_and_timestamps():
    """Verifica que inspect_jwt_token decodifique header, payload, tiempos UTC y estado de expiración."""
    now = int(time.time())
    token = jwt.encode(
        {"sub": "user|123", "iat": now - 120, "nbf": now - 60, "exp": now + 3600},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    info = inspect_jwt_token(token)
    assert info["valid_structure"] is True
    assert info["header"]["alg"] == "HS256"
    assert info["payload"]["sub"] == "user|123"
    assert info["is_expired"] is False
    assert "exp_iso" in info["timestamps"]
    assert "iat_iso" in info["timestamps"]
    assert "nbf_iso" in info["timestamps"]
    assert info["signature_verified"] is False
    assert info["risk_flags"] == []


def test_jwt_decode_flags_alg_none_missing_exp_sensitive_data_and_jku():
    """Verifica todos los chequeos de seguridad de jwt-decode:
    - alg: none (CVE-2015-9235)
    - Ausencia de exp
    - Datos sensibles en payload (password, api_key, secret)
    - Inyección de cabeceras jku / jwk / x5u
    """
    malicious_header = {
        "alg": "none",
        "typ": "JWT",
        "jku": "https://attacker.example.com/jwks.json",
        "x5u": "https://attacker.example.com/cert.pem",
    }
    malicious_payload = {
        "sub": "admin",
        "password": "PlaintextPassword123",
        "binance_api_key": "secret_key_value",
    }
    unsigned_token = (
        f"{_b64url_encode(json.dumps(malicious_header).encode())}."
        f"{_b64url_encode(json.dumps(malicious_payload).encode())}."
    )

    info = inspect_jwt_token(unsigned_token)
    assert info["valid_structure"] is True
    flags = info["risk_flags"]
    assert "ALG_NONE" in flags
    assert "MISSING_EXP" in flags
    assert "DANGEROUS_HEADER_KEY" in flags
    assert "SENSITIVE_DATA_IN_PAYLOAD" in flags
    assert any("CVE-2015-9235" in w for w in info["warnings"])


def test_jwt_decode_recursive_nested_jwt():
    """Verifica decodificación recursiva cuando el header contiene cty='JWT'."""
    inner_token = create_access_token(
        data={"sub": "inner-user", "role": "ADMIN"},
        secret_key=TEST_HMAC_SECRET,
    )
    outer_header = {"alg": "HS256", "typ": "JWT", "cty": "JWT"}
    outer_token = jwt.encode(
        {"jwt": inner_token, "exp": int(time.time()) + 1800},
        TEST_HMAC_SECRET,
        algorithm="HS256",
        headers=outer_header,
    )
    info = inspect_jwt_token(outer_token)
    assert info["valid_structure"] is True
    assert info["nested_jwt"] is not None
    assert info["nested_jwt"]["payload"]["sub"] == "inner-user"


def test_jwt_decode_malformed_tokens():
    """Verifica el reporte específico ante errores de formato (segmentos, base64, JSON)."""
    bad_segments = inspect_jwt_token("only.two")
    assert bad_segments["valid_structure"] is False
    assert "segment" in bad_segments["error"].lower()

    bad_json = inspect_jwt_token(f"{_b64url_encode(b'not-json')}.{_b64url_encode(b'{}')}.sig")
    assert bad_json["valid_structure"] is False
    assert "json" in bad_json["error"].lower()


# =====================================================================
# 3. PRUEBAS DE SKILL: jwt-validate (Estructura, Claims, Firma y JWKS)
# =====================================================================


def test_jwt_validate_rejects_token_without_exp_claim():
    """Verifica que decode_access_token y validate_jwt_token rechacen tokens sin exp aunque la firma sea válida."""
    immortal_token = jwt.encode({"sub": "1", "role": "ADMIN"}, TEST_HMAC_SECRET, algorithm="HS256")
    assert decode_access_token(immortal_token, TEST_HMAC_SECRET, algorithm="HS256") is None

    report = validate_jwt_token(immortal_token, key=TEST_HMAC_SECRET, algorithms=["HS256"])
    assert report["valid"] is False
    assert report["claims_status"] == "FAIL"


def test_jwt_validate_clock_skew_leeway_and_expiration():
    """Verifica tolerancia de clock skew (60s) y rechazo de tokens expirados fuera de ventana."""
    now = int(time.time())
    # Expiró hace 30s -> dentro de los 60s de clock skew
    skew_token = jwt.encode(
        {"sub": "1", "iat": now - 300, "exp": now - 30},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    report_ok = validate_jwt_token(
        skew_token, key=TEST_HMAC_SECRET, algorithms=["HS256"], clock_skew_seconds=60
    )
    assert report_ok["valid"] is True
    assert report_ok["result"] == "VALID"

    # Expiró hace 120s -> fuera del clock skew
    expired_token = jwt.encode(
        {"sub": "1", "iat": now - 600, "exp": now - 120},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    report_fail = validate_jwt_token(
        expired_token, key=TEST_HMAC_SECRET, algorithms=["HS256"], clock_skew_seconds=60
    )
    assert report_fail["valid"] is False
    assert report_fail["claims_status"] == "FAIL"


def test_jwt_validate_nbf_iat_and_expected_claims():
    """Verifica validación de nbf futuro, iat > 30 días de antigüedad y claims iss/aud/sub."""
    now = int(time.time())
    # 1. nbf en el futuro (dentro de 10 minutos)
    future_nbf_token = jwt.encode(
        {"sub": "1", "iat": now, "nbf": now + 600, "exp": now + 3600},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    rep_nbf = validate_jwt_token(future_nbf_token, key=TEST_HMAC_SECRET, algorithms=["HS256"])
    assert rep_nbf["valid"] is False
    assert rep_nbf["claims_status"] == "FAIL"

    # 2. iat > 30 días en el pasado (token obsoleto)
    old_iat = now - (35 * 86400)
    stale_token = jwt.encode(
        {"sub": "1", "iat": old_iat, "exp": now + 3600},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    rep_stale = validate_jwt_token(stale_token, key=TEST_HMAC_SECRET, algorithms=["HS256"])
    assert rep_stale["valid"] is True
    assert "IAT_OLDER_THAN_30_DAYS" in rep_stale["warnings"]

    # 3. Verificación de iss, aud, sub
    scoped_token = jwt.encode(
        {
            "sub": "user-99",
            "iss": "https://p2p-merchant.local",
            "aud": "p2p-api",
            "iat": now,
            "exp": now + 3600,
        },
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    rep_match = validate_jwt_token(
        scoped_token,
        key=TEST_HMAC_SECRET,
        algorithms=["HS256"],
        expected_issuer="https://p2p-merchant.local",
        expected_audience="p2p-api",
        expected_subject="user-99",
    )
    assert rep_match["valid"] is True

    rep_mismatch = validate_jwt_token(
        scoped_token,
        key=TEST_HMAC_SECRET,
        algorithms=["HS256"],
        expected_issuer="https://wrong-issuer.local",
    )
    assert rep_mismatch["valid"] is False
    assert rep_mismatch["claims_status"] == "FAIL"


def test_jwt_validate_prevents_algorithm_confusion_rs256_to_hs256(rsa_keypair):
    """Verifica bloqueo del ataque de confusión de algoritmo (firmar HS256 usando la clave pública RSA)."""
    _, rsa_pub = rsa_keypair
    now = int(time.time())
    # Un atacante toma la llave pública RSA y firma manualmente un token con HMAC-SHA256
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_b64 = _b64url_encode(
        json.dumps({"sub": "1", "role": "ADMIN", "iat": now, "exp": now + 3600}).encode()
    )
    import hashlib
    import hmac

    forged_sig = _b64url_encode(
        hmac.new(rsa_pub.encode("utf-8"), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    )
    forged_token = f"{header_b64}.{payload_b64}.{forged_sig}"

    # El validador configurado para RS256 debe rechazar rotundamente el token forjado
    assert decode_access_token(forged_token, rsa_pub, algorithm="RS256") is None
    report = validate_jwt_token(forged_token, key=rsa_pub, algorithms=["RS256"])
    assert report["valid"] is False
    assert report["signature_status"] == "FAIL"


def test_jwt_validate_with_jwks_keyset(rsa_keypair):
    """Verifica validación de firma contra un conjunto JWKS (JSON Web Key Set) por kid."""
    from jwt.algorithms import RSAAlgorithm

    rsa_priv, rsa_pub = rsa_keypair
    now = int(time.time())
    token = jwt.encode(
        {"sub": "jwks-user", "iat": now, "exp": now + 3600},
        rsa_priv,
        algorithm="RS256",
        headers={"kid": "p2p-rsa-2026"},
    )
    pub_key_obj = serialization.load_pem_public_key(rsa_pub.encode("utf-8"))
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(pub_key_obj))
    jwk_dict["kid"] = "p2p-rsa-2026"
    jwk_dict["alg"] = "RS256"
    jwks = {"keys": [jwk_dict]}

    report = validate_jwt_token(token, jwks=jwks, algorithms=["RS256"])
    assert report["valid"] is True
    assert report["signature_status"] == "PASS"
    assert report["kid"] == "p2p-rsa-2026"


def test_jwt_validate_without_key_skips_signature_and_warns():
    """Verifica que si no se provee clave ni JWKS, valide estructura y claims pero reporte firma SKIPPED."""
    now = int(time.time())
    token = jwt.encode(
        {"sub": "unverified-user", "iat": now, "exp": now + 3600},
        TEST_HMAC_SECRET,
        algorithm="HS256",
    )
    report = validate_jwt_token(token, key=None, algorithms=["HS256"])
    assert report["structure_status"] == "PASS"
    assert report["claims_status"] == "PASS"
    assert report["signature_status"] == "SKIPPED"
    assert report["signature_verified"] is False
    assert report["valid"] is False
    assert "Signature was NOT verified" in report["message"]


def test_fastapi_auth_lifecycle_with_jwt_skills():
    """Verifica el flujo completo de emisión, decodificación, validación y rechazo de JWT en las rutas de FastAPI."""
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from config.settings import Settings
    from src.api.deps import get_current_user
    from src.api.routes.auth import login, refresh_token
    from src.api.schemas.auth import LoginRequest
    from src.data.database import Base
    from src.security.auth_service import AuthService

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        settings = Settings(
            MASTER_ENCRYPTION_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            JWT_SECRET_KEY=TEST_HMAC_SECRET,
        )
        auth_svc = AuthService(db_session=session)
        auth_svc.ensure_default_admin(
            default_username="jwt_auditor", default_password="StrongPassword2026!"
        )

        # 1. Login emite JWT con sub, username, role, iat y exp
        token_resp = login(
            req=LoginRequest(username="jwt_auditor", password="StrongPassword2026!"),
            db=session,
            settings=settings,
        )
        token = token_resp.access_token

        # 2. jwt-decode: Inspeccionar sin verificar firma
        decoded_info = inspect_jwt_token(token)
        assert decoded_info["valid_structure"] is True
        assert decoded_info["payload"]["username"] == "jwt_auditor"
        assert decoded_info["payload"]["role"] == "ADMIN"
        assert "iat_iso" in decoded_info["timestamps"]
        assert "exp_iso" in decoded_info["timestamps"]
        assert decoded_info["risk_flags"] == []

        # 3. jwt-validate: Validar estructura, claims y firma
        val_report = validate_jwt_token(
            token,
            key=settings.jwt_secret,
            algorithms=[settings.JWT_ALGORITHM],
            expected_subject=str(token_resp.user.id),
        )
        assert val_report["valid"] is True
        assert val_report["result"] == "VALID"

        # 4. Dependencia FastAPI get_current_user acepta el token legítimo
        active_user = get_current_user(token=token, db=session, settings=settings)
        assert active_user.username == "jwt_auditor"

        # 5. Refresh emite un nuevo token válido
        refreshed = refresh_token(current_user=active_user, settings=settings)
        assert validate_jwt_token(refreshed.access_token, key=settings.jwt_secret)["valid"] is True

        # 6. Token adulterado con jku malicioso es bloqueado en get_current_user (HTTP 401)
        evil_token = jwt.encode(
            {"sub": str(active_user.id), "exp": int(time.time()) + 3600},
            settings.jwt_secret,
            algorithm="HS256",
            headers={"jku": "https://evil.example.com/jwks.json"},
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=evil_token, db=session, settings=settings)
        assert exc_info.value.status_code == 401
    finally:
        session.close()

