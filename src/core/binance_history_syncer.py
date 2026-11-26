"""Sincronizador automático de historial de órdenes Binance P2P vía API oficial.

Permite consultar el endpoint GET /sapi/v1/c2c/orderMatch/listUserOrderHistory,
mapear las órdenes al modelo relacional Order, insertarlas de forma estrictamente
idempotente en la base de datos y generar reportes exportables en CSV.
"""

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, cast

import httpx
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.binance_client import BinanceAuthError, BinanceWeightExceededError
from src.core.binance_schemas import BinanceOrderMatchItem
from src.data.models import Order
from src.security.file_guards import (
    MAX_ORDERS_UPLOAD_BYTES,
    assert_not_executable_payload,
    parse_html_table_rows,
    validate_xls_safety,
    validate_xlsx_zip_safety,
)

logger = logging.getLogger("binance_history_syncer")


@dataclass
class SyncHistoryResult:
    """Resultado estructurado de la sincronización de órdenes."""

    total_fetched: int = 0
    orders_inserted: int = 0
    orders_existing: int = 0
    orders_updated: int = 0
    cancelled_skipped: int = 0
    reconciled_vouchers: int = 0
    buy_orders: int = 0
    sell_orders: int = 0
    total_volume_usdt: float = 0.0
    total_volume_fiat: float = 0.0
    effective_days: int = 0
    days_clamped: bool = False
    warnings: list[str] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    csv_bytes: bytes | None = None
    csv_comma_bytes: bytes | None = None
    excel_bytes: bytes | None = None
    error_message: str | None = None
    success: bool = True


