import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

logger = logging.getLogger("spread_monitor")


@dataclass
class BankRateQuote:
    """Cotización de tasas de compra y venta P2P para un banco o método de pago."""
    bank_name: str
    buy_rate: float       # Tasa a la que compras USDT (entregas Bs)
    sell_rate: float      # Tasa a la que vendes USDT (recibes Bs)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_ads: int = 0
    score: float = 0.0
    liquidity_pct: float = 0.0
    binance_code: str = ""
    exchanges: list[str] = field(default_factory=lambda: ["binance"])
    source: str = "binance"


    @property
    def spread_ves(self) -> float:
        return round(self.sell_rate - self.buy_rate, 4)

    @property
    def spread_pct(self) -> float:
        if self.buy_rate <= 0:
            return 0.0
        return round((self.spread_ves / self.buy_rate) * 100, 4)


@dataclass
class NetProfitCalculation:
    """Resultado desglosado de rentabilidad neta real de un ciclo comercial P2P."""
    crypto_amount: float
    buy_price: float
    sell_price: float
    gross_buy_ves: float
    gross_sell_ves: float
    binance_fee_ves: float
    bank_fee_buy_ves: float
    bank_fee_sell_ves: float
    net_profit_ves: float
    net_profit_usdt: float
    gross_spread_pct: float
    net_spread_pct: float
    is_profitable: bool
    is_viable: bool
    warning_level: str
    warning_message: str


