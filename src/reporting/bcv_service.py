"""Servicio de consulta y registro de la tasa de cambio oficial del BCV (Banco Central de Venezuela)."""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("bcv_service")

BCV_OFFICIAL_URL = "https://www.bcv.org.ve"
BCV_FALLBACK_API = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"


class BCVService:
    """Consulta la tasa oficial del BCV directamente desde su portal web o APIs de respaldo."""

    def __init__(self, bcv_url: str = BCV_OFFICIAL_URL, fallback_api_url: str = BCV_FALLBACK_API):
        self.bcv_url = bcv_url
        self.fallback_api_url = fallback_api_url
        self._cached_rate: float | None = None
        self._cached_rates_dict: dict[str, Any] = {}

    def fetch_current_rate(self) -> float:
        """Obtiene la tasa oficial actual de USD/VES aplicando principio Fail-closed estricto."""
        # 1. Intentar scraping directo del portal oficial del BCV
        rate = self._scrape_bcv_official()
        if rate is not None and rate > 0:
            self._cached_rate = rate
            return rate

        # 2. Intentar API de respaldo
        rate_fallback = self._fetch_from_fallback_api()
        if rate_fallback is not None and rate_fallback > 0:
            self._cached_rate = rate_fallback
            return rate_fallback

        # 3. Retornar tasa cacheada previa si existe
        if self._cached_rate and self._cached_rate > 0:
            logger.warning(f"Usando tasa BCV previamente cacheada: {self._cached_rate}")
            return self._cached_rate

        # 4. Fail-closed: No fabricar valores arbitrarios ni por defecto
        logger.error("FAIL-CLOSED: No se pudo obtener la tasa oficial del BCV de ninguna fuente ni de caché.")
        return 0.0

    def get_official_rate(self) -> float:
        """Alias para fetch_current_rate que retorna la tasa oficial vigente."""
        return self.fetch_current_rate()

    def fetch_full_rates(self) -> dict[str, Any]:
        """Extrae todas las tasas publicadas por el BCV (USD, EUR, CNY, TRY, RUB y Fecha Valor)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            with httpx.Client(verify=False, timeout=12.0) as client:
                res = client.get(self.bcv_url, headers=headers)
                if res.status_code == 200:
                    html = res.text
                    parsed = self._parse_bcv_html(html)
                    if parsed.get("usd"):
                        self._cached_rates_dict = parsed
                        self._cached_rate = float(parsed["usd"])
                    return parsed
        except (httpx.RequestError, ValueError) as e:
            logger.debug(f"Error consultando tasas completas del BCV: {e}")
        if self._cached_rates_dict:
            return self._cached_rates_dict
        return {"usd": self.fetch_current_rate()}

    def _scrape_bcv_official(self) -> float | None:
        """Realiza scraping de la estructura oficial del BCV (div id='dolar')."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            with httpx.Client(verify=False, timeout=12.0) as client:
                res = client.get(self.bcv_url, headers=headers)
                if res.status_code == 200:
                    parsed = self._parse_bcv_html(res.text)
                    usd = parsed.get("usd")
                    if usd:
                        logger.info(f"Tasa oficial BCV obtenida exitosamente en vivo: {usd} VES/USD")
                        return float(usd)
        except (httpx.RequestError, ValueError) as e:
            logger.debug(f"Scraping directo BCV no disponible temporalmente: {e}")
        return None

    def _parse_bcv_html(self, html: str) -> dict[str, Any]:
        """Parsea el HTML oficial del BCV extrayendo divisas y fecha valor."""
        result: dict[str, Any] = {}
        for currency, div_id in [("usd", "dolar"), ("eur", "euro"), ("cny", "yuan"), ("try", "lira"), ("rub", "rublo")]:
            m = re.search(
                rf'id=["\']{div_id}["\'].*?<strong[^>]*>\s*([0-9.,]+)\s*</strong>',
                html,
                re.DOTALL | re.IGNORECASE
            )
            if m:
                raw_str = m.group(1).strip().replace(".", "").replace(",", ".")
                try:
                    result[currency] = float(raw_str)
                except ValueError:
                    pass

        m_date = re.search(r'date-display-single[^>]*>\s*([^<]+)\s*</span>', html, re.DOTALL | re.IGNORECASE)
        if m_date:
            result["fecha_valor"] = m_date.group(1).strip()

        return result

    def _fetch_from_fallback_api(self) -> float | None:
        """Consulta el API secundario de respaldo."""
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(self.fallback_api_url)
                if res.status_code == 200:
                    data = res.json()
                    price = data.get("price") or data.get("monitors", {}).get("usd", {}).get("price")
                    if price:
                        return float(price)
        except (httpx.RequestError, ValueError):
            pass
        return None
