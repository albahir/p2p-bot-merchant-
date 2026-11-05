"""Servicio de gestión histórica y resolución de tasas oficiales del BCV con régimen estricto de Fecha Valor.
Maneja conversión a huso horario venezolano (UTC-4), reglas de fin de semana (viernes anterior),
y auto-población retroactiva (backfill) para órdenes históricas de Binance.
"""

import logging
from datetime import UTC, date, datetime, timedelta, timezone
from typing import cast

from sqlalchemy.orm import Session

from src.data.models import Order
from src.data.repositories import BCVHistoryRepository
from src.reporting.bcv_service import BCVService

logger = logging.getLogger("bcv_history_service")

# Zona horaria oficial de Venezuela (UTC-4 permanente)
VET_TIMEZONE = timezone(timedelta(hours=-4))


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

    @staticmethod
    def to_venezuela_time(dt: datetime) -> datetime:
        """Convierte cualquier datetime a la hora oficial de Venezuela (UTC-4)."""
        if dt.tzinfo is None:
            # Asumir UTC si es ingenuo
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(VET_TIMEZONE)

    def get_rate_for_date(self, target_date: date) -> float:
        """Obtiene la tasa oficial vigente para una fecha calendario en Venezuela."""
        # Si cae en fin de semana, retroceder al viernes hábil anterior
        weekday = target_date.weekday()  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
        if weekday == 5:  # Sábado
            target_date = target_date - timedelta(days=1)
        elif weekday == 6:  # Domingo
            target_date = target_date - timedelta(days=2)

        # 1. Buscar en la base de datos histórica por Fecha Valor exacta
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

        # 3. Si la fecha es de hoy o futura, consultar en vivo
        today_ve = datetime.now(VET_TIMEZONE).date()
        if target_date >= today_ve:
            live_val = self.live_service.fetch_current_rate()
            if live_val > 0:
                return float(live_val)

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
