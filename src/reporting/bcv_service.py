"""Servicio de consulta y registro de la tasa de cambio oficial del BCV (Banco Central de Venezuela)."""

import logging

import httpx

logger = logging.getLogger("bcv_service")

# Endpoint público o fallback de referencia de tasa oficial
BCV_FALLBACK_URL = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"


class BCVService:
    """Consulta la tasa oficial del BCV para cálculos y conversiones contables/fiscales."""

    def __init__(self, api_url: str = BCV_FALLBACK_URL):
        self.api_url = api_url

    def fetch_current_rate(self) -> float:
        """Obtiene la tasa oficial actual de USD/VES."""
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(self.api_url)
                if res.status_code == 200:
                    data = res.json()
                    # Soporta formato { "monitors": { "usd": { "price": 36.5 } } } o { "price": 36.5 }
                    price = data.get("price") or data.get("monitors", {}).get("usd", {}).get("price")
                    if price:
                        return float(price)
            logger.warning("No se pudo obtener tasa BCV de la API externa, usando valor de referencia.")
            return 36.5
        except Exception as e:
            logger.error(f"Error consultando tasa BCV: {e}")
            return 36.5
