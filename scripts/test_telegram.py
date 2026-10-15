# Script de diagnóstico rápido para verificar conexión a Telegram
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from config.settings import Settings


def test_telegram_connection():
    print("==> Verificando credenciales de Telegram desde config/.env...")
    settings = Settings()
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_ALERT_CHAT_ID

    print(f"Token configurado: {token[:10]}... (longitud: {len(token)})")
    print(f"Chat ID configurado: {chat_id}")

    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN está vacío en config/.env.")
        return

    # 1. Probar getMe (validar token con Telegram)
    try:
        url_me = f"https://api.telegram.org/bot{token}/getMe"
        res = httpx.get(url_me, timeout=10.0)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            bot_info = data["result"]
            print(f"SUCCESS: Bot autenticado en Telegram -> @{bot_info.get('username')} (Nombre: {bot_info.get('first_name')})")
        else:
            print(f"FAILED getMe: Código HTTP {res.status_code} -> {data.get('description')}")
            return
    except (httpx.RequestError, ValueError) as e:
        print(f"FAILED conectando con Telegram API: {e}")
        return

    # 2. Probar sendMessage (validar chat_id con sesión persistente y reintentos)
    payload = {
        "chat_id": chat_id,
        "text": "🟢 *Conexión Exitosa*: Tu bot P2P Merchant está vinculado y listo para enviar alertas.",
        "parse_mode": "Markdown"
    }
    url_send = f"https://api.telegram.org/bot{token}/sendMessage"

    with httpx.Client(timeout=httpx.Timeout(15.0, connect=8.0)) as client:
        for attempt in range(3):
            try:
                print(f"Intento de envío {attempt + 1}/3...")
                res_send = client.post(url_send, json=payload)
                data_send = res_send.json()
                if res_send.status_code == 200 and data_send.get("ok"):
                    print("SUCCESS: ¡Mensaje de prueba recibido exitosamente en tu Telegram!")
                    return
                else:
                    print(f"FAILED sendMessage: Código HTTP {res_send.status_code} -> {data_send.get('description')}")
                    return
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                print(f"Aviso: Timeout temporal en intento {attempt + 1}: {e}")
                if attempt < 2:
                    import time
                    time.sleep(1)
            except (httpx.RequestError, ValueError) as e:
                print(f"FAILED enviando mensaje: {e}")
                return
    print("FAILED: No se pudo completar el envío tras 3 intentos. Revisa tu conexión de red o DNS.")

if __name__ == "__main__":
    test_telegram_connection()
