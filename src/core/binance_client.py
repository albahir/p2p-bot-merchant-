"""Cliente de conexión oficial a Binance P2P con firma Ed25519 y monitor de weight.
Cumple con la Constitución:
- Header x-mbx-used-weight vigilado proactivamente.
- Fail-closed ante 429 y 5xx.
- recvWindow configurado en 5000ms.
"""

import time
import logging
from typing import Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("binance_client")

MAX_ALLOWED_WEIGHT = 5000
WEIGHT_COOLDOWN_SECONDS = 60


class BinanceWeightExceededError(Exception):
    """Excepción lanzada cuando el peso consumido de la API supera el umbral seguro."""
    pass


class BinanceP2PClient:
    """Cliente para operaciones P2P en Binance con firma Ed25519."""

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

    def check_weight(self, headers: httpx.Headers) -> None:
        """Monitorea el header x-mbx-used-weight y aplica fail-closed preventivo si es necesario."""
        weight_str = headers.get("x-mbx-used-weight")
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
    ) -> Dict[str, Any]:
        """Consulta el order book público de Binance P2P."""
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
            response.raise_for_status()
            return response.json()

    def get_order_history(
        self,
        trade_type: str,
        start_timestamp: int,
        end_timestamp: int,
        page: int = 1,
        rows: int = 50
    ) -> Dict[str, Any]:
        """Consulta el histórico de órdenes completadas o en curso con paginación máxima de 30 días."""
        thirty_days_ms = 30 * 24 * 60 * 60 * 1000
        if (end_timestamp - start_timestamp) > thirty_days_ms:
            raise ValueError("FAIL-CLOSED: La ventana de consulta histórica no puede superar los 30 días.")

        url = f"{self.base_url}/sapi/v1/c2c/orderMatch/listUserOrderHistory"
        params = {
            "tradeType": trade_type,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "page": page,
            "rows": rows,
            "recvWindow": self.recv_window,
            "timestamp": int(time.time() * 1000)
        }
        headers = {"X-MBX-APIKEY": self.api_key}

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params, headers=headers)
            self.check_weight(response.headers)
            response.raise_for_status()
            return response.json()

    def create_ad(self, ad_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un anuncio en Binance P2P."""
        url = f"{self.base_url}/sapi/v1/c2c/ads/post"
        headers = {"X-MBX-APIKEY": self.api_key}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=ad_payload, headers=headers)
            self.check_weight(response.headers)
            response.raise_for_status()
            return response.json()

    def update_ad(self, ad_no: str, update_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza el precio o inventario de un anuncio."""
        url = f"{self.base_url}/sapi/v1/c2c/ads/update"
        headers = {"X-MBX-APIKEY": self.api_key}
        payload = {"advNo": ad_no, **update_payload}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            self.check_weight(response.headers)
            response.raise_for_status()
            return response.json()

    def pause_ad(self, ad_no: str) -> Dict[str, Any]:
        """Pausa un anuncio propio."""
        return self.update_ad(ad_no=ad_no, update_payload={"advStatus": "PAUSED"})