class SpreadMonitor:
    """Servicio de monitoreo de spread, arbitraje interbancario y alertas de rentabilidad."""

    MIN_VIABLE_SPREAD_PCT: float = 0.80  # Regla de oro para operar en Bolívares

    @classmethod
    def calculate_cycle_net_profit(
        cls,
        crypto_amount: float,
        buy_price: float,
        sell_price: float,
        binance_maker_fee_pct: float = 0.0035,  # 0.35% estándar Maker
        bank_fee_pct: float = 0.003,            # 0.30% comisión interbancaria Pago Móvil
    ) -> NetProfitCalculation:
        """Calcula la ganancia neta real descontando comisiones de Binance y comisiones bancarias."""
        gross_buy = crypto_amount * buy_price
        gross_sell = crypto_amount * sell_price

        # Comisión de Binance (en VES equivalente sobre la venta o por anuncio)
        binance_fee = gross_sell * binance_maker_fee_pct

        # Comisiones bancarias (0.3% al enviar Bs en compra y 0.3% al recibir o transferir)
        bank_fee_buy = gross_buy * bank_fee_pct
        bank_fee_sell = gross_sell * bank_fee_pct

        total_costs_ves = gross_buy + binance_fee + bank_fee_buy + bank_fee_sell
        net_profit_ves = round(gross_sell - total_costs_ves, 2)

        # Retorno equivalente en USDT (recomprando a la tasa de compra)
        net_profit_usdt = round(net_profit_ves / buy_price, 4) if buy_price > 0 else 0.0

        # Spreads porcentuales
        gross_spread_pct = round(((sell_price - buy_price) / buy_price) * 100, 2) if buy_price > 0 else 0.0
        net_spread_pct = round((net_profit_ves / gross_buy) * 100, 2) if gross_buy > 0 else 0.0

        is_profitable = net_profit_ves > 0
        is_viable = gross_spread_pct >= cls.MIN_VIABLE_SPREAD_PCT and is_profitable

        warning_level = "OK"
        warning_msg = "Margen operativo saludable."

        if not is_profitable:
            warning_level = "LOSS"
            warning_msg = "Operación a PÉRDIDA. Las comisiones bancarias y de Binance superan el spread bruto."
        elif not is_viable:
            warning_level = "CRITICAL_MARGIN"
            warning_msg = (
                f"Alerta: Spread bruto ({gross_spread_pct:.2f}%) inferior al mínimo recomendado del "
                f"{cls.MIN_VIABLE_SPREAD_PCT:.2f}%. Alto riesgo de rentabilidad nula tras costos ocultos."
            )

        return NetProfitCalculation(
            crypto_amount=crypto_amount,
            buy_price=buy_price,
            sell_price=sell_price,
            gross_buy_ves=round(gross_buy, 2),
            gross_sell_ves=round(gross_sell, 2),
            binance_fee_ves=round(binance_fee, 2),
            bank_fee_buy_ves=round(bank_fee_buy, 2),
            bank_fee_sell_ves=round(bank_fee_sell, 2),
            net_profit_ves=net_profit_ves,
            net_profit_usdt=net_profit_usdt,
            gross_spread_pct=gross_spread_pct,
            net_spread_pct=net_spread_pct,
            is_profitable=is_profitable,
            is_viable=is_viable,
            warning_level=warning_level,
            warning_message=warning_msg,
        )

    @staticmethod
    def calculate_bcv_gap(p2p_price: float, bcv_rate: float) -> float:
        """Calcula el porcentaje de brecha cambiaria entre el mercado P2P y la tasa oficial del BCV."""
        if bcv_rate <= 0:
            return 0.0
        return round(((p2p_price - bcv_rate) / bcv_rate) * 100, 2)

    def generate_arbitrage_matrix(self, quotes: list[BankRateQuote]) -> list[dict[str, Any]]:
        """Genera una matriz comparativa banco por banco con spreads y rentabilidades estimadas."""
        matrix: list[dict[str, Any]] = []
        for q in quotes:
            calc = self.calculate_cycle_net_profit(
                crypto_amount=100.0,
                buy_price=q.buy_rate,
                sell_price=q.sell_rate,
            )
            matrix.append({
                "bank": q.bank_name,
                "buy_rate": q.buy_rate,
                "sell_rate": q.sell_rate,
                "spread_ves": q.spread_ves,
                "spread_pct": q.spread_pct,
                "est_profit_ves_100u": calc.net_profit_ves,
                "is_viable": calc.is_viable,
                "warning_level": calc.warning_level,
            })
        return sorted(matrix, key=lambda x: x["spread_pct"], reverse=True)

    def find_best_cross_arbitrage(self, quotes: list[BankRateQuote]) -> dict[str, Any] | None:
        """Encuentra la mejor oportunidad de arbitraje interbancario (comprar en banco A y vender en banco B distinto)."""
        if not quotes or len(quotes) < 2:
            return None

        best_cross: dict[str, Any] | None = None
        best_spread_pct = -999.0

        for q_buy in quotes:
            for q_sell in quotes:
                # El arbitraje cruzado requiere entidades o métodos distintos
                if q_buy.bank_name == q_sell.bank_name or q_buy.buy_rate <= 0 or q_sell.sell_rate <= 0:
                    continue

                spread_ves = round(q_sell.sell_rate - q_buy.buy_rate, 4)
                spread_pct = round((spread_ves / q_buy.buy_rate) * 100, 2)

                if spread_pct > best_spread_pct:
                    calc = self.calculate_cycle_net_profit(
                        crypto_amount=100.0,
                        buy_price=q_buy.buy_rate,
                        sell_price=q_sell.sell_rate,
                    )
                    best_spread_pct = spread_pct
                    best_cross = {
                        "buy_bank": q_buy.bank_name,
                        "buy_rate": q_buy.buy_rate,
                        "sell_bank": q_sell.bank_name,
                        "sell_rate": q_sell.sell_rate,
                        "spread_ves": spread_ves,
                        "spread_pct": spread_pct,
                        "net_profit_ves_100u": calc.net_profit_ves,
                        "is_viable": calc.is_viable,
                        "buy_source": getattr(q_buy, "source", "unknown"),
                        "sell_source": getattr(q_sell, "source", "unknown"),
                    }

        return best_cross

    BANK_PAY_TYPE_MAP: ClassVar[dict[str, str]] = {
        "Banco de Venezuela": "SpecificBank",
        "Banesco": "Banesco",
        "Pago Móvil": "PagoMovil",
        "Mercantil": "Mercantil",
        "Bancamiga": "Bancamiga",
        "BBVA Banco Provincial": "BBVABancoProvincial",
        "BNC Banco Nacional de Crédito": "BancoNacionaldeCredito",
        "Banco Activo": "BancoActivo",
    }

    # Mapa de los 21 métodos de pago oficiales de Binance P2P detectados en Venezuela
    BINANCE_METHODS_MAP: ClassVar[dict[str, str]] = {
        "Pago Móvil": "PagoMovil",
        "Banesco": "Banesco",
        "Banco de Venezuela": "BancoDeVenezuela",
        "Mercantil": "Mercantil",
        "Transferencia Bancaria (BANK)": "BANK",
        "BBVA Provincial": "Provincial",
        "BNC Banco Nacional de Crédito": "BNCBancoNacional",
        "Bancamiga": "Bancamiga",
        "BBVA Bank": "BBVABank",
        "Bancaribe": "Bancaribe",
        "Banco del Tesoro": "BancoDelTesoro",
        "Banco Venezolano de Crédito": "BancoVeneCredit",
        "BDDT Banco Digital": "BDDT",
        "Banplus": "Banplus",
        "Specific Bank": "SpecificBank",
        "Banco Plaza": "BancoPlaza",
        "BFC Banco Fondo Común": "BFC",
        "Banco Activo": "BancoActivo",
        "Recarga Pines": "RecargaPines",
        "R4 Banco Microfinanciero": "R4",
        "N58 Banco Digital": "N58",
    }

    @staticmethod
    def _normalize_bank_name(raw_name: str) -> str:
        """Normaliza nombres crudos devueltos por APIs externas al nombre institucional estándar."""
        mapping = {
            "BancoDeVenezuela": "Banco de Venezuela",
            "BNCBancoNacional": "BNC Banco Nacional de Crédito",
            "Provincial": "BBVA Provincial",
            "BBVABank": "BBVA Provincial",
            "BANK": "Transferencia Bancaria",
            "BancoDelTesoro": "Banco del Tesoro",
            "BancoVeneCredit": "Banco Venezolano de Crédito",
            "BDDT": "Banco Digital de los Trabajadores",
            "BFC": "BFC Banco Fondo Común",
            "BancoActivo": "Banco Activo",
            "BancoPlaza": "Banco Plaza",
            "R4": "R4 Banco Microfinanciero",
            "N58": "N58 Banco Digital",
            "SpecificBank": "Banco de Venezuela (Transfers)",
        }
        return mapping.get(raw_name, raw_name)

    def fetch_pitbullchain_quotes(
        self,
        exchange: str = "binance",
        timeout: float = 6.0,
    ) -> list[BankRateQuote]:
        """Obtiene el ranking y cotizaciones agregadas de bancos P2P desde la API de PitbullChain."""
        url = f"https://pitbullchain.com/api/p2p/banks?exchange={exchange}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "application/json",
        }
        quotes: list[BankRateQuote] = []
        now = datetime.now(UTC)

        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.debug(f"PitbullChain API returned status {resp.status_code}")
                    return []

                payload = resp.json()
                data = payload.get("data", {})
                banks_list = data.get("banks", [])

                for b in banks_list:
                    raw_bank = str(b.get("bank", "")).strip()
                    if not raw_bank:
                        continue

                    norm_bank = self._normalize_bank_name(raw_bank)
                    avg_buy = float(b.get("avgBuyPrice", 0.0) or 0.0)
                    avg_sell = float(b.get("avgSellPrice", 0.0) or 0.0)

                    # Si solo hay precio en un sentido, estimar margen conservador
                    if avg_buy > 0 and avg_sell <= 0:
                        avg_sell = round(avg_buy * 0.995, 2)
                    elif avg_sell > 0 and avg_buy <= 0:
                        avg_buy = round(avg_sell * 1.005, 2)
                    elif avg_buy <= 0 and avg_sell <= 0:
                        continue

                    total_ads = int(b.get("totalAds", 0) or 0)
                    score = float(b.get("score", 0.0) or 0.0)
                    liquidity_pct = float(b.get("liquidityPct", 0.0) or 0.0)
                    binance_code = str(b.get("binanceId", "") or b.get("bankCode", "") or "")
                    exchanges = list(b.get("exchanges", ["binance"]))

                    quotes.append(
                        BankRateQuote(
                            bank_name=norm_bank,
                            buy_rate=avg_buy,
                            sell_rate=avg_sell,
                            updated_at=now,
                            total_ads=total_ads,
                            score=score,
                            liquidity_pct=liquidity_pct,
                            binance_code=binance_code,
                            exchanges=exchanges,
                            source="pitbullchain",
                        )
                    )

            return quotes
        except (httpx.RequestError, ValueError, KeyError, OSError, RuntimeError) as e:
            logger.debug(f"No se pudo consultar PitbullChain API ({e})")
            return []

    def fetch_yadio_rate(self, fiat: str = "VES", timeout: float = 5.0) -> float | None:
        """Consulta la tasa P2P consolidada de mercado libre en Yadio API."""
        url = f"https://api.yadio.io/rate/{fiat}"
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    val = data.get("usd")
                    return float(val) if val is not None else None
        except (httpx.RequestError, ValueError, KeyError, OSError, RuntimeError) as e:
            logger.debug(f"Error consultando Yadio API: {e}")
        return None

    def fetch_criptoya_rate(
        self,
        asset: str = "USDT",
        fiat: str = "VES",
        volume: float = 1.0,
        timeout: float = 5.0,
    ) -> dict[str, float] | None:
        """Consulta el spread consolidado Ask/Bid de Binance P2P en CriptoYa API."""
        url = f"https://criptoya.com/api/binancep2p/{asset}/{fiat}/{volume}"
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    ask = float(data.get("ask", 0.0) or 0.0)
                    bid = float(data.get("bid", 0.0) or 0.0)
                    if ask > 0 and bid > 0:
                        return {"ask": ask, "bid": bid}
        except (httpx.RequestError, ValueError, KeyError, OSError, RuntimeError) as e:
            logger.debug(f"Error consultando CriptoYa API: {e}")
        return None

    def fetch_live_quotes(
        self,
        client: Any | None = None,
        asset: str = "USDT",
        fiat: str = "VES",
        banks: list[str] | None = None,
        use_public_bapi: bool = False,
        exchange: str = "binance",
    ) -> list[BankRateQuote]:
        """Obtiene las mejores cotizaciones de compra y venta por banco con arquitectura Failover Multinivel.

        Nivel 1: PitbullChain Aggregated API (Bancos, Spreads, Liquidez, Scores y Anuncios).
        Nivel 2: Binance P2P Client (SAPI / BAPI).
        Nivel 3: CriptoYa / Yadio API (Ancla macro de mercado).
        Nivel 4: Cotizaciones calibradas en memoria (Fail-closed / offline).
        """
        # Si se suministró un cliente explícito (ej. en tests automatizados), usarlo directamente
        if client is not None:
            target_banks = banks or list(self.BANK_PAY_TYPE_MAP.keys())
            quotes: list[BankRateQuote] = []
            now = datetime.now(UTC)

            try:
                buy_resp = client.search_p2p_ads(
                    asset=asset,
                    fiat=fiat,
                    trade_type="BUY",
                    rows=20,
                    use_public_bapi=use_public_bapi,
                )
                sell_resp = client.search_p2p_ads(
                    asset=asset,
                    fiat=fiat,
                    trade_type="SELL",
                    rows=20,
                    use_public_bapi=use_public_bapi,
                )

                for bank in target_banks:
                    pay_code = self.BANK_PAY_TYPE_MAP.get(bank, "").lower()
                    bank_lower = bank.lower()

                    best_buy: float | None = None
                    for item in buy_resp.data:
                        names_lower = [b.lower() for b in item.bank_names]
                        if any(bank_lower in n or (pay_code and pay_code in n) for n in names_lower):
                            p = float(item.adv.price)
                            if best_buy is None or p < best_buy:
                                best_buy = p

                    best_sell: float | None = None
                    for item in sell_resp.data:
                        names_lower = [b.lower() for b in item.bank_names]
                        if any(bank_lower in n or (pay_code and pay_code in n) for n in names_lower):
                            p = float(item.adv.price)
                            if best_sell is None or p > best_sell:
                                best_sell = p

                    if best_buy is not None and best_sell is not None:
                        quotes.append(BankRateQuote(bank_name=bank, buy_rate=best_buy, sell_rate=best_sell, updated_at=now, source="binance"))
                    elif best_buy is not None:
                        quotes.append(BankRateQuote(bank_name=bank, buy_rate=best_buy, sell_rate=round(best_buy * 1.01, 2), updated_at=now, source="binance"))

                if quotes:
                    return quotes
                logger.warning("No se encontraron órdenes P2P para los bancos especificados.")
                return []
            except (httpx.RequestError, RuntimeError, ValueError, KeyError, OSError, TypeError) as e:
                logger.warning(f"Fallo consultando cliente Binance P2P ({e}).")
                return []

        # Nivel 1: PitbullChain Aggregated API
        pitbull_quotes = self.fetch_pitbullchain_quotes(exchange=exchange)
        if pitbull_quotes:
            return pitbull_quotes

        # Nivel 2: Binance P2P BAPI / SAPI con credenciales si están disponibles
        try:
            from config.settings import Settings
            from src.core.binance_client import BinanceP2PClient
            from src.security.api_key_manager import ApiKeyManager

            settings = Settings()
            api_key = ""
            private_key = ""
            try:
                km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY)
                api_key = km.get_secret("binance_api_key") or ""
                private_key = km.get_secret("binance_private_key") or ""
            except (ValueError, KeyError, OSError, RuntimeError, TypeError):
                api_key = ""
                private_key = ""

            client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
            binance_quotes = self.fetch_live_quotes(
                client=client,
                asset=asset,
                fiat=fiat,
                banks=banks,
                use_public_bapi=True,
            )
            if binance_quotes:
                return binance_quotes
        except (ImportError, ValueError, KeyError, OSError, RuntimeError) as e:
            logger.debug(f"Fallo Nivel 2 Binance Client: {e}")

        # Fail-closed: Si no se obtuvieron cotizaciones de los libros reales P2P, no fabricar datos sintéticos
        logger.warning("FAIL-CLOSED: No se obtuvieron cotizaciones P2P reales ni de PitbullChain ni de Binance API.")
        return []

    def get_market_quotes(self, client: Any | None = None, use_sandbox: bool = True) -> list[BankRateQuote]:
        """Obtiene cotizaciones de mercado en tiempo real o genera instantáneas calibradas."""
        if not use_sandbox:
            return self.fetch_live_quotes(client=client, use_public_bapi=True)

        now = datetime.now(UTC)
        return [
            BankRateQuote("Banco de Venezuela", buy_rate=1012.20, sell_rate=1007.50, updated_at=now, total_ads=15, score=82.0, liquidity_pct=18.0, binance_code="BancoDeVenezuela", source="calibrated"),
            BankRateQuote("Banesco", buy_rate=1012.50, sell_rate=1007.20, updated_at=now, total_ads=18, score=89.0, liquidity_pct=22.0, binance_code="Banesco", source="calibrated"),
            BankRateQuote("Pago Móvil", buy_rate=1012.80, sell_rate=1007.80, updated_at=now, total_ads=22, score=88.0, liquidity_pct=25.0, binance_code="PagoMovil", source="calibrated"),
            BankRateQuote("Mercantil", buy_rate=1013.00, sell_rate=1007.60, updated_at=now, total_ads=7, score=55.0, liquidity_pct=9.0, binance_code="Mercantil", source="calibrated"),
            BankRateQuote("Bancamiga", buy_rate=1013.50, sell_rate=1008.00, updated_at=now, total_ads=3, score=45.0, liquidity_pct=4.0, binance_code="Bancamiga", source="calibrated"),
            BankRateQuote("BNC Banco Nacional de Crédito", buy_rate=1013.20, sell_rate=1007.90, updated_at=now, total_ads=2, score=43.0, liquidity_pct=3.0, binance_code="BNCBancoNacional", source="calibrated"),
            BankRateQuote("Banco Activo", buy_rate=1014.00, sell_rate=1006.50, updated_at=now, total_ads=1, score=42.0, liquidity_pct=1.0, binance_code="BancoActivo", source="calibrated"),
        ]

