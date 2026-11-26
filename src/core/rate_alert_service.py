"""Servicio de detección de cambios en Tasa Oficial BCV y Oportunidades de Arbitraje P2P.
Emite alertas proactivas ante fluctuaciones cambiarias o spreads interbancarios anómalos.
"""

import logging
import re
import time
from datetime import date

import httpx

from src.core.spread_monitor import BankRateQuote, SpreadMonitor
from src.reporting.bcv_service import BCVService

logger = logging.getLogger("rate_alert_service")

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}


def parse_fecha_valor(fecha_str: str) -> date | None:
    """Extrae y normaliza una fecha calendario a partir de cadenas de Fecha Valor del BCV."""
    if not fecha_str:
        return None
    cleaned = fecha_str.strip().lower()

    # Formato común: 'Lunes, 19 Octubre 2026' o 'Martes, 20 Octubre  2026' o '19 de Octubre de 2026'
    m = re.search(r'(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\s+(?:de\s+)?(\d{4})', cleaned)
    if m:
        try:
            day = int(m.group(1))
            month_str = m.group(2)
            year = int(m.group(3))
            month = SPANISH_MONTHS.get(month_str)
            if month and 1 <= day <= 31:
                return date(year, month, day)
        except ValueError:
            pass

    # Formato numérico DD/MM/YYYY o DD-MM-YYYY
    m_num = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', cleaned)
    if m_num:
        try:
            day = int(m_num.group(1))
            month = int(m_num.group(2))
            year = int(m_num.group(3))
            return date(year, month, day)
        except ValueError:
            pass

    return None


