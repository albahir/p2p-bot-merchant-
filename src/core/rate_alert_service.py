"""Servicio de detección de cambios en Tasa Oficial BCV y Oportunidades de Arbitraje P2P.
Emite alertas proactivas ante fluctuaciones cambiarias o spreads interbancarios anómalos.
"""

import logging
import time

from src.core.spread_monitor import BankRateQuote, SpreadMonitor
from src.reporting.bcv_service import BCVService

logger = logging.getLogger("rate_alert_service")


class RateAlertService:
    """Monitor proactivo de cambios en la tasa oficial del BCV y spreads de mercado."""

    def __init__(self, cooldown_seconds: int = 600):
        self.cooldown_seconds = cooldown_seconds
        self.last_known_bcv_rate: float | None = None
        self.last_bcv_alert_time: float = 0.0
        self.last_arbitrage_alert_time: float = 0.0
        self.last_arbitrage_key: str | None = None
        self.monitor = SpreadMonitor()
        self.bcv_service = BCVService()

    def check_bcv_rate_change(self, current_rate: float, fecha_valor: str = "") -> str | None:
        """Detecta si la tasa oficial del BCV ha cambiado respecto al último valor conocido."""
        if current_rate <= 0:
            return None

        if self.last_known_bcv_rate is None:
            self.last_known_bcv_rate = current_rate
            logger.info(f"Tasa BCV base registrada: {current_rate:,.2f} VES/USD")
            return None

        # Comparar con tolerancia mínima de 0.01 VES
        diff = round(current_rate - self.last_known_bcv_rate, 4)
        if abs(diff) >= 0.01:
            previous = self.last_known_bcv_rate
            self.last_known_bcv_rate = current_rate
            diff_pct = (diff / previous) * 100.0 if previous > 0 else 0.0
            direction = "🔺 Subió" if diff > 0 else "🔻 Bajó"

            lines = [
                "🔔 *¡CAMBIO EN TASA OFICIAL BCV DETECTADO!*\n",
                f"• Tasa Anterior: `{previous:,.2f} VES/USD`",
                f"• Nueva Tasa BCV: `{current_rate:,.2f} VES/USD` ({direction} `{diff_pct:+.2f}%`)",
            ]
            if fecha_valor:
                lines.append(f"• Fecha Valor Oficial: *{fecha_valor}*")

            ref_p2p = 1000.0
            quotes = self.monitor.get_market_quotes()
            if quotes:
                ref_p2p = quotes[0].buy_rate
            gap = self.monitor.calculate_bcv_gap(p2p_price=ref_p2p, bcv_rate=current_rate)
            lines.append(f"• Brecha P2P vs BCV: `{gap:+.2f}%`")
            lines.append("\n💡 *Acción recomendada*: Revisa y ajusta los precios de tus anuncios Maker en Binance P2P.")

            return "\n".join(lines)

        return None

    def check_spread_opportunities(self, quotes: list[BankRateQuote]) -> str | None:
        """Identifica oportunidades destacadas de arbitraje interbancario (> 1.50% spread)."""
        if not quotes:
            return None

        cross = self.monitor.find_best_cross_arbitrage(quotes)
        if cross and cross["spread_pct"] >= 1.50:
            key = f"{cross['buy_bank']}->{cross['sell_bank']}"
            now = time.time()
            if key != self.last_arbitrage_key or (now - self.last_arbitrage_alert_time) > self.cooldown_seconds:
                self.last_arbitrage_key = key
                self.last_arbitrage_alert_time = now
                return (
                    f"⚡ *¡OPORTUNIDAD DE ARBITRAJE INTERBANCARIO DETECTADA!* (Spread: `+{cross['spread_pct']:+.2f}%`)\n\n"
                    f"• Compra en: *{cross['buy_bank']}* a `{cross['buy_rate']:,.2f} Bs`\n"
                    f"• Venta en: *{cross['sell_bank']}* a `{cross['sell_rate']:,.2f} Bs`\n"
                    f"• Spread Bruto: `+{cross['spread_ves']:+.2f} Bs`\n"
                    f"• Retorno Estimado: `+{cross['net_profit_ves_100u']:,.2f} Bs` por cada 100 USDT\n\n"
                    f"💡 Usa `/spread` para ver la matriz completa de bancos."
                )

        return None

    def poll_and_check(self) -> list[str]:
        """Consulta en vivo el BCV y cotizaciones P2P y retorna alertas disparadas."""
        alerts: list[str] = []
        try:
            full_bcv = self.bcv_service.fetch_full_rates()
            usd_rate = float(full_bcv.get("usd", 0.0))
            fecha = str(full_bcv.get("fecha_valor", ""))
            if usd_rate > 0:
                bcv_alert = self.check_bcv_rate_change(current_rate=usd_rate, fecha_valor=fecha)
                if bcv_alert:
                    alerts.append(bcv_alert)

            quotes = self.monitor.get_market_quotes()
            spread_alert = self.check_spread_opportunities(quotes)
            if spread_alert:
                alerts.append(spread_alert)
        except (ValueError, TypeError, OSError) as e:
            logger.debug(f"Error evaluando alertas de mercado: {e}")

        return alerts
