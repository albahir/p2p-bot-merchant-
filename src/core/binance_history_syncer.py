"""Sincronizador automático de historial de órdenes Binance P2P vía API oficial.

Permite consultar el endpoint GET /sapi/v1/c2c/orderMatch/listUserOrderHistory,
mapear las órdenes al modelo relacional Order, insertarlas de forma estrictamente
idempotente en la base de datos y generar reportes exportables en CSV.
"""

import calendar
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import httpx
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.binance_client import BinanceAuthError, BinanceWeightExceededError
from src.core.binance_schemas import BinanceOrderMatchItem
from src.data.models import Order
from src.data.repositories import OrderRepository
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
    buy_orders: int = 0
    sell_orders: int = 0
    total_volume_usdt: float = 0.0
    total_volume_fiat: float = 0.0
    orders: list[Order] = field(default_factory=list)
    csv_bytes: bytes | None = None
    csv_comma_bytes: bytes | None = None
    excel_bytes: bytes | None = None
    error_message: str | None = None
    success: bool = True


class BinanceHistorySyncer:
    """Servicio de extracción y persistencia de órdenes P2P desde Binance API."""

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
            order_status=str(item.orderStatus.value),
            counterparty_name=str(item.counterPartNickName or ""),
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
    def generate_orders_df(orders: list[Order]) -> pd.DataFrame:
        """Construye un DataFrame normalizado en hora VET (UTC-4) y referencia oficial BCV."""
        rows = []
        for o in orders:
            bcv = float(getattr(o, "bcv_rate", 0.0) or 0.0)
            fiat_amt = float(getattr(o, "fiat_amount", 0.0) or 0.0)
            usd_bcv = round(fiat_amt / bcv, 2) if bcv > 0 else 0.0
            rows.append(
                {
                    "Número de Orden": str(o.order_number),
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
                    "Contraparte": o.counterparty_name,
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

    def sync_orders(
        self,
        client: Any,
        db: Session,
        days: int = 30,
        trade_type: str = "ALL",
        page_size: int = 50,
        user_id: int | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> SyncHistoryResult:
        """Extrae el historial de órdenes desde Binance API en ventanas <= 30 días, con tasa BCV histórica por fecha."""
        now_dt = datetime.now(UTC)
        vet_tz = timezone(timedelta(hours=-4))
        if year is not None and month is not None:
            last_day = calendar.monthrange(year, month)[1]
            start_vet = datetime(year, month, 1, 0, 0, 0, tzinfo=vet_tz).astimezone(UTC)
            end_vet = min(
                datetime(year, month, last_day, 23, 59, 59, 999000, tzinfo=vet_tz).astimezone(UTC),
                now_dt,
            )
            total_start_ms = int(start_vet.timestamp() * 1000)
            total_end_ms = max(total_start_ms + 1000, int(end_vet.timestamp() * 1000))
        else:
            safe_days = max(1, min(days, 365))
            total_end_ms = int(now_dt.timestamp() * 1000)
            total_start_ms = total_end_ms - (safe_days * 24 * 60 * 60 * 1000)

        # Generar ventanas consecutivas de máximo 30 días
        window_size_ms = 30 * 24 * 60 * 60 * 1000
        windows: list[tuple[int, int]] = []
        curr_start = total_start_ms
        while curr_start < total_end_ms:
            curr_end = min(curr_start + window_size_ms, total_end_ms)
            windows.append((curr_start, curr_end))
            curr_start = curr_end

        types_to_fetch = ["BUY", "SELL"] if trade_type.upper() == "ALL" else [trade_type.upper()]
        all_items: list[BinanceOrderMatchItem] = []
        seen_order_numbers: set[str] = set()

        try:
            for w_start, w_end in windows:
                for t_type in types_to_fetch:
                    page = 1
                    while True:
                        resp = client.get_order_history(
                            trade_type=t_type,
                            start_timestamp=w_start,
                            end_timestamp=w_end,
                            page=page,
                            rows=page_size,
                        )
                        items = getattr(resp, "data", []) or []
                        if not items:
                            break

                        for itm in items:
                            o_num = getattr(itm, "order_number", None) or getattr(itm, "orderNumber", "")
                            if o_num and o_num not in seen_order_numbers:
                                seen_order_numbers.add(o_num)
                                all_items.append(itm)

                        if len(items) < page_size:
                            break
                        page += 1

        except (
            BinanceAuthError,
            BinanceWeightExceededError,
            httpx.HTTPError,
            RuntimeError,
            ValueError,
            KeyError,
            OSError,
        ) as e:
            logger.error(f"Error consultando historial de órdenes en Binance: {e}")
            return SyncHistoryResult(
                success=False,
                error_message=f"Error consultando Binance API: {e}",
            )


        # Mapear e insertar en base de datos
        repo = OrderRepository(db, user_id=user_id)
        orders: list[Order] = []
        inserted_count = 0
        existing_count = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0

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

        try:
            for item in all_items:
                raw_ts = getattr(item, "createTime", None) or getattr(item, "create_time", 0)
                item_dt = datetime.fromtimestamp(float(raw_ts) / 1000.0, tz=UTC) if raw_ts else datetime.now(UTC)
                order_entity = self._map_item_to_order(item, bcv_rate=_rate_for_dt(item_dt))
                orders.append(order_entity)

                if order_entity.trade_type == "BUY":
                    buy_count += 1
                elif order_entity.trade_type == "SELL":
                    sell_count += 1

                if order_entity.asset.upper() == "USDT":
                    vol_usdt += float(order_entity.crypto_amount)
                vol_fiat += float(order_entity.fiat_amount)

                existing = repo.get_by_order_number(str(order_entity.order_number))
                if existing:
                    existing_count += 1
                else:
                    repo.create(order_entity)
                    inserted_count += 1

            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error persistiendo órdenes de Binance en BD: {e}")
            return SyncHistoryResult(
                success=False,
                error_message=f"Error en base de datos: {e}",
            )

        # Generar archivos para descarga directa:
        # 1. CSV con delimitador ';' (para Microsoft Excel en español/Latam)
        # 2. CSV con delimitador ',' (para software o librerías internacionales)
        # 3. Excel nativo .xlsx (abre con columnas automáticas sin importar configuración regional)
        csv_bytes = self.generate_orders_csv(orders, sep=";")
        csv_comma_bytes = self.generate_orders_csv(orders, sep=",")
        excel_bytes = self.generate_orders_excel(orders)

        return SyncHistoryResult(
            total_fetched=len(all_items),
            orders_inserted=inserted_count,
            orders_existing=existing_count,
            buy_orders=buy_count,
            sell_orders=sell_count,
            total_volume_usdt=round(vol_usdt, 2),
            total_volume_fiat=round(vol_fiat, 2),
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
    ) -> SyncHistoryResult:
        """Parsea e importa órdenes de Binance P2P desde archivos Excel (.xlsx) o CSV descargados por el usuario."""
        import io
        repo = OrderRepository(db, user_id=user_id)
        orders: list[Order] = []
        inserted_count = 0
        existing_count = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0

        try:
            if len(file_bytes) > MAX_ORDERS_UPLOAD_BYTES:
                max_mb = MAX_ORDERS_UPLOAD_BYTES // (1024 * 1024)
                raise ValueError(f"El archivo supera el límite máximo permitido de {max_mb} MB.")

            lower_name = filename.lower()
            if lower_name.endswith(".xlsx"):
                validate_xlsx_zip_safety(file_bytes)
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    nrows=5050,
                    engine="openpyxl",
                    engine_kwargs={"read_only": True, "data_only": True},
                )
            elif lower_name.endswith(".xls"):
                xls_kind = validate_xls_safety(file_bytes)
                if xls_kind == "XLSX":
                    df = pd.read_excel(
                        io.BytesIO(file_bytes),
                        nrows=5050,
                        engine="openpyxl",
                        engine_kwargs={"read_only": True, "data_only": True},
                    )
                elif xls_kind == "HTML":
                    html_rows = parse_html_table_rows(file_bytes, max_rows=5050)
                    df = (
                        pd.DataFrame(html_rows[1:], columns=html_rows[0])
                        if len(html_rows) >= 2
                        else pd.DataFrame()
                    )
                else:
                    df = pd.read_excel(io.BytesIO(file_bytes), nrows=5050)
            else:
                assert_not_executable_payload(file_bytes)
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=",", nrows=5050)
                    if len(df.columns) <= 1:
                        df = pd.read_csv(io.BytesIO(file_bytes), sep=";", nrows=5050)
                except (ValueError, UnicodeDecodeError, OSError):
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=";", nrows=5050)


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

            for _, row in df.iterrows():
                order_num = _get_val(row, "order number", "order no", "número de orden", "orden", "nº de orden")
                if not order_num or pd.isna(order_num):
                    continue

                order_num = str(order_num).strip()
                t_type_raw = str(_get_val(row, "type", "order type", "tipo") or "BUY").upper()
                trade_type = "SELL" if "SELL" in t_type_raw or "VENTA" in t_type_raw else "BUY"

                asset = str(_get_val(row, "asset", "crypto", "cripto", "criptomoneda") or "USDT").upper()
                fiat = str(_get_val(row, "fiat", "moneda fiat", "fiat currency") or "VES").upper()

                fiat_amt = float(_get_val(row, "total price", "total fiat", "monto fiat", "monto total", "total") or 0.0)
                crypto_amt = float(_get_val(row, "quantity", "amount", "cantidad", "cantidad cripto") or 0.0)
                unit_price = float(_get_val(row, "unit price", "price", "precio", "precio unitario") or (fiat_amt / crypto_amt if crypto_amt > 0 else 0.0))

                counterparty = str(_get_val(row, "counterparty", "contraparte", "counterpart", "usuario") or "")
                time_val = _get_val(row, "created time", "create time", "fecha", "fecha/hora", "date")

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
                    order_number=order_num,
                    trade_type=trade_type,
                    asset=asset,
                    fiat=fiat,
                    fiat_amount=fiat_amt,
                    crypto_amount=crypto_amt,
                    unit_price=unit_price,
                    fee_fiat=0.0,
                    fee_crypto=0.0,
                    bcv_rate=rate_cache[day_key],
                    order_status="COMPLETED",
                    counterparty_name=counterparty,
                    created_at=created_dt,
                )

                orders.append(order_entity)
                if trade_type == "BUY":
                    buy_count += 1
                else:
                    sell_count += 1

                if asset == "USDT":
                    vol_usdt += crypto_amt
                vol_fiat += fiat_amt

                existing = repo.get_by_order_number(order_num)
                if existing:
                    existing_count += 1
                else:
                    repo.create(order_entity)
                    inserted_count += 1

            # Auto-conciliar huérfanos con estas nuevas órdenes
            try:
                from src.integrations.receipt_ocr import BankReceiptOCR
                BankReceiptOCR().reconcile_orphan_vouchers(db=db, tolerance_hours=48, user_id=user_id)
            except (SQLAlchemyError, ValueError, TypeError, KeyError, OSError) as e:
                logger.warning(f"Error al auto-conciliar huérfanos tras importar archivo: {e}")

            return SyncHistoryResult(
                total_fetched=len(orders),
                orders_inserted=inserted_count,
                orders_existing=existing_count,
                buy_orders=buy_count,
                sell_orders=sell_count,
                total_volume_usdt=round(vol_usdt, 2),
                total_volume_fiat=round(vol_fiat, 2),
                orders=orders,
                success=True,
            )

        except (SQLAlchemyError, ValueError, TypeError, KeyError, OSError, UnicodeDecodeError) as err:
            logger.error(f"Error importando archivo de órdenes de Binance: {err}")
            return SyncHistoryResult(
                success=False,
                error_message=f"No se pudo procesar el archivo: {err}",
            )