class RateAlertService:
    """Monitor proactivo de cambios en la tasa oficial del BCV y spreads de mercado."""

    def __init__(self, cooldown_seconds: int = 600, bcv_cooldown_seconds: int | None = None):
        self.cooldown_seconds = cooldown_seconds
        self.bcv_cooldown_seconds = bcv_cooldown_seconds if bcv_cooldown_seconds is not None else cooldown_seconds
        self.last_known_bcv_rate: float | None = None
        self.last_known_fecha_valor: str | None = None
        self.last_known_fecha_date: date | None = None
        self.last_bcv_alert_time: float = 0.0
        self.last_arbitrage_alert_time: float = 0.0
        self.last_arbitrage_key: str | None = None
        self.last_arbitrage_buy_rate: float | None = None
        self.last_arbitrage_sell_rate: float | None = None
        self.last_arbitrage_spread_pct: float | None = None
        self.last_negative_spread_alert_time: float = 0.0
        self.last_negative_spread_banks: set[str] = set()
        self._recent_bcv_alerts: list[tuple[float, float]] = []  # (timestamp, rate)
        self.monitor = SpreadMonitor()
        self.bcv_service = BCVService()

    def check_bcv_rate_change(self, current_rate: float, fecha_valor: str = "") -> str | None:
        """Detecta si la tasa oficial del BCV ha cambiado respecto al último valor conocido.

        Implementa protección estricta anti-flapping (oscilación de balanceadores de carga / CDN)
        y filtro cronológico de Fecha Valor.
        """
        if current_rate <= 0:
            return None

        now = time.time()
        parsed_incoming_date = parse_fecha_valor(fecha_valor)

        # Si es la primera tasa vista, registrarla sin emitir alerta
        if self.last_known_bcv_rate is None:
            self.last_known_bcv_rate = current_rate
            self.last_known_fecha_valor = fecha_valor
            self.last_known_fecha_date = parsed_incoming_date
            logger.info(f"Tasa BCV base registrada: {current_rate:,.2f} VES/USD (Fecha: {fecha_valor})")
            return None

        # 1. Filtro Cronológico de Fecha Valor:
        # Si ya registramos una tasa con Fecha Valor más reciente (ej. Martes 20),
        # jamás retroceder a una fecha anterior (ej. Lunes 19) causada por servidores desincronizados de CANTV/BCV.
        if parsed_incoming_date and self.last_known_fecha_date and parsed_incoming_date < self.last_known_fecha_date:
            logger.debug(
                f"BCV Flapping filtrado: Se descartó respuesta desactualizada con fecha anterior "
                f"({parsed_incoming_date} < {self.last_known_fecha_date})"
            )
            return None

        # 2. Tolerancia mínima de variación (>= 0.01 VES)
        diff = round(current_rate - self.last_known_bcv_rate, 4)
        if abs(diff) < 0.01:
            return None

        # 3. Limpieza de ventana anti-flapping (últimos 30 minutos)
        self._recent_bcv_alerts = [
            (ts, r) for (ts, r) in self._recent_bcv_alerts if (now - ts) < 1800.0
        ]

        # Si esta tasa exacta ya fue alertada en los últimos 30 minutos, se trata de oscilación de CDN
        if any(abs(current_rate - past_rate) < 0.005 for _, past_rate in self._recent_bcv_alerts):
            logger.debug(f"BCV Flapping filtrado: Tasa {current_rate} ya fue alertada recientemente.")
            return None

        # 4. Respeto al Cooldown de Alertas BCV
        if (
            self.bcv_cooldown_seconds > 0
            and (now - self.last_bcv_alert_time) < self.bcv_cooldown_seconds
            and abs(diff / self.last_known_bcv_rate) < 0.05
        ):
            logger.debug(f"BCV Cooldown activo: Alerta suprimida ({now - self.last_bcv_alert_time:.1f}s < {self.bcv_cooldown_seconds}s)")
            return None

        previous = self.last_known_bcv_rate
        self.last_known_bcv_rate = current_rate
        if fecha_valor:
            self.last_known_fecha_valor = fecha_valor
        if parsed_incoming_date:
            self.last_known_fecha_date = parsed_incoming_date

        self.last_bcv_alert_time = now
        self._recent_bcv_alerts.append((now, current_rate))

        diff_pct = (diff / previous) * 100.0 if previous > 0 else 0.0
        direction = "🔺 Subió" if diff > 0 else "🔻 Bajó"

        lines = [
            "🔔 *¡CAMBIO EN TASA OFICIAL BCV DETECTADO!*\n",
            f"• Tasa Anterior: `{previous:,.2f} VES/USD`",
            f"• Nueva Tasa BCV: `{current_rate:,.2f} VES/USD` ({direction} `{diff_pct:+.2f}%`)",
        ]
        if fecha_valor:
            lines.append(f"• Fecha Valor Oficial: *{fecha_valor}*")

        ref_p2p = 0.0
        try:
            quotes = self.monitor.fetch_live_quotes(use_public_bapi=True)
            valid_rates = [q.buy_rate for q in quotes if getattr(q, "buy_rate", 0.0) > 0 and getattr(q, "source", "") not in ("calibrated", "mock", "fallback")]
            if valid_rates:
                ref_p2p = valid_rates[0]
        except (httpx.HTTPError, OSError, RuntimeError, ValueError, TypeError):
            ref_p2p = 0.0

        if ref_p2p > 0:
            gap = self.monitor.calculate_bcv_gap(p2p_price=ref_p2p, bcv_rate=current_rate)
            lines.append(f"• Brecha P2P vs BCV: `{gap:+.2f}%`")
        else:
            lines.append("• Brecha P2P vs BCV: `N/D (Sin datos P2P en vivo)`")
        lines.append("\n💡 *Acción recomendada*: Revisa y ajusta los precios de tus anuncios Maker en Binance P2P.")

        return "\n".join(lines)

    def check_spread_opportunities(self, quotes: list[BankRateQuote]) -> str | None:
        """Identifica oportunidades destacadas de arbitraje interbancario (> 1.50% spread).
        Evita enviar alertas repetitivas si la oportunidad y las tasas no han cambiado.
        """
        if not quotes:
            return None

        # NUNCA alertar sobre cotizaciones simuladas o calibradas de fallback
        if any(getattr(q, "source", "") in ("calibrated", "mock", "fallback") for q in quotes):
            return None

        cross = self.monitor.find_best_cross_arbitrage(quotes)
        if not cross or cross["spread_pct"] < 1.50:
            return None

        # Requiere viabilidad operativa (margen neto positivo tras comisiones Binance y bancarias)
        if not cross.get("is_viable", False):
            return None

        key = f"{cross['buy_bank']}->{cross['sell_bank']}"
        now = time.time()
        is_new_key = (key != self.last_arbitrage_key)

        # Evaluar si hubo cambio significativo en tasas o spread respecto a la última alerta
        rates_changed = False
        if (
            self.last_arbitrage_buy_rate is not None
            and self.last_arbitrage_sell_rate is not None
            and self.last_arbitrage_spread_pct is not None
        ):
            rate_delta = abs(cross["buy_rate"] - self.last_arbitrage_buy_rate) + abs(
                cross["sell_rate"] - self.last_arbitrage_sell_rate
            )
            spread_delta = abs(cross["spread_pct"] - self.last_arbitrage_spread_pct)
            # Solo consideramos cambio si el spread varió en >= 0.20% o las tasas en >= 0.50 Bs
            if spread_delta >= 0.20 or rate_delta >= 0.50:
                rates_changed = True
        else:
            rates_changed = True

        should_alert = is_new_key or (rates_changed and (now - self.last_arbitrage_alert_time) > self.cooldown_seconds)

        if should_alert:
            self.last_arbitrage_key = key
            self.last_arbitrage_buy_rate = float(cross["buy_rate"])
            self.last_arbitrage_sell_rate = float(cross["sell_rate"])
            self.last_arbitrage_spread_pct = float(cross["spread_pct"])
            self.last_arbitrage_alert_time = now
            return (
                f"⚡ *¡OPORTUNIDAD DE ARBITRAJE INTERBANCARIO DETECTADA!* (Spread: `{cross['spread_pct']:+.2f}%`)\n\n"
                f"• Compra en: *{cross['buy_bank']}* a `{cross['buy_rate']:,.2f} Bs`\n"
                f"• Venta en: *{cross['sell_bank']}* a `{cross['sell_rate']:,.2f} Bs`\n"
                f"• Spread Bruto: `{cross['spread_ves']:+.2f} Bs`\n"
                f"• Retorno Estimado: `{cross['net_profit_ves_100u']:+,.2f} Bs` por cada 100 USDT\n\n"
                f"💡 Usa `/spread` para ver la matriz completa de bancos."
            )

        return None

    def check_negative_spread_risk(
        self,
        quotes: list[BankRateQuote],
        bcv_rate: float = 0.0,
    ) -> str | None:
        """Detecta y alerta cuando el Spread Intrabanco se vuelve negativo (sell_rate < buy_rate)
        o se invierte peligrosamente durante un ciclo abierto por volatilidad del Bolívar.
        """
        if not quotes:
            return None
        if any(getattr(q, "source", "") in ("calibrated", "mock", "fallback") for q in quotes):
            return None

        inverted: list[BankRateQuote] = [
            q for q in quotes if q.buy_rate > 0 and q.sell_rate > 0 and q.sell_rate < q.buy_rate
        ]
        if not inverted:
            self.last_negative_spread_banks.clear()
            return None

        current_banks = {q.bank_name for q in inverted}
        now = time.time()
        is_new_inversion = bool(current_banks - self.last_negative_spread_banks)
        if not is_new_inversion and self.cooldown_seconds > 0 and (now - self.last_negative_spread_alert_time) < self.cooldown_seconds:
            return None

        self.last_negative_spread_banks = current_banks
        self.last_negative_spread_alert_time = now

        lines = [
            "⚠️ *¡ALERTA DE RIESGO CAMBIARIO: SPREAD INTRABANCO NEGATIVO!*\n",
            "Se detectó inversión de precios (Costo de Compra > Precio de Venta) en:",
        ]
        for q in inverted:
            spread_ves = q.sell_rate - q.buy_rate
            spread_pct = (spread_ves / q.buy_rate) * 100.0 if q.buy_rate > 0 else 0.0
            lines.append(
                f"• *{q.bank_name}*: Compra `{q.buy_rate:,.2f} Bs` vs Venta `{q.sell_rate:,.2f} Bs` "
                f"(Spread: `{spread_pct:+.2f}%` / `{spread_ves:+.2f} Bs`)"
            )
        if bcv_rate > 0:
            lines.append(f"\n• Referencia BCV Oficial: `{bcv_rate:,.2f} VES/USD`")
        lines.append(
            "\n🛡️ *Acción de Cobertura*: Pausa tus anuncios en los bancos afectados o rota hacia ruta interbancaria positiva."
        )
        return "\n".join(lines)

    def _persist_bcv_to_history_db(
        self,
        usd_rate: float,
        eur_rate: float | None = None,
        fecha_valor_str: str = "",
    ) -> None:
        """Persiste la tasa oficial detectada en la tabla `bcv_rate_history` (SQLite o PostgreSQL/Neon)."""
        if usd_rate <= 0:
            return
        try:
            from datetime import datetime

            from sqlalchemy.exc import SQLAlchemyError

            from src.data.database import SessionLocal
            from src.data.models import BCVRateHistory
            from src.data.repositories import BCVHistoryRepository
            from src.reporting.bcv_history_service import VET_TIMEZONE, BCVHistoryService

            today_ve = datetime.now(VET_TIMEZONE).date()
            effective_today = BCVHistoryService.effective_business_date(today_ve)
            parsed_date = parse_fecha_valor(fecha_valor_str)

            db = SessionLocal()
            try:
                repo = BCVHistoryRepository(db)
                # 1. Guardar para la Fecha Valor publicada por el BCV (si se pudo parsear del HTML)
                if parsed_date:
                    repo.upsert_rate(
                        BCVRateHistory(
                            fecha_valor=parsed_date,
                            usd_rate=usd_rate,
                            eur_rate=eur_rate,
                            source="bcv_official",
                        )
                    )
                # 2. Garantizar que el día hábil vigente en curso también tenga su registro en BD
                existing_today = repo.get_rate_by_date(effective_today)
                if existing_today is None:
                    repo.upsert_rate(
                        BCVRateHistory(
                            fecha_valor=effective_today,
                            usd_rate=usd_rate,
                            eur_rate=eur_rate,
                            source="bcv_official",
                        )
                    )
            finally:
                db.close()
        except (SQLAlchemyError, ValueError, KeyError, OSError, RuntimeError, ImportError) as e:
            logger.debug(f"No se pudo sincronizar tasa BCV en bcv_rate_history: {e}")

    def poll_and_check(self) -> list[str]:
        """Consulta en vivo el BCV y cotizaciones P2P, persiste en `bcv_rate_history` y retorna alertas."""
        alerts: list[str] = []
        try:
            full_bcv = self.bcv_service.fetch_full_rates()
            usd_rate = float(full_bcv.get("usd", 0.0))
            eur_raw = full_bcv.get("eur")
            eur_rate = float(eur_raw) if eur_raw is not None and float(eur_raw) > 0 else None
            fecha = str(full_bcv.get("fecha_valor", ""))
            if usd_rate > 0:
                self._persist_bcv_to_history_db(
                    usd_rate=usd_rate,
                    eur_rate=eur_rate,
                    fecha_valor_str=fecha,
                )
                bcv_alert = self.check_bcv_rate_change(current_rate=usd_rate, fecha_valor=fecha)
                if bcv_alert:
                    alerts.append(bcv_alert)

            # Consultar cotizaciones en vivo mediante failover multinivel (Pitbull / Binance / CriptoYa / Yadio)
            quotes = self.monitor.fetch_live_quotes(use_public_bapi=True)
            spread_alert = self.check_spread_opportunities(quotes)
            if spread_alert:
                alerts.append(spread_alert)
            risk_alert = self.check_negative_spread_risk(quotes, bcv_rate=usd_rate)
            if risk_alert:
                alerts.append(risk_alert)
        except (ValueError, TypeError, OSError) as e:
            logger.debug(f"Error evaluando alertas de mercado: {e}")

        return alerts