class BinanceHistorySyncer:
    """Servicio de extracción y persistencia de órdenes P2P desde Binance API."""

    MAX_API_HISTORY_DAYS: int = 180
    MAX_WINDOW_DAYS: int = 30
    DEFAULT_PAGE_SIZE: int = 100

    @staticmethod
    def _normalize_order_status(raw_status: Any) -> str:
        """Normaliza estados de órdenes Binance en inglés o español a códigos canónicos."""
        if raw_status is None or (isinstance(raw_status, float) and pd.isna(raw_status)):
            return "COMPLETED"
        val = raw_status.value if hasattr(raw_status, "value") else raw_status
        txt = str(val).strip().upper()
        if not txt or txt == "NAN":
            return "COMPLETED"
        if "COMPLET" in txt or "SUCCESS" in txt or "FINISH" in txt:
            return "COMPLETED"
        if "CANCELLED_BY_SYSTEM" in txt or ("CANCEL" in txt and "SISTEM" in txt) or ("CANCEL" in txt and "SYSTEM" in txt):
            return "CANCELLED_BY_SYSTEM"
        if "CANCEL" in txt or "EXPIR" in txt or "FAIL" in txt or "RECHAZ" in txt or "ANULAD" in txt:
            return "CANCELLED"
        if txt in ("PENDING", "TRADING", "BUYER_PAYED", "DISTRIBUTING", "IN_APPEAL"):
            return txt
        if "PEND" in txt or "CURSO" in txt or "APEL" in txt or "PAGAD" in txt:
            return "PENDING"
        return txt[:30]

    @staticmethod
    def _is_cancelled_status(status_str: str) -> bool:
        up = (status_str or "").upper()
        return "CANCEL" in up or "EXPIR" in up

    @staticmethod
    def _parse_numeric_cell(val: Any, default: float = 0.0) -> float:
        """Convierte celdas numéricas de CSV/Excel tolerando comas decimales, separadores de miles y símbolos."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        if isinstance(val, (int, float)):
            return float(val)
        txt = (
            str(val)
            .strip()
            .replace("Bs.", "")
            .replace("Bs", "")
            .replace("VES", "")
            .replace("USDT", "")
            .replace("$", "")
            .strip()
        )
        if not txt or txt.lower() == "nan":
            return default
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            txt = txt.replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return default

    @staticmethod
    def _resolve_bcv_rate(db: Session | None = None) -> float:
        """Obtiene la tasa oficial BCV vigente con fallback al último histórico en BD."""
        try:
            from src.reporting.bcv_service import BCVService

            rate = float(BCVService().fetch_current_rate() or 0.0)
            if rate > 0.0:
                return rate
        except (RuntimeError, ValueError, OSError, KeyError, TypeError):
            pass

        if db is not None:
            try:
                from src.data.models import BCVRateHistory

                latest = db.query(BCVRateHistory).order_by(BCVRateHistory.fecha_valor.desc()).first()
                if latest and float(latest.usd_rate or 0.0) > 0.0:
                    return float(latest.usd_rate)
            except SQLAlchemyError:
                pass
        return 0.0

    @staticmethod
    def _map_item_to_order(item: BinanceOrderMatchItem, bcv_rate: float = 0.0) -> Order:
        """Convierte un BinanceOrderMatchItem de la API en la entidad SQLAlchemy Order."""
        created_dt = datetime.fromtimestamp(item.createTime / 1000.0, tz=UTC)
        unit_price = float(item.unitPrice)
        crypto_amount = float(item.amount)
        fiat_amount = float(item.totalPrice)
        fee_crypto = float(item.fee_decimal)
        fee_fiat = round(fee_crypto * unit_price, 2)
        raw_pm = getattr(item, "payMethodName", None)
        payment_method = str(raw_pm).strip()[:50] if raw_pm and str(raw_pm).strip() else None
        norm_status = BinanceHistorySyncer._normalize_order_status(item.orderStatus)

        return Order(
            order_number=str(item.orderNumber),
            trade_type=str(item.tradeType.value),
            asset=str(item.asset),
            fiat=str(item.fiat),
            fiat_amount=fiat_amount,
            crypto_amount=crypto_amount,
            unit_price=unit_price,
            fee_fiat=fee_fiat,
            fee_crypto=fee_crypto,
            bcv_rate=bcv_rate,
            order_status=norm_status,
            counterparty_name=str(item.counterPartNickName or "")[:100],
            payment_method=payment_method,
            created_at=created_dt,
        )

    @staticmethod
    def _to_vet_str(dt: datetime | None) -> str:
        """Convierte un datetime UTC/naive a Hora Legal de Venezuela (VET, UTC-4)."""
        if not dt:
            return ""
        vet_tz = timezone(timedelta(hours=-4))
        aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        return aware.astimezone(vet_tz).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _safe_spreadsheet_text(raw: Any, max_len: int = 200) -> str:
        """Neutraliza caracteres de control e inyección de fórmulas (=, +, -, @) al exportar CSV/Excel."""
        if raw is None:
            return ""
        text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(raw)).strip()
        if len(text) > 1 and text.startswith(("=", "+", "-", "@")) and not re.match(r"^[-+]\d", text):
            text = "'" + text
        return text[:max_len]

    @staticmethod
    def generate_orders_df(orders: list[Order]) -> pd.DataFrame:
        """Construye un DataFrame normalizado en hora VET (UTC-4) y referencia oficial BCV."""
        rows = []
        for o in orders:
            bcv = float(getattr(o, "bcv_rate", 0.0) or 0.0)
            fiat_amt = float(getattr(o, "fiat_amount", 0.0) or 0.0)
            usd_bcv = round(fiat_amt / bcv, 2) if bcv > 0 else 0.0
            rows.append(
                {
                    "Número de Orden": BinanceHistorySyncer._safe_spreadsheet_text(o.order_number, max_len=64),
                    "Tipo": o.trade_type,
                    "Estado": o.order_status,
                    "Criptoactivo": o.asset,
                    "Cantidad Cripto": o.crypto_amount,
                    "Moneda Fiat": o.fiat,
                    "Monto Fiat": fiat_amt,
                    "Precio Unitario": o.unit_price,
                    "Comisión Cripto": o.fee_crypto,
                    "Comisión Fiat": o.fee_fiat,
                    "Tasa BCV (VES/USD)": round(bcv, 4) if bcv > 0 else 0.0,
                    "Equivalente USD (BCV)": usd_bcv,
                    "Banco / Método de Pago": BinanceHistorySyncer._safe_spreadsheet_text(
                        getattr(o, "payment_method", None) or "-"
                    ),
                    "Contraparte": BinanceHistorySyncer._safe_spreadsheet_text(o.counterparty_name),
                    "Fecha y Hora (VET)": BinanceHistorySyncer._to_vet_str(cast(datetime | None, o.created_at)),
                    "Fecha y Hora (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
                }
            )
        return pd.DataFrame(rows)

    @classmethod
    def generate_orders_csv(cls, orders: list[Order], sep: str = ";") -> bytes:
        """Genera un archivo CSV codificado en UTF-8 con BOM.
        Por defecto utiliza ';' (punto y coma) para que Microsoft Excel en español/Latam
        separe automáticamente cada dato en su columna respectiva al hacer doble clic.
        """
        df = cls.generate_orders_df(orders)
        csv_str = df.to_csv(index=False, sep=sep)
        return csv_str.encode("utf-8-sig")

    @classmethod
    def generate_orders_excel(cls, orders: list[Order]) -> bytes:
        """Genera un archivo nativo de Microsoft Excel (.xlsx) con columnas separadas y autoajustadas."""
        import io

        df = cls.generate_orders_df(orders)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Órdenes P2P", index=False)
            worksheet = writer.sheets["Órdenes P2P"]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
                if col[0].value == "Número de Orden":
                    for cell in col[1:]:
                        cell.number_format = "@"

        return output.getvalue()

    @staticmethod
    def _load_existing_orders_map(
        db: Session,
        order_numbers: list[str],
        user_id: int | None,
    ) -> dict[str, Order]:
        """Carga en lote las órdenes ya registradas del operador para evitar consultas N+1."""
        if not order_numbers:
            return {}
        existing_map: dict[str, Order] = {}
        chunk_size = 500
        for idx in range(0, len(order_numbers), chunk_size):
            chunk = order_numbers[idx : idx + chunk_size]
            q = db.query(Order).filter(Order.order_number.in_(chunk))
            if user_id is not None:
                q = q.filter(Order.user_id == user_id)
            for row in q.all():
                existing_map[str(row.order_number)] = row
        return existing_map

    def sync_orders(
        self,
        client: Any,
        db: Session,
        days: int = 30,
        trade_type: str = "ALL",
        page_size: int = 100,
        user_id: int | None = None,
        year: int | None = None,
        month: int | None = None,
        start_date: date | None = None,
        only_completed: bool = False,
        include_exports: bool = True,
        auto_reconcile: bool = True,
    ) -> SyncHistoryResult:
        """Extrae el historial de órdenes desde Binance API en ventanas <= 30 días (más reciente → más antigua),
        respetando el límite real de 6 meses (180 días) de Binance C2C y guardando en lote por ventana.
        """
        now_dt = datetime.now(UTC)
        vet_tz = timezone(timedelta(hours=-4))
        warnings: list[str] = []
        days_clamped = False
        effective_days = max(1, int(days))

        if year is not None and month is not None:
            last_day = calendar.monthrange(year, month)[1]
            start_day = (
                start_date.day
                if (start_date is not None and start_date.year == year and start_date.month == month)
                else 1
            )
            start_vet = datetime(year, month, start_day, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC)
            end_vet = min(
                datetime(year, month, last_day, 23, 59, 59, 999000, tzinfo=vet_tz).astimezone(UTC),
                now_dt,
            )
            total_start_ms = int(start_vet.timestamp() * 1000)
            total_end_ms = max(total_start_ms + 1000, int(end_vet.timestamp() * 1000))
            effective_days = max(1, int((total_end_ms - total_start_ms) // (24 * 60 * 60 * 1000)) + 1)
        else:
            if days > self.MAX_API_HISTORY_DAYS:
                days_clamped = True
                effective_days = self.MAX_API_HISTORY_DAYS
                warnings.append(
                    "La API oficial de Binance P2P solo entrega historial de los últimos 6 meses (180 días). "
                    "Se sincronizaron los últimos 180 días; para historial anterior (hasta 365+ días), "
                    "descárgalo en Binance Web y súbelo con 'Importar (.csv / .xlsx)'."
                )
            else:
                effective_days = max(1, min(int(days), self.MAX_API_HISTORY_DAYS))
            total_end_ms = int(now_dt.timestamp() * 1000)
            total_start_ms = total_end_ms - (effective_days * 24 * 60 * 60 * 1000)

        # Sincronizar deriva de reloj con Binance antes de iniciar ventanas largas
        sync_time_fn = getattr(client, "sync_time", None)
        if callable(sync_time_fn):
            try:
                sync_time_fn()
            except (httpx.HTTPError, RuntimeError, ValueError, OSError):
                pass

        # Generar ventanas consecutivas de máximo 30 días y recorrer de MÁS RECIENTE a MÁS ANTIGUA
        # Así las órdenes recientes se aseguran primero y no se pierden si una ventana vieja excede el límite de Binance.
        window_size_ms = self.MAX_WINDOW_DAYS * 24 * 60 * 60 * 1000
        windows: list[tuple[int, int]] = []
        curr_start = total_start_ms
        while curr_start < total_end_ms:
            curr_end = min(curr_start + window_size_ms, total_end_ms)
            windows.append((curr_start, curr_end))
            curr_start = curr_end
        windows.reverse()

        safe_page_size = max(1, min(int(page_size), 100))
        types_to_fetch = ["BUY", "SELL"] if trade_type.upper() == "ALL" else [trade_type.upper()]

        from src.reporting.bcv_history_service import BCVHistoryService

        bcv_hist = BCVHistoryService(db)
        bcv_hist.seed_historical_rates_if_missing()
        fallback_bcv_rate: float | None = None
        rate_cache: dict[str, float] = {}

        def _rate_for_dt(dt_obj: datetime) -> float:
            nonlocal fallback_bcv_rate
            vet_d = bcv_hist.to_venezuela_time(dt_obj).date()
            k = vet_d.isoformat()
            if k not in rate_cache:
                resolved = bcv_hist.get_rate_for_date(vet_d)
                if resolved > 0:
                    rate_cache[k] = resolved
                else:
                    if fallback_bcv_rate is None:
                        fallback_bcv_rate = self._resolve_bcv_rate(db)
                    rate_cache[k] = fallback_bcv_rate
            return rate_cache[k]

        orders: list[Order] = []
        seen_order_numbers: set[str] = set()
        total_fetched = 0
        inserted_count = 0
        existing_count = 0
        updated_count = 0
        cancelled_skipped = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0
        succeeded_windows = 0

        for w_start, w_end in windows:
            window_items: list[BinanceOrderMatchItem] = []
            try:
                for t_type in types_to_fetch:
                    page = 1
                    while True:
                        resp = client.get_order_history(
                            trade_type=t_type,
                            start_timestamp=w_start,
                            end_timestamp=w_end,
                            page=page,
                            rows=safe_page_size,
                        )
                        items = getattr(resp, "data", []) or []
                        if not items:
                            break

                        for itm in items:
                            o_num = str(
                                getattr(itm, "order_number", None) or getattr(itm, "orderNumber", "") or ""
                            ).strip()
                            if o_num and o_num not in seen_order_numbers:
                                seen_order_numbers.add(o_num)
                                window_items.append(itm)

                        if len(items) < safe_page_size:
                            break
                        page += 1

                succeeded_windows += 1
            except (BinanceAuthError, BinanceWeightExceededError) as e:
                logger.error(f"Error crítico consultando historial de órdenes en Binance: {e}")
                return SyncHistoryResult(
                    success=False,
                    error_message=f"Error consultando Binance API: {e}",
                )
            except (httpx.HTTPError, RuntimeError, ValueError, KeyError, OSError) as e:
                if succeeded_windows == 0:
                    logger.error(f"Error consultando historial de órdenes en Binance: {e}")
                    return SyncHistoryResult(
                        success=False,
                        error_message=f"Error consultando Binance API: {e}",
                    )
                logger.warning(
                    "Ventana histórica antigua rechazada o interrumpida tras %d ventana(s) exitosa(s): %s",
                    succeeded_windows,
                    e,
                )
                warnings.append(
                    "Binance rechazó o interrumpió una ventana histórica antigua; "
                    "se conservaron todas las órdenes más recientes ya descargadas."
                )
                break

            if not window_items:
                continue

            total_fetched += len(window_items)
            window_nums = [
                str(getattr(itm, "order_number", None) or getattr(itm, "orderNumber", "")).strip()
                for itm in window_items
            ]

            try:
                existing_map = self._load_existing_orders_map(db, window_nums, user_id)
                for item in window_items:
                    raw_ts = getattr(item, "createTime", None) or getattr(item, "create_time", 0)
                    item_dt = (
                        datetime.fromtimestamp(float(raw_ts) / 1000.0, tz=UTC)
                        if raw_ts
                        else datetime.now(UTC)
                    )
                    order_entity = self._map_item_to_order(item, bcv_rate=_rate_for_dt(item_dt))
                    if user_id is not None:
                        order_entity.user_id = user_id  # type: ignore[assignment]

                    o_num = str(order_entity.order_number)
                    status_str = str(order_entity.order_status).upper()
                    is_completed = status_str == "COMPLETED"
                    existing = existing_map.get(o_num)

                    # Si se pidieron solo completadas, omitir nuevas canceladas/pendientes
                    # pero sí actualizar si una orden previamente PENDING cambió de estado.
                    if only_completed and not is_completed:
                        if self._is_cancelled_status(status_str):
                            cancelled_skipped += 1
                        if existing is not None and str(existing.order_status).upper() != status_str:
                            existing.order_status = status_str  # type: ignore[assignment]
                            updated_count += 1
                        continue

                    orders.append(order_entity)

                    # Solo órdenes COMPLETADAS se computan en conteos y volúmenes reales
                    if is_completed:
                        if order_entity.trade_type == "BUY":
                            buy_count += 1
                        elif order_entity.trade_type == "SELL":
                            sell_count += 1
                        if order_entity.asset.upper() == "USDT":
                            vol_usdt += float(order_entity.crypto_amount)
                        vol_fiat += float(order_entity.fiat_amount)

                    if existing is not None:
                        changed = False
                        if str(existing.order_status).upper() != status_str:
                            existing.order_status = status_str  # type: ignore[assignment]
                            changed = True
                        if not existing.payment_method and order_entity.payment_method:
                            existing.payment_method = order_entity.payment_method  # type: ignore[assignment]
                            changed = True
                        if float(existing.bcv_rate or 0.0) <= 0.0 and float(order_entity.bcv_rate or 0.0) > 0.0:
                            existing.bcv_rate = order_entity.bcv_rate  # type: ignore[assignment]
                            changed = True
                        if changed:
                            updated_count += 1
                        else:
                            existing_count += 1
                    else:
                        db.add(order_entity)
                        existing_map[o_num] = order_entity
                        inserted_count += 1

                db.commit()
            except SQLAlchemyError as e:
                db.rollback()
                logger.error(f"Error persistiendo órdenes de Binance en BD: {e}")
                return SyncHistoryResult(
                    success=False,
                    error_message=f"Error en base de datos: {e}",
                )

        # Auto-conciliar comprobantes bancarios huérfanos con las órdenes completadas nuevas/actualizadas
        reconciled_vouchers = 0
        if auto_reconcile and (inserted_count > 0 or updated_count > 0):
            try:
                from src.integrations.receipt_ocr import BankReceiptOCR

                reconciled_vouchers = int(
                    BankReceiptOCR().reconcile_orphan_vouchers(
                        db=db,
                        tolerance_hours=48,
                        user_id=user_id,
                    )
                    or 0
                )
            except (SQLAlchemyError, ValueError, TypeError, KeyError, OSError) as e:
                logger.warning(f"Error al auto-conciliar huérfanos tras sincronizar Binance API: {e}")

        csv_bytes: bytes | None = None
        csv_comma_bytes: bytes | None = None
        excel_bytes: bytes | None = None
        if include_exports:
            csv_bytes = self.generate_orders_csv(orders, sep=";")
            csv_comma_bytes = self.generate_orders_csv(orders, sep=",")
            excel_bytes = self.generate_orders_excel(orders)

        return SyncHistoryResult(
            total_fetched=total_fetched,
            orders_inserted=inserted_count,
            orders_existing=existing_count,
            orders_updated=updated_count,
            cancelled_skipped=cancelled_skipped,
            reconciled_vouchers=reconciled_vouchers,
            buy_orders=buy_count,
            sell_orders=sell_count,
            total_volume_usdt=round(vol_usdt, 2),
            total_volume_fiat=round(vol_fiat, 2),
            effective_days=effective_days,
            days_clamped=days_clamped,
            warnings=warnings,
            orders=orders,
            csv_bytes=csv_bytes,
            csv_comma_bytes=csv_comma_bytes,
            excel_bytes=excel_bytes,
            success=True,
        )

    def import_orders_file(
        self,
        file_bytes: bytes,
        filename: str,
        db: Session,
        user_id: int | None = None,
        only_completed: bool = False,
    ) -> SyncHistoryResult:
        """Parsea e importa órdenes de Binance P2P desde archivos Excel (.xlsx) o CSV descargados por el usuario.
        Respeta la columna real de estado (jamás marca canceladas como COMPLETED), extrae método de pago y comisiones.
        """
        import io

        orders: list[Order] = []
        inserted_count = 0
        existing_count = 0
        updated_count = 0
        cancelled_skipped = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0
        max_rows = 20000

        try:
            if len(file_bytes) > MAX_ORDERS_UPLOAD_BYTES:
                max_mb = MAX_ORDERS_UPLOAD_BYTES // (1024 * 1024)
                raise ValueError(f"El archivo supera el límite máximo permitido de {max_mb} MB.")

            lower_name = filename.lower()
            if lower_name.endswith(".xlsx"):
                validate_xlsx_zip_safety(file_bytes)
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    nrows=max_rows,
                    engine="openpyxl",
                    engine_kwargs={"read_only": True, "data_only": True},
                )
            elif lower_name.endswith(".xls"):
                xls_kind = validate_xls_safety(file_bytes)
                if xls_kind == "XLSX":
                    df = pd.read_excel(
                        io.BytesIO(file_bytes),
                        nrows=max_rows,
                        engine="openpyxl",
                        engine_kwargs={"read_only": True, "data_only": True},
                    )
                elif xls_kind == "HTML":
                    html_rows = parse_html_table_rows(file_bytes, max_rows=max_rows)
                    df = (
                        pd.DataFrame(html_rows[1:], columns=html_rows[0])
                        if len(html_rows) >= 2
                        else pd.DataFrame()
                    )
                else:
                    df = pd.read_excel(io.BytesIO(file_bytes), nrows=max_rows)
            else:
                assert_not_executable_payload(file_bytes)
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=",", nrows=max_rows)
                    if len(df.columns) <= 1:
                        df = pd.read_csv(io.BytesIO(file_bytes), sep=";", nrows=max_rows)
                except (ValueError, UnicodeDecodeError, OSError):
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=";", nrows=max_rows)

            col_map = {str(c).strip().lower().replace("_", " "): c for c in df.columns}

            def _get_val(row: Any, *keys: str) -> Any:
                for k in keys:
                    for c_clean, c_orig in col_map.items():
                        if k in c_clean:
                            return row[c_orig]
                return None

            from src.reporting.bcv_history_service import BCVHistoryService

            bcv_hist = BCVHistoryService(db)
            bcv_hist.seed_historical_rates_if_missing()
            current_bcv_rate = self._resolve_bcv_rate(db)
            rate_cache: dict[str, float] = {}

            parsed_entities: list[Order] = []
            parsed_nums: list[str] = []

            for _, row in df.iterrows():
                order_num = _get_val(
                    row,
                    "order number",
                    "order no",
                    "número de pedido",
                    "numero de pedido",
                    "número de orden",
                    "numero de orden",
                    "nº de orden",
                    "orden",
                )
                if not order_num or pd.isna(order_num):
                    continue

                order_num = str(order_num).strip()
                if not order_num or "no hay datos" in order_num.lower():
                    continue

                raw_status = _get_val(row, "order status", "status", "estado")
                norm_status = self._normalize_order_status(raw_status)

                if only_completed and norm_status != "COMPLETED":
                    if self._is_cancelled_status(norm_status):
                        cancelled_skipped += 1
                    continue

                t_type_raw = str(_get_val(row, "order type", "trade type", "tipo de orden", "type", "tipo") or "BUY").upper()
                trade_type = "SELL" if "SELL" in t_type_raw or "VENTA" in t_type_raw else "BUY"

                asset = str(_get_val(row, "asset", "crypto", "cripto", "criptomoneda", "activo") or "USDT").strip().upper()
                fiat = str(_get_val(row, "fiat", "moneda fiat", "fiat currency", "tipo de fiat") or "VES").strip().upper()

                fiat_amt = self._parse_numeric_cell(
                    _get_val(row, "total price", "total fiat", "monto fiat", "monto total", "precio total", "total"),
                    0.0,
                )
                crypto_amt = self._parse_numeric_cell(
                    _get_val(row, "quantity", "amount", "cantidad cripto", "cantidad"),
                    0.0,
                )
                unit_price = self._parse_numeric_cell(
                    _get_val(row, "unit price", "precio unitario", "price", "precio"),
                    0.0,
                )
                if unit_price <= 0.0 and crypto_amt > 0.0:
                    unit_price = fiat_amt / crypto_amt
                if crypto_amt <= 0.0 and unit_price > 0.0:
                    crypto_amt = fiat_amt / unit_price

                maker_fee = self._parse_numeric_cell(
                    _get_val(row, "maker fee", "tarifa de creador", "comisión maker", "comision maker"),
                    0.0,
                )
                taker_fee = self._parse_numeric_cell(
                    _get_val(row, "taker fee", "comisión de tomador", "comision de tomador", "comisión taker"),
                    0.0,
                )
                generic_fee = self._parse_numeric_cell(
                    _get_val(row, "comisión cripto", "comision cripto", "commission", "fee"),
                    0.0,
                )
                fee_crypto = round(maker_fee + taker_fee, 8) if (maker_fee > 0.0 or taker_fee > 0.0) else round(generic_fee, 8)
                fee_fiat = round(fee_crypto * unit_price, 2) if fee_crypto > 0.0 else 0.0

                raw_cp = _get_val(row, "counterparty", "contraparte", "counterpart", "usuario")
                counterparty = "" if (raw_cp is None or pd.isna(raw_cp)) else str(raw_cp).strip()[:100]

                raw_pm = _get_val(row, "payment method", "método de pago", "metodo de pago", "pay method")
                payment_method = (
                    None
                    if (raw_pm is None or pd.isna(raw_pm) or not str(raw_pm).strip())
                    else str(raw_pm).strip()[:50]
                )

                time_val = _get_val(row, "created time", "create time", "hora de creación", "hora de creacion", "fecha", "fecha/hora", "date")
                try:
                    created_dt = pd.to_datetime(time_val).to_pydatetime()
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=UTC)
                except (ValueError, TypeError, OverflowError):
                    created_dt = datetime.now(UTC)

                vet_day = bcv_hist.to_venezuela_time(created_dt).date()
                day_key = vet_day.isoformat()
                if day_key not in rate_cache:
                    resolved_r = bcv_hist.get_rate_for_date(vet_day)
                    rate_cache[day_key] = resolved_r if resolved_r > 0 else current_bcv_rate

                order_entity = Order(
                    user_id=user_id,
                    order_number=order_num,
                    trade_type=trade_type,
                    asset=asset,
                    fiat=fiat,
                    fiat_amount=fiat_amt,
                    crypto_amount=crypto_amt,
                    unit_price=unit_price,
                    fee_fiat=fee_fiat,
                    fee_crypto=fee_crypto,
                    bcv_rate=rate_cache[day_key],
                    order_status=norm_status,
                    counterparty_name=counterparty,
                    payment_method=payment_method,
                    created_at=created_dt,
                )
                parsed_entities.append(order_entity)
                parsed_nums.append(order_num)

            existing_map = self._load_existing_orders_map(db, parsed_nums, user_id)
            for order_entity in parsed_entities:
                o_num = str(order_entity.order_number)
                status_str = str(order_entity.order_status).upper()
                orders.append(order_entity)

                if status_str == "COMPLETED":
                    if order_entity.trade_type == "BUY":
                        buy_count += 1
                    else:
                        sell_count += 1
                    if order_entity.asset == "USDT":
                        vol_usdt += float(order_entity.crypto_amount)
                    vol_fiat += float(order_entity.fiat_amount)

                existing = existing_map.get(o_num)
                if existing is not None:
                    changed = False
                    if str(existing.order_status).upper() != status_str:
                        existing.order_status = status_str  # type: ignore[assignment]
                        changed = True
                    if not existing.payment_method and order_entity.payment_method:
                        existing.payment_method = order_entity.payment_method  # type: ignore[assignment]
                        changed = True
                    if changed:
                        updated_count += 1
                    else:
                        existing_count += 1
                else:
                    db.add(order_entity)
                    existing_map[o_num] = order_entity
                    inserted_count += 1

            db.commit()

            # Auto-conciliar huérfanos con estas nuevas órdenes
            reconciled_vouchers = 0
            try:
                from src.integrations.receipt_ocr import BankReceiptOCR

                reconciled_vouchers = int(
                    BankReceiptOCR().reconcile_orphan_vouchers(
                        db=db,
                        tolerance_hours=48,
                        user_id=user_id,
                    )
                    or 0
                )
            except (SQLAlchemyError, ValueError, TypeError, KeyError, OSError) as e:
                logger.warning(f"Error al auto-conciliar huérfanos tras importar archivo: {e}")

            return SyncHistoryResult(
                total_fetched=len(orders) + cancelled_skipped,
                orders_inserted=inserted_count,
                orders_existing=existing_count,
                orders_updated=updated_count,
                cancelled_skipped=cancelled_skipped,
                reconciled_vouchers=reconciled_vouchers,
                buy_orders=buy_count,
                sell_orders=sell_count,
                total_volume_usdt=round(vol_usdt, 2),
                total_volume_fiat=round(vol_fiat, 2),
                orders=orders,
                success=True,
            )

        except (SQLAlchemyError, ValueError, TypeError, KeyError, OSError, UnicodeDecodeError) as err:
            db.rollback()
            logger.error(f"Error importando archivo de órdenes de Binance: {err}")
            return SyncHistoryResult(
                success=False,
                error_message=f"No se pudo procesar el archivo: {err}",
            )


