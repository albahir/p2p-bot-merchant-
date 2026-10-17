"""Cliente de conexión oficial a Binance P2P con firma Ed25519, monitor de weight y sincronización de hora.
Cumple con la Constitución:
- Header x-mbx-used-weight vigilado proactivamente (< 5,000).
- Fail-closed ante 401, 403, 429 y 5xx.
- recvWindow configurado en 5000ms con compensación de deriva horaria (Clock Drift).
- Validación de respuestas con esquemas Pydantic tipados.
"""

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, cast

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.binance_schemas import (
    BinanceOrderHistoryResponse,
    BinanceSearchResponse,
    BinanceServerTime,
)

logger = logging.getLogger("binance_client")

MAX_ALLOWED_WEIGHT = 5000
WEIGHT_COOLDOWN_SECONDS = 60


class BinanceWeightExceededError(Exception):
    """Excepción lanzada cuando el peso consumido de la API supera el umbral seguro."""


class BinanceAuthError(Exception):
    """Excepción crítica lanzada cuando la API Key o firma es rechazada (Fail-Closed)."""


class BinanceP2PClient:
    """Cliente oficial para operaciones P2P en Binance con firma Ed25519 y compensación de drift."""

    def __init__(
        self,
        api_key: str,
        private_key_pem: str,
        base_url: str = "https://api.binance.com",
        recv_window: int = 5000
    ):
        self.api_key = api_key
        self.private_key_pem = private_key_pem
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window
        self.last_used_weight = 0
        self.time_offset_ms = 0  # serverTime - localTime

    def sync_time(self) -> int:
        """Sincroniza el reloj local con el servidor de Binance para evitar el error -1021."""
        url = f"{self.base_url}/api/v3/time"
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = BinanceServerTime.model_validate(res.json())
                    local_now = int(time.time() * 1000)
                    self.time_offset_ms = data.serverTime - local_now
                    logger.info(f"Sincronización horaria con Binance exitosa. Offset: {self.time_offset_ms}ms")
                    return self.time_offset_ms
        except (httpx.RequestError, ValueError) as e:
            logger.warning(f"No se pudo consultar /api/v3/time ({e}). Usando hora local.")
        return 0

    def get_synced_timestamp(self) -> int:
        """Devuelve el timestamp en milisegundos compensado con la hora del servidor."""
        return int(time.time() * 1000) + self.time_offset_ms

    def sign_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Calcula y agrega el parámetro 'signature' obligatorio utilizando la clave privada (Ed25519/RSA) o secret (HMAC)."""
        query_string = urllib.parse.urlencode(params)
        signature = self._generate_signature(query_string)
        signed = dict(params)
        signed["signature"] = signature
        return signed

    def _generate_signature(self, data: str) -> str:
        """Genera la firma criptográfica exigida por Binance sobre la cadena de parámetros urlencoded."""
        cleaned_key = self.private_key_pem.strip()
        data_bytes = data.encode("utf-8")

        # 1. Si es formato PEM (Ed25519 o RSA)
        if "-----BEGIN" in cleaned_key:
            try:
                priv_key = load_pem_private_key(cleaned_key.encode("utf-8"), password=None)
                if isinstance(priv_key, Ed25519PrivateKey):
                    raw_sig = priv_key.sign(data_bytes)
                    return base64.b64encode(raw_sig).decode("utf-8")
                elif isinstance(priv_key, RSAPrivateKey):
                    raw_sig = priv_key.sign(
                        data_bytes,
                        padding.PKCS1v15(),
                        hashes.SHA256()
                    )
                    return base64.b64encode(raw_sig).decode("utf-8")
                raise BinanceAuthError("Tipo de clave PEM no admitido: se requiere Ed25519 o RSA.")
            except Exception as e:
                raise BinanceAuthError(f"FAIL-CLOSED: Error al firmar petición con clave PEM: {e}") from e

        # 2. Si es clave secreta simétrica HMAC-SHA256 estándar de Binance
        return hmac.new(cleaned_key.encode("utf-8"), data_bytes, hashlib.sha256).hexdigest()

    def check_weight(self, headers: httpx.Headers) -> None:
        """Monitorea el header x-mbx-used-weight y aplica fail-closed preventivo si es necesario."""
        weight_str = headers.get("x-mbx-used-weight-1m") or headers.get("x-mbx-used-weight")
        if weight_str and weight_str.isdigit():
            self.last_used_weight = int(weight_str)
            logger.debug(f"API Used Weight: {self.last_used_weight}")
            if self.last_used_weight >= MAX_ALLOWED_WEIGHT:
                logger.warning(
                    f"ALERTA WEIGHT: {self.last_used_weight} >= {MAX_ALLOWED_WEIGHT}. "
                    f"Pausando por {WEIGHT_COOLDOWN_SECONDS} segundos."
                )
                time.sleep(WEIGHT_COOLDOWN_SECONDS)
                raise BinanceWeightExceededError(
                    f"FAIL-CLOSED: Límite de peso alcanzado ({self.last_used_weight})."
                )

    def _handle_response_errors(self, response: httpx.Response) -> dict[str, Any]:
        """Procesa y clasifica de forma segura los códigos de error de Binance."""
        if response.status_code in (401, 403):
            raise BinanceAuthError(
                f"FAIL-CLOSED: Rechazo de autenticación Binance (HTTP {response.status_code}): {response.text}"
            )
        response.raise_for_status()

        data = cast(dict[str, Any], response.json())
        code = str(data.get("code", "000000"))
        if code not in ("000000", "0", "200"):
            msg = data.get("message") or data.get("msg") or "Error desconocido de API Binance"
            if code in ("-1003", "100001003"):
                raise BinanceWeightExceededError(f"Rate limit de Binance alcanzado: {msg}")
            if code in ("-2014", "-2015", "100001004", "100001005"):
                raise BinanceAuthError(f"FAIL-CLOSED: Clave rechazada o IP no autorizada: {msg}")
            if code in ("-1021", "100001006"):
                # Intentar sincronizar hora ante error de timestamp
                self.sync_time()
            raise RuntimeError(f"Error Binance [{code}]: {msg}")
        return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    def get_order_book(
        self,
        asset: str = "USDT",
        fiat: str = "VES",
        trade_type: str = "BUY",
        page: int = 1,
        rows: int = 10
    ) -> BinanceSearchResponse:
        """Consulta y valida el order book público de Binance P2P con esquemas tipados."""
        url = f"{self.base_url}/sapi/v1/c2c/orderMatch/search"
        payload = {
            "asset": asset,
            "fiat": fiat,
            "tradeType": trade_type,
            "page": page,
            "rows": rows
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            self.check_weight(response.headers)
            raw_data = self._handle_response_errors(response)
            validated = BinanceSearchResponse.model_validate(raw_data)
            return cast(BinanceSearchResponse, validated)

    def get_order_history(
        self,
        trade_type: str,
        start_timestamp: int,
        end_timestamp: int,
        page: int = 1,
        rows: int = 50
    ) -> BinanceOrderHistoryResponse:
        """Consulta el histórico de órdenes con paginación de 30 días y validación de tipos."""
        thirty_days_ms = 30 * 24 * 60 * 60 * 1000
        if (end_timestamp - start_timestamp) > thirty_days_ms:
            raise ValueError("FAIL-CLOSED: La ventana de consulta histórica no puede superar los 30 días.")

        url = f"{self.base_url}/sapi/v1/c2c/orderMatch/listUserOrderHistory"
        params: dict[str, Any] = {
            "tradeType": trade_type,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "page": page,
            "rows": rows,
            "recvWindow": self.recv_window,
            "timestamp": self.get_synced_timestamp()
        }
        signed_params = self.sign_params(params)
        headers = {"X-MBX-APIKEY": self.api_key}

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=signed_params, headers=headers)
            self.check_weight(response.headers)
            raw_data = self._handle_response_errors(response)
            validated_history = BinanceOrderHistoryResponse.model_validate(raw_data)
            return cast(BinanceOrderHistoryResponse, validated_history)

    def create_ad(self, ad_payload: dict[str, Any]) -> dict[str, Any]:
        """Crea un anuncio en Binance P2P."""
        url = f"{self.base_url}/sapi/v1/c2c/ads/post"
        headers = {"X-MBX-APIKEY": self.api_key}
        payload: dict[str, Any] = {
            "recvWindow": self.recv_window,
            "timestamp": self.get_synced_timestamp(),
            **ad_payload
        }
        signed_payload = self.sign_params(payload)
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=signed_payload, headers=headers)
            self.check_weight(response.headers)
            return self._handle_response_errors(response)

    def update_ad(self, ad_no: str, update_payload: dict[str, Any]) -> dict[str, Any]:
        """Actualiza el precio o inventario de un anuncio."""
        url = f"{self.base_url}/sapi/v1/c2c/ads/update"
        headers = {"X-MBX-APIKEY": self.api_key}
        payload: dict[str, Any] = {
            "advNo": ad_no,
            "recvWindow": self.recv_window,
            "timestamp": self.get_synced_timestamp(),
            **update_payload
        }
        signed_payload = self.sign_params(payload)
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=signed_payload, headers=headers)
            self.check_weight(response.headers)
            return self._handle_response_errors(response)

    def pause_ad(self, ad_no: str) -> dict[str, Any]:
        """Pausa un anuncio propio."""
        return self.update_ad(ad_no=ad_no, update_payload={"advStatus": "PAUSED"})
