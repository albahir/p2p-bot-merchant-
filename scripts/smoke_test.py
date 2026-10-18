"""Script de Smoke Testing operacional y verificación de salud post-despliegue.
Valida:
1. Primitivas Criptográficas (AES-256-GCM y Ed25519).
2. Integridad de importación del grafo de módulos.
3. Conexión e inicialización de esquemas de Base de Datos.
4. Sincronización horaria (Anti Clock Drift Binance -1021).
5. Endpoint de salud de UI / Dashboard (Streamlit).
"""

import argparse
import os
import sys
import time

# Asegurar compatibilidad de encoding en Windows y Linux
reconf = getattr(sys.stdout, "reconfigure", None)
if callable(reconf):
    try:
        reconf(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        pass


def log_step(name: str, status: str, details: str = "") -> None:
    badge = "[PASS]" if status == "OK" else "[FAIL]" if status == "FAIL" else "[WARN]"
    print(f"{badge:<8} {name:<35} {details}")


def verify_crypto_engine() -> bool:
    """Verifica que las primitivas criptográficas del bot operen con normalidad."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # 1. Test AES-256-GCM
        key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = b"p2p-bot-smoke-test-payload"
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        if decrypted != plaintext:
            log_step("Crypto: AES-256-GCM", "FAIL", "Fallo de descifrado en memoria")
            return False

        # 2. Test Ed25519
        priv_key = ed25519.Ed25519PrivateKey.generate()
        pub_key = priv_key.public_key()
        signature = priv_key.sign(plaintext)
        pub_key.verify(signature, plaintext)

        log_step("Crypto: AES-256-GCM & Ed25519", "OK", "Primitivas criptograficas verificadas")
        return True
    except Exception as e:  # noqa: BLE001
        log_step("Crypto: AES-256-GCM & Ed25519", "FAIL", str(e))
        return False


def verify_module_imports() -> bool:
    """Verifica que todos los componentes críticos del bot se importen sin fallos."""
    modules_to_test = [
        "src.core.binance_client",
        "src.security.api_key_manager",
        "src.security.audit_logger",
        "src.security.identity_service",
        "src.reporting.tax_engine",
        "src.reporting.excel_reporter",
        "src.reporting.sheets_exporter",
        "src.reporting.monthly_closer",
        "src.integrations.telegram_notifier",
    ]
    all_ok = True
    for mod in modules_to_test:
        try:
            __import__(mod)
            log_step(f"Import: {mod}", "OK")
        except Exception as e:  # noqa: BLE001
            log_step(f"Import: {mod}", "FAIL", str(e))
            all_ok = False
    return all_ok


def verify_database() -> bool:
    """Verifica que la base de datos pueda ser conectada e inicializada."""
    try:
        from sqlalchemy import create_engine

        from src.data.database import Base

        db_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        log_step("Database: Schema Init", "OK", f"Conectado a {db_url.split('@')[-1]}")
        return True
    except Exception as e:  # noqa: BLE001
        log_step("Database: Schema Init", "FAIL", str(e))
        return False


def verify_clock_drift() -> bool:
    """Verifica la desincronización de reloj con Binance/NTP para evitar error -1021."""
    try:
        import httpx

        client = httpx.Client(timeout=4.0)
        t_before = time.time() * 1000
        resp = client.get("https://api.binance.com/api/v3/time")
        t_after = time.time() * 1000

        if resp.status_code == 200:
            server_time = resp.json().get("serverTime")
            local_time = (t_before + t_after) / 2
            drift_ms = abs(local_time - server_time)

            if drift_ms > 1000:
                log_step("Clock Sync: Binance API", "WARN", f"Desfase horario alto: {drift_ms:.1f}ms (>1000ms)")
                return False
            log_step("Clock Sync: Binance API", "OK", f"Desfase horario optimo: {drift_ms:.1f}ms")
            return True
        log_step("Clock Sync: Binance API", "WARN", f"Status {resp.status_code} al consultar hora oficial")
        return True
    except Exception as e:  # noqa: BLE001
        log_step("Clock Sync: Binance API", "WARN", f"No se pudo consultar hora externa: {e}")
        return True


def verify_dashboard_health(host: str = "http://localhost:8501") -> bool:
    """Verifica el endpoint de salud de Streamlit si está en ejecución."""
    try:
        import httpx

        client = httpx.Client(timeout=3.0)
        resp = client.get(f"{host}/_stcore/health")
        if resp.status_code == 200:
            log_step("Dashboard: Streamlit Health", "OK", "HTTP 200 OK")
            return True
        log_step("Dashboard: Streamlit Health", "WARN", f"Respondio con HTTP {resp.status_code}")
        return False
    except Exception:  # noqa: BLE001
        log_step("Dashboard: Streamlit Health", "WARN", "Servicio no detectado en puerto local (Omitido en CI/build)")
        return True


def run_smoke_tests(stage: str, check_ui: bool = False) -> bool:
    print("\n==================================================")
    print(f"INICIANDO SMOKE TESTS OPERACIONALES - STAGE: {stage.upper()}")
    print("==================================================\n")

    results = [
        verify_crypto_engine(),
        verify_module_imports(),
        verify_database(),
        verify_clock_drift(),
    ]

    if check_ui:
        results.append(verify_dashboard_health())

    overall_success = all(results)
    print("\n--------------------------------------------------")
    if overall_success:
        print("TODOS LOS SMOKE TESTS PASARON EXITOSAMENTE.")
    else:
        print("AL MENOS UN SMOKE TEST CRITICO HA FALLADO.")
    print("--------------------------------------------------\n")
    return overall_success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke Tests Operacionales p2p-bot-merchant")
    parser.add_argument("--stage", default="local", help="Etapa de ejecucion (local, staging, production)")
    parser.add_argument("--check-ui", action="store_true", help="Verificar endpoint de salud de Streamlit")
    args = parser.parse_args()

    success = run_smoke_tests(stage=args.stage, check_ui=args.check_ui)
    sys.exit(0 if success else 1)
