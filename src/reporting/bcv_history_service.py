"""Servicio de gestión histórica y resolución de tasas oficiales del BCV con régimen estricto de Fecha Valor.
Maneja conversión a huso horario venezolano (UTC-4), reglas de fin de semana (viernes anterior),
y auto-población retroactiva (backfill) para órdenes históricas de Binance.
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.models import BCVRateHistory, Order
from src.data.repositories import BCVHistoryRepository
from src.reporting.bcv_service import BCVService

logger = logging.getLogger("bcv_history_service")

# Zona horaria oficial de Venezuela (UTC-4 permanente)
VET_TIMEZONE = timezone(timedelta(hours=-4))
BCV_SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "bcv_rates_seed.json"


class BCVHistoryService:
    """Motor de resolución de tasas oficiales históricas según el régimen legal de Fecha Valor."""

    def __init__(
        self,
        db_session: Session,
        bcv_live_service: BCVService | None = None,
    ):
        self.db = db_session
        self.repo = BCVHistoryRepository(self.db)
        self.live_service = bcv_live_service or BCVService()
        self._seed_checked = False

    def seed_historical_rates_if_missing(self) -> int:
        """Siembra las tasas históricas oficiales del BCV desde el JSON local sin sobrescribir registros existentes."""
        self._seed_checked = True
        if not BCV_SEED_FILE.exists():
            return 0
        try:
            raw_items = json.loads(BCV_SEED_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("No se pudo leer el seed histórico BCV (%s): %s", BCV_SEED_FILE, exc)
            return 0
        if not isinstance(raw_items, list):
            return 0

        existing_rows: list[Any] = self.db.query(BCVRateHistory.fecha_valor).all()
        existing_dates: set[date] = {
            cast(date, r[0])
            for r in existing_rows
            if r and r[0] is not None
        }
        inserted = 0
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("fecha_valor") or "").strip()
            raw_rate = float(item.get("usd_rate") or 0.0)
            if not raw_date or raw_rate <= 0:
                continue
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if parsed_date in existing_dates:
                continue
            self.db.add(
                BCVRateHistory(
                    fecha_valor=parsed_date,
                    usd_rate=raw_rate,
                    source="bcv_official_seed",
                )
            )
            existing_dates.add(parsed_date)
            inserted += 1

        if inserted > 0:
            try:
                self.db.commit()
                logger.info("Seed BCV histórico completado: %d fechas valor oficiales cargadas.", inserted)
            except SQLAlchemyError as exc:
                self.db.rollback()
                logger.warning("Error persistiendo seed histórico BCV: %s", exc)
                return 0
        return inserted

    @staticmethod
    def to_venezuela_time(dt: datetime) -> datetime:
        """Convierte cualquier datetime a la hora oficial de Venezuela (UTC-4)."""
        if dt.tzinfo is None:
            # Asumir UTC si es ingenuo
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(VET_TIMEZONE)

    @staticmethod
    def effective_business_date(target_date: date) -> date:
        """Si la fecha cae en sábado o domingo, retorna el viernes hábil inmediato anterior."""
        weekday = target_date.weekday()  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
        if weekday == 5:  # Sábado
            return target_date - timedelta(days=1)
        if weekday == 6:  # Domingo
            return target_date - timedelta(days=2)
        return target_date

    def get_or_fetch_current_rates(self, force_refresh: bool = False) -> dict[str, Any]:
        """Obtiene la tasa BCV vigente desde la base de datos histórica (`bcv_rate_history`);
        solo si no está registrada para la Fecha Valor hábil actual, consulta el portal BCV y la persiste en BD.
        """
        today_ve = datetime.now(VET_TIMEZONE).date()
        effective_date = self.effective_business_date(today_ve)

        if not force_refresh:
            existing = self.repo.get_rate_by_date(effective_date)
            if existing and float(existing.usd_rate) > 0:
                return {
                    "usd": float(existing.usd_rate),
                    "eur": float(existing.eur_rate) if existing.eur_rate else None,
                    "cny": None,
                    "fecha_valor": effective_date.strftime("%Y-%m-%d"),
                    "source": str(existing.source or "bcv_db_history"),
                }

        # Consultar en vivo solo cuando no exista registro para la fecha valor hábil actual
        full_rates = self.live_service.fetch_full_rates() if hasattr(self.live_service, "fetch_full_rates") else {}
        usd_val = float(full_rates.get("usd") or 0.0)
        if usd_val <= 0:
            usd_val = float(self.live_service.fetch_current_rate() or 0.0)

        eur_raw = full_rates.get("eur")
        eur_val = float(eur_raw) if eur_raw is not None and float(eur_raw) > 0 else None
        cny_raw = full_rates.get("cny")
        cny_val = float(cny_raw) if cny_raw is not None and float(cny_raw) > 0 else None
        fecha_valor_str = str(full_rates.get("fecha_valor") or effective_date.strftime("%Y-%m-%d"))

        if usd_val > 0:
            try:
                from src.core.rate_alert_service import parse_fecha_valor

                self.repo.upsert_rate(
                    BCVRateHistory(
                        fecha_valor=effective_date,
                        usd_rate=usd_rate if (usd_rate := usd_val) else usd_val,
                        eur_rate=eur_val,
                        source="bcv_official",
                    )
                )
                parsed_fv = parse_fecha_valor(fecha_valor_str)
                if parsed_fv and parsed_fv != effective_date:
                    self.repo.upsert_rate(
                        BCVRateHistory(
                            fecha_valor=parsed_fv,
                            usd_rate=usd_val,
                            eur_rate=eur_val,
                            source="bcv_official",
                        )
                    )
                logger.info(
                    f"Tasa BCV persistida en bcv_rate_history para Fecha Valor {effective_date}: USD={usd_val}, EUR={eur_val}"
                )
            except (SQLAlchemyError, ValueError, OSError, RuntimeError) as e:
                logger.warning(f"No se pudo persistir tasa BCV en bcv_rate_history: {e}")

            return {
                "usd": usd_val,
                "eur": eur_val,
                "cny": cny_val,
                "fecha_valor": fecha_valor_str,
                "source": "bcv_live_saved",
            }

        # Fallback a la última tasa histórica guardada en la base de datos si el portal BCV está caído
        latest = self.repo.get_latest_rate()
        if latest and float(latest.usd_rate) > 0:
            return {
                "usd": float(latest.usd_rate),
                "eur": float(latest.eur_rate) if latest.eur_rate else None,
                "cny": None,
                "fecha_valor": str(latest.fecha_valor),
                "source": "bcv_db_fallback",
            }

        return {"usd": 0.0, "eur": None, "cny": None, "fecha_valor": None, "source": "unavailable"}

    def get_rate_for_date(self, target_date: date) -> float:
        """Obtiene la tasa oficial vigente para una fecha calendario en Venezuela."""
        original_date = target_date
        target_date = self.effective_business_date(target_date)

        # 1. Buscar en la base de datos histórica por Fecha Valor exacta
        record = self.repo.get_rate_by_date(target_date)
        if not record and not self._seed_checked and self.seed_historical_rates_if_missing() > 0:
            record = self.repo.get_rate_by_date(target_date)
        if record and record.usd_rate > 0:
            return float(record.usd_rate)

        # 2. Si no está en BD (ej. feriado o laguna), buscar hacia atrás hasta 7 días
        for days_back in range(1, 8):
            prev_date = target_date - timedelta(days=days_back)
            if prev_date.weekday() in (5, 6):
                continue
            prev_rec = self.repo.get_rate_by_date(prev_date)
            if prev_rec and prev_rec.usd_rate > 0:
                logger.info(
                    f"Tasa para {target_date} no encontrada directamente. Usando fecha hábil previa {prev_date}: {prev_rec.usd_rate}"
                )
                return float(prev_rec.usd_rate)

        # 3. Si la fecha corresponde al día actual (o su fin de semana) o futura, consultar en vivo y persistir en BD
        today_ve = datetime.now(VET_TIMEZONE).date()
        if original_date >= today_ve or target_date >= self.effective_business_date(today_ve):
            current_data = self.get_or_fetch_current_rates()
            live_val = float(current_data.get("usd") or 0.0)
            if live_val > 0:
                return live_val

        # 4. Última tasa disponible en el sistema
        latest = self.repo.get_latest_rate()
        if latest and latest.usd_rate > 0:
            return float(latest.usd_rate)

        return 0.0

    def get_rate_for_timestamp(self, dt: datetime) -> float:
        """Determina la tasa oficial aplicable a una transacción ocurrida en el timestamp dado."""
        dt_ve = self.to_venezuela_time(dt)
        return self.get_rate_for_date(dt_ve.date())

    def backfill_orders(self, orders: list[Order]) -> int:
        """Puebla retroactivamente la tasa BCV oficial en órdenes históricas que carezcan de ella."""
        updated_count = 0
        for order in orders:
            if order.bcv_rate is None or float(order.bcv_rate) <= 0.0:
                t_order = cast(datetime, order.completed_at or order.created_at)
                resolved_rate = self.get_rate_for_timestamp(t_order)
                if resolved_rate > 0:
                    order.bcv_rate = resolved_rate  # type: ignore[assignment]
                    updated_count += 1
        return updated_count
