import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

logger = logging.getLogger("spread_monitor")

_ORDERBOOK_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_VOLUME_QUOTES_CACHE: dict[tuple[Any, ...], tuple[float, list["BankRateQuote"]]] = {}
CACHE_TTL_SECONDS: float = 12.0


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
            "PagoMovil": "Pago Móvil",
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
            "SpecificBank": "Banco de Venezuela (Transferencias)",
        }
        return mapping.get(raw_name, raw_name)

    @classmethod
    def resolve_binance_pay_types(cls, bank_filter: str | None) -> list[str]:
        """Mapea un nombre o filtro de banco a la lista blanca de payTypes oficiales de Binance P2P."""
        if not bank_filter:
            return []
        clean = bank_filter.strip()
        if not clean or clean.lower() == "todos":
            return []

        whitelist_aliases: dict[str, list[str]] = {
            "pago móvil": ["PagoMovil"],
            "pagomovil": ["PagoMovil"],
            "banesco": ["Banesco"],
            "banco de venezuela": ["BancoDeVenezuela", "SpecificBank"],
            "bandodevenezuela": ["BancoDeVenezuela", "SpecificBank"],
            "venezuela": ["BancoDeVenezuela", "SpecificBank"],
            "specificbank": ["SpecificBank"],
            "mercantil": ["Mercantil"],
            "bbva provincial": ["Provincial", "BBVABank", "BBVABancoProvincial"],
            "provincial": ["Provincial", "BBVABank", "BBVABancoProvincial"],
            "bnc": ["BNCBancoNacional", "BancoNacionaldeCredito"],
            "bnc banco nacional de crédito": ["BNCBancoNacional", "BancoNacionaldeCredito"],
            "bancamiga": ["Bancamiga"],
            "transferencia bancaria": ["BANK"],
            "bank": ["BANK"],
            "bancaribe": ["Bancaribe"],
            "banco del tesoro": ["BancoDelTesoro"],
            "banplus": ["Banplus"],
            "bfc": ["BFC"],
            "bfc banco fondo común": ["BFC"],
            "banco activo": ["BancoActivo"],
            "banco plaza": ["BancoPlaza"],
        }
        lower_key = clean.lower()
        if lower_key in whitelist_aliases:
            return whitelist_aliases[lower_key]

        # Permitir coincidencia exacta contra valores de BINANCE_METHODS_MAP
        for label, code in cls.BINANCE_METHODS_MAP.items():
            if lower_key in (label.lower(), code.lower()):
                return [code]

        return []

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

                seen_banks: dict[str, BankRateQuote] = {}
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

                    if norm_bank in seen_banks:
                        existing = seen_banks[norm_bank]
                        existing.total_ads += total_ads
                        existing.liquidity_pct = round(existing.liquidity_pct + liquidity_pct, 2)
                        if avg_buy > 0 and (existing.buy_rate <= 0 or avg_buy < existing.buy_rate):
                            existing.buy_rate = avg_buy
                        existing.sell_rate = max(existing.sell_rate, avg_sell)
                        continue

                    quote_obj = BankRateQuote(
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
                    seen_banks[norm_bank] = quote_obj
                    quotes.append(quote_obj)

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
        trans_amount_ves: float | None = None,
        merchant_only: bool = False,
    ) -> list[BankRateQuote]:
        """Obtiene las mejores cotizaciones de compra y venta por banco con arquitectura Failover Multinivel.

        Nivel 1: PitbullChain Aggregated API + enriquecimiento en vivo por monto (transAmount) en Binance BAPI.
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
                    trans_amount=trans_amount_ves,
                    merchant_check=merchant_only,
                    use_public_bapi=use_public_bapi,
                )
                sell_resp = client.search_p2p_ads(
                    asset=asset,
                    fiat=fiat,
                    trade_type="SELL",
                    rows=20,
                    trans_amount=trans_amount_ves,
                    merchant_check=merchant_only,
                    use_public_bapi=use_public_bapi,
                )

                for bank in target_banks:
                    pay_code = self.BANK_PAY_TYPE_MAP.get(bank, "").lower()
                    bank_lower = bank.lower()

                    best_buy: float | None = None
                    buy_ads_count = 0
                    for item in buy_resp.data:
                        names_lower = [b.lower() for b in item.bank_names]
                        if any(bank_lower in n or (pay_code and pay_code in n) for n in names_lower):
                            buy_ads_count += 1
                            p = float(item.adv.price)
                            if best_buy is None or p < best_buy:
                                best_buy = p

                    best_sell: float | None = None
                    sell_ads_count = 0
                    for item in sell_resp.data:
                        names_lower = [b.lower() for b in item.bank_names]
                        if any(bank_lower in n or (pay_code and pay_code in n) for n in names_lower):
                            sell_ads_count += 1
                            p = float(item.adv.price)
                            if best_sell is None or p > best_sell:
                                best_sell = p

                    total_bank_ads = buy_ads_count + sell_ads_count
                    if best_buy is not None and best_sell is not None:
                        quotes.append(
                            BankRateQuote(
                                bank_name=bank,
                                buy_rate=best_buy,
                                sell_rate=best_sell,
                                updated_at=now,
                                total_ads=total_bank_ads,
                                source="binance",
                            )
                        )
                    elif best_buy is not None:
                        quotes.append(
                            BankRateQuote(
                                bank_name=bank,
                                buy_rate=best_buy,
                                sell_rate=round(best_buy * 1.01, 2),
                                updated_at=now,
                                total_ads=total_bank_ads,
                                source="binance",
                            )
                        )

                if quotes:
                    return quotes
                logger.warning("No se encontraron órdenes P2P para los bancos especificados.")
                return []
            except (httpx.RequestError, RuntimeError, ValueError, KeyError, OSError, TypeError) as e:
                logger.warning(f"Fallo consultando cliente Binance P2P ({e}).")
                return []

        has_volume_filter = bool((trans_amount_ves and trans_amount_ves > 0) or merchant_only)
        cache_key = (
            exchange,
            round(float(trans_amount_ves or 0.0), -2),
            bool(merchant_only),
        )
        now_ts = time.monotonic()
        if has_volume_filter:
            cached_entry = _VOLUME_QUOTES_CACHE.get(cache_key)
            if cached_entry and (now_ts - cached_entry[0]) < CACHE_TTL_SECONDS:
                return cached_entry[1]

        # Nivel 1: PitbullChain Aggregated API
        pitbull_quotes = self.fetch_pitbullchain_quotes(exchange=exchange)

        # Si el usuario filtró por monto específico (trans_amount_ves) o solo verificados,
        # consultar el libro real de Binance P2P con ese filtro exacto para ajustar las puntas de cada banco
        if has_volume_filter:
            try:
                from src.core.binance_client import BinanceP2PClient

                bapi_client = BinanceP2PClient()
                live_filtered = self.fetch_live_quotes(
                    client=bapi_client,
                    asset=asset,
                    fiat=fiat,
                    banks=banks,
                    use_public_bapi=True,
                    trans_amount_ves=trans_amount_ves,
                    merchant_only=merchant_only,
                )
                if live_filtered and pitbull_quotes:
                    by_name = {self._normalize_bank_name(q.bank_name): q for q in live_filtered}
                    for pq in pitbull_quotes:
                        norm_pq = self._normalize_bank_name(pq.bank_name)
                        if norm_pq in by_name:
                            lq = by_name[norm_pq]
                            pq.buy_rate = lq.buy_rate
                            pq.sell_rate = lq.sell_rate
                            if lq.total_ads > 0:
                                pq.total_ads = lq.total_ads
                            pq.source = "binance_filtered"
                elif live_filtered:
                    _VOLUME_QUOTES_CACHE[cache_key] = (now_ts, live_filtered)
                    return live_filtered
            except (ImportError, ValueError, KeyError, OSError, RuntimeError) as e:
                logger.debug(f"Enriquecimiento BAPI por volumen omitido: {e}")

        if pitbull_quotes:
            if has_volume_filter:
                _VOLUME_QUOTES_CACHE[cache_key] = (now_ts, pitbull_quotes)
            return pitbull_quotes

        # Nivel 2: Binance P2P BAPI / SAPI con credenciales si están disponibles
        try:
            from sqlalchemy.exc import SQLAlchemyError

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
            except (SQLAlchemyError, ValueError, KeyError, OSError, RuntimeError, TypeError):
                api_key = ""
                private_key = ""

            b_client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
            binance_quotes = self.fetch_live_quotes(
                client=b_client,
                asset=asset,
                fiat=fiat,
                banks=banks,
                use_public_bapi=True,
                trans_amount_ves=trans_amount_ves,
                merchant_only=merchant_only,
            )
            if binance_quotes:
                _VOLUME_QUOTES_CACHE[cache_key] = (now_ts, binance_quotes)
                return binance_quotes
        except (ImportError, ValueError, KeyError, OSError, RuntimeError) as e:
            logger.debug(f"Fallo Nivel 2 Binance Client: {e}")

        # Fail-closed: Si no se obtuvieron cotizaciones de los libros reales P2P, no fabricar datos sintéticos
        logger.warning("FAIL-CLOSED: No se obtuvieron cotizaciones P2P reales ni de PitbullChain ni de Binance API.")
        return []

    def fetch_filtered_orderbook(
        self,
        amount_usdt: float = 100.0,
        amount_ves: float | None = None,
        bank: str = "Todos",
        merchant_only: bool = False,
        rows: int = 10,
        client: Any | None = None,
    ) -> dict[str, Any]:
        """Consulta el libro de órdenes real de Binance P2P filtrado por banco, monto (transAmount) y verificados.

        Calcula el Spread por Precio tanto en modalidad Taker (tomar anuncios existentes) como Maker
        (publicar anuncio propio compitiendo en la punta del libro).
        """
        safe_usdt = max(1.0, min(float(amount_usdt), 100000.0))
        safe_rows = max(1, min(int(rows), 20))
        pay_types = self.resolve_binance_pay_types(bank)
        clean_bank = bank.strip() if bank and bank.strip() else "Todos"

        # Determinar tasa de referencia para convertir amount_usdt -> transAmount en Bs (VES)
        ref_rate = 1005.0
        base_quotes = _VOLUME_QUOTES_CACHE.get(("binance", 0.0, False))
        if base_quotes and base_quotes[1]:
            ref_rate = base_quotes[1][0].buy_rate or 1005.0
        elif client is None:
            yadio = self.fetch_yadio_rate()
            if yadio and yadio > 0:
                ref_rate = yadio

        trans_amount_ves = (
            round(float(amount_ves), 2)
            if (amount_ves is not None and amount_ves > 0)
            else round(safe_usdt * ref_rate, 2)
        )

        cache_key = (
            clean_bank.lower(),
            round(trans_amount_ves, -2),
            bool(merchant_only),
            safe_rows,
        )
        now_ts = time.monotonic()
        if client is None:
            cached = _ORDERBOOK_CACHE.get(cache_key)
            if cached and (now_ts - cached[0]) < CACHE_TTL_SECONDS:
                return cached[1]

        active_client = client
        if active_client is None:
            from src.core.binance_client import BinanceP2PClient

            active_client = BinanceP2PClient()

        buy_ads: list[dict[str, Any]] = []
        sell_ads: list[dict[str, Any]] = []
        source_label = "binance_bapi"

        try:
            buy_resp = active_client.search_p2p_ads(
                asset="USDT",
                fiat="VES",
                trade_type="BUY",
                rows=safe_rows,
                pay_types=pay_types,
                trans_amount=trans_amount_ves,
                merchant_check=merchant_only,
                use_public_bapi=True,
            )
            sell_resp = active_client.search_p2p_ads(
                asset="USDT",
                fiat="VES",
                trade_type="SELL",
                rows=safe_rows,
                pay_types=pay_types,
                trans_amount=trans_amount_ves,
                merchant_check=merchant_only,
                use_public_bapi=True,
            )

            for item in buy_resp.data:
                price_f = float(item.adv.price or 0.0)
                if price_f <= 0:
                    continue
                min_ves = float(item.adv.minSingleTransAmount or 0.0)
                max_ves = float(item.adv.maxSingleTransAmount or 0.0)
                surplus = float(item.adv.surplusAmount or 0.0)
                norm_banks = [self._normalize_bank_name(b) for b in item.bank_names]
                buy_ads.append({
                    "adv_no": item.adv.advNo,
                    "trade_type": "BUY",
                    "price": round(price_f, 2),
                    "surplus_usdt": round(surplus, 2),
                    "min_ves": round(min_ves, 2),
                    "max_ves": round(max_ves, 2),
                    "min_usdt": round(min_ves / price_f, 2) if price_f > 0 else 0.0,
                    "max_usdt": round(max_ves / price_f, 2) if price_f > 0 else 0.0,
                    "nick_name": item.advertiser.nickName,
                    "month_orders": int(item.advertiser.monthOrderCount or 0),
                    "finish_rate_pct": round(float(item.advertiser.monthFinishRate or 0.0) * 100, 1),
                    "is_merchant": (
                        item.advertiser.userType == "merchant"
                        or int(item.advertiser.monthOrderCount or 0) >= 300
                        or merchant_only
                    ),
                    "banks": norm_banks,
                })

            for item in sell_resp.data:
                price_f = float(item.adv.price or 0.0)
                if price_f <= 0:
                    continue
                min_ves = float(item.adv.minSingleTransAmount or 0.0)
                max_ves = float(item.adv.maxSingleTransAmount or 0.0)
                surplus = float(item.adv.surplusAmount or 0.0)
                norm_banks = [self._normalize_bank_name(b) for b in item.bank_names]
                sell_ads.append({
                    "adv_no": item.adv.advNo,
                    "trade_type": "SELL",
                    "price": round(price_f, 2),
                    "surplus_usdt": round(surplus, 2),
                    "min_ves": round(min_ves, 2),
                    "max_ves": round(max_ves, 2),
                    "min_usdt": round(min_ves / price_f, 2) if price_f > 0 else 0.0,
                    "max_usdt": round(max_ves / price_f, 2) if price_f > 0 else 0.0,
                    "nick_name": item.advertiser.nickName,
                    "month_orders": int(item.advertiser.monthOrderCount or 0),
                    "finish_rate_pct": round(float(item.advertiser.monthFinishRate or 0.0) * 100, 1),
                    "is_merchant": (
                        item.advertiser.userType == "merchant"
                        or int(item.advertiser.monthOrderCount or 0) >= 300
                        or merchant_only
                    ),
                    "banks": norm_banks,
                })
        except (httpx.RequestError, RuntimeError, ValueError, KeyError, OSError, TypeError) as e:
            logger.warning(f"Fallo consultando orderbook filtrado Binance P2P ({e})")
            source_label = "error_fallback"

        # Ordenar anuncios igual que Binance P2P:
        # Pestaña COMPRAR (BUY): del más barato al más caro
        buy_ads.sort(key=lambda x: x["price"])
        # Pestaña VENDER (SELL): del más caro al más barato
        sell_ads.sort(key=lambda x: x["price"], reverse=True)

        best_buy_price = buy_ads[0]["price"] if buy_ads else 0.0
        best_sell_price = sell_ads[0]["price"] if sell_ads else 0.0

        # En Binance P2P:
        # - Taker Spread: Compras tomando un anuncio en BUY (best_buy_price) y vendes tomando en SELL (best_sell_price)
        # - Maker Spread (Comerciante con Anuncio): Compras publicando en la columna SELL (best_sell_price)
        #   y vendes publicando en la columna BUY (best_buy_price)
        taker_spread_ves = (
            round(best_sell_price - best_buy_price, 2)
            if (best_buy_price > 0 and best_sell_price > 0)
            else 0.0
        )
        taker_spread_pct = (
            round((taker_spread_ves / best_buy_price) * 100, 2)
            if best_buy_price > 0
            else 0.0
        )

        maker_spread_ves = (
            round(best_buy_price - best_sell_price, 2)
            if (best_buy_price > 0 and best_sell_price > 0)
            else 0.0
        )
        maker_spread_pct = (
            round((maker_spread_ves / best_sell_price) * 100, 2)
            if best_sell_price > 0
            else 0.0
        )

        # Seleccionar el modo más rentable (Maker cuando best_buy_price > best_sell_price, Taker en caso contrario)
        if best_buy_price > best_sell_price > 0:
            calc = self.calculate_cycle_net_profit(
                crypto_amount=safe_usdt,
                buy_price=best_sell_price,
                sell_price=best_buy_price,
                binance_maker_fee_pct=0.0035,
                bank_fee_pct=0.0,
            )
            effective_spread_ves = maker_spread_ves
            effective_spread_pct = maker_spread_pct
            recommended_mode = "MAKER"
        elif best_buy_price > 0 and best_sell_price > 0:
            calc = self.calculate_cycle_net_profit(
                crypto_amount=safe_usdt,
                buy_price=best_buy_price,
                sell_price=best_sell_price,
                binance_maker_fee_pct=0.0,
                bank_fee_pct=0.0,
            )
            effective_spread_ves = taker_spread_ves
            effective_spread_pct = taker_spread_pct
            recommended_mode = "TAKER"
        else:
            effective_spread_ves = 0.0
            effective_spread_pct = 0.0
            recommended_mode = "NONE"
            calc = None

        result: dict[str, Any] = {
            "amount_usdt": safe_usdt,
            "trans_amount_ves": trans_amount_ves,
            "bank_filter": clean_bank,
            "pay_types": pay_types,
            "merchant_only": bool(merchant_only),
            "best_buy_price": best_buy_price,
            "best_sell_price": best_sell_price,
            "price_spread_ves": effective_spread_ves,
            "price_spread_pct": effective_spread_pct,
            "taker_spread_ves": taker_spread_ves,
            "taker_spread_pct": taker_spread_pct,
            "maker_spread_ves": maker_spread_ves,
            "maker_spread_pct": maker_spread_pct,
            "recommended_mode": recommended_mode,
            "net_profit_ves": calc.net_profit_ves if calc else 0.0,
            "net_profit_usdt": calc.net_profit_usdt if calc else 0.0,
            "buy_ads": buy_ads,
            "sell_ads": sell_ads,
            "source": source_label,
            "timestamp": datetime.now(UTC),
        }

        if client is None and (buy_ads or sell_ads):
            _ORDERBOOK_CACHE[cache_key] = (now_ts, result)

        return result

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

