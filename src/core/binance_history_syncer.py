"""Sincronizador automático de historial de órdenes Binance P2P vía API oficial.

Permite consultar el endpoint GET /sapi/v1/c2c/orderMatch/listUserOrderHistory,
mapear las órdenes al modelo relacional Order, insertarlas de forma estrictamente
idempotente en la base de datos y generar reportes exportables en CSV.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.binance_client import BinanceAuthError, BinanceWeightExceededError
from src.core.binance_schemas import BinanceOrderMatchItem
from src.data.models import Order
from src.data.repositories import OrderRepository

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
    def _map_item_to_order(item: BinanceOrderMatchItem) -> Order:
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
            bcv_rate=0.0,
            order_status=str(item.orderStatus.value),
            counterparty_name=str(item.counterPartNickName or ""),
            created_at=created_dt,
        )

    @staticmethod
    def generate_orders_df(orders: list[Order]) -> pd.DataFrame:
        """Construye un DataFrame normalizado a partir de la lista de órdenes."""
        rows = [
            {
                "Número de Orden": o.order_number,
                "Tipo": o.trade_type,
                "Estado": o.order_status,
                "Criptoactivo": o.asset,
                "Cantidad Cripto": o.crypto_amount,
                "Moneda Fiat": o.fiat,
                "Monto Fiat": o.fiat_amount,
                "Precio Unitario": o.unit_price,
                "Comisión Cripto": o.fee_crypto,
                "Comisión Fiat": o.fee_fiat,
                "Contraparte": o.counterparty_name,
                "Fecha y Hora (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
            }
            for o in orders
        ]
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

        return output.getvalue()

    def sync_orders(
        self,
        client: Any,
        db: Session,
        days: int = 30,
        trade_type: str = "ALL",
        page_size: int = 50,
    ) -> SyncHistoryResult:
        """Extrae el historial de órdenes desde Binance API en ventanas de 30 días, las inserta en BD y genera el CSV."""
        safe_days = max(1, min(days, 365))
        now_dt = datetime.now(UTC)
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
        repo = OrderRepository(db)
        orders: list[Order] = []
        inserted_count = 0
        existing_count = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0

        try:
            for item in all_items:
                order_entity = self._map_item_to_order(item)
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
    ) -> SyncHistoryResult:
        """Parsea e importa órdenes de Binance P2P desde archivos Excel (.xlsx) o CSV descargados por el usuario."""
        import io
        repo = OrderRepository(db)
        orders: list[Order] = []
        inserted_count = 0
        existing_count = 0
        buy_count = 0
        sell_count = 0
        vol_usdt = 0.0
        vol_fiat = 0.0

        try:
            if filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=",")
                    if len(df.columns) <= 1:
                        df = pd.read_csv(io.BytesIO(file_bytes), sep=";")
                except (ValueError, UnicodeDecodeError, OSError):
                    df = pd.read_csv(io.BytesIO(file_bytes), sep=";")


            col_map = {str(c).strip().lower().replace("_", " "): c for c in df.columns}

            def _get_val(row: Any, *keys: str) -> Any:
                for k in keys:
                    for c_clean, c_orig in col_map.items():
                        if k in c_clean:
                            return row[c_orig]
                return None

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
                    bcv_rate=0.0,
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
                BankReceiptOCR().reconcile_orphan_vouchers(db=db, tolerance_hours=48)
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


