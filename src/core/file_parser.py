"""Parser inteligente de archivos exportados de Binance (CSV y Excel).
Procesa:
1. Historial de Órdenes C2C (P2P).
2. Historial de Depósitos On-Chain.
3. Historial de Retiros On-Chain.
Maneja encabezados en español e inglés y omite metadatos en archivos Excel.
"""

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from src.data.models import Order, WalletMovement

logger = logging.getLogger("binance_file_parser")


class BinanceFileParser:
    """Parser multi-formato para ingesta de datos históricos de Binance."""

    @staticmethod
    def _find_header_row_excel(file_path: str, keywords: list[str]) -> int:
        """Encuentra la fila donde comienzan los encabezados reales de la tabla."""
        df_raw = pd.read_excel(file_path, header=None, nrows=15)
        for idx, row in df_raw.iterrows():
            row_str = " ".join(str(val).lower() for val in row.values)
            if any(kw.lower() in row_str for kw in keywords):
                return int(idx)
        return 0

    @staticmethod
    def _parse_datetime(val: Any) -> datetime:
        """Parsea fechas en múltiples formatos comunes de Binance."""
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=UTC)
            return val
        val_str = str(val).strip()
        # Limpiar referencias de zona horaria como (UTC--4)
        val_str = re.sub(r"\(UTC[+-]?\d+\)", "", val_str).strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
        return datetime.now(UTC)

    @staticmethod
    def _parse_float(val: Any, default: float = 0.0) -> float:
        if val is None or pd.isna(val):
            return default
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip().replace("$", "").replace("VES", "").replace("USDT", "").strip()
        # Manejo de formatos numéricos con coma decimal
        if "," in val_str and "." in val_str:
            val_str = val_str.replace(",", "")
        elif "," in val_str:
            val_str = val_str.replace(",", ".")
        try:
            return float(val_str)
        except ValueError:
            return default

    def parse_c2c_file(self, file_path: str) -> list[Order]:
        """Parsea órdenes P2P/C2C desde archivo CSV o Excel."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        if file_path.lower().endswith((".xlsx", ".xls")):
            header_row = self._find_header_row_excel(
                file_path, ["número de pedido", "order number", "tipo de orden"]
            )
            df = pd.read_excel(file_path, header=header_row)
        else:
            df = pd.read_csv(file_path)

        # Normalizar nombres de columnas a minúsculas
        cols = {str(c).strip().lower(): c for c in df.columns}
        orders: list[Order] = []

        col_order_num = cols.get("número de pedido") or cols.get("order number")
        col_type = cols.get("tipo de orden") or cols.get("order type") or cols.get("trade type")
        col_asset = cols.get("activo") or cols.get("asset type") or cols.get("asset")
        col_fiat = cols.get("tipo de fiat") or cols.get("fiat type") or cols.get("fiat")
        col_total_fiat = cols.get("precio total") or cols.get("total price")
        col_price = cols.get("precio") or cols.get("unit price") or cols.get("price")
        col_qty = cols.get("cantidad") or cols.get("quantity") or cols.get("amount")
        col_fee_maker = cols.get("tarifa de creador") or cols.get("maker fee")
        col_fee_taker = cols.get("comisión de tomador") or cols.get("taker fee")
        col_status = cols.get("estado") or cols.get("status")
        col_date = cols.get("hora de creación") or cols.get("created time")
        col_counterparty = cols.get("contraparte") or cols.get("counterparty") or cols.get("counterpart")

        if not col_order_num or not col_type:
            logger.warning(f"Columnas clave no encontradas en {file_path}")
            return orders

        for _, row in df.iterrows():
            order_num = str(row[col_order_num]).strip()
            if not order_num or "no hay datos" in order_num.lower() or pd.isna(row[col_order_num]):
                continue

            raw_type = str(row[col_type]).strip().upper()
            trade_type = "BUY" if "COMPRA" in raw_type or "BUY" in raw_type else "SELL"

            raw_status = str(row[col_status]).strip().upper() if col_status else "COMPLETED"
            order_status = (
                "COMPLETED" if "COMPLET" in raw_status or "SUCCESS" in raw_status else "CANCELLED"
            )

            asset = str(row[col_asset]).strip().upper() if col_asset and not pd.isna(row[col_asset]) else "USDT"
            fiat = str(row[col_fiat]).strip().upper() if col_fiat and not pd.isna(row[col_fiat]) else "VES"

            fiat_amount = self._parse_float(row[col_total_fiat]) if col_total_fiat else 0.0
            unit_price = self._parse_float(row[col_price]) if col_price else 0.0
            crypto_amount = self._parse_float(row[col_qty]) if col_qty else 0.0

            if crypto_amount == 0.0 and unit_price > 0.0:
                crypto_amount = fiat_amount / unit_price

            fee_m = self._parse_float(row[col_fee_maker]) if col_fee_maker else 0.0
            fee_t = self._parse_float(row[col_fee_taker]) if col_fee_taker else 0.0
            total_fee = fee_m + fee_t

            created_at = self._parse_datetime(row[col_date]) if col_date else datetime.now(UTC)
            counterparty = (
                str(row[col_counterparty]).strip()
                if col_counterparty and not pd.isna(row[col_counterparty])
                else None
            )

            orders.append(
                Order(
                    order_number=order_num,
                    trade_type=trade_type,
                    asset=asset,
                    fiat=fiat,
                    fiat_amount=fiat_amount,
                    crypto_amount=crypto_amount,
                    unit_price=unit_price,
                    fee_fiat=total_fee,
                    fee_crypto=0.0,
                    bcv_rate=0.0,
                    order_status=order_status,
                    counterparty_name=counterparty,
                    created_at=created_at,
                )
            )


        return orders

    def parse_deposits_file(self, file_path: str) -> list[WalletMovement]:
        """Parsea depósitos on-chain desde archivo CSV o Excel."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        if file_path.lower().endswith((".xlsx", ".xls")):
            header_row = self._find_header_row_excel(
                file_path, ["hora", "time", "moneda", "coin"]
            )
            df = pd.read_excel(file_path, header=header_row)
        else:
            df = pd.read_csv(file_path)

        cols = {str(c).strip().lower(): c for c in df.columns}
        movements: list[WalletMovement] = []

        col_date = cols.get("hora") or cols.get("time") or cols.get("date")
        col_coin = cols.get("moneda") or cols.get("coin") or cols.get("currency")
        col_net = cols.get("red") or cols.get("network")
        col_qty = cols.get("cantidad") or cols.get("amount")
        col_addr = cols.get("dirección") or cols.get("address") or cols.get("deposit address")
        col_txid = (
            cols.get("id de transacción (txid)")
            or cols.get("txid")
            or cols.get("id de transacción")
        )
        col_status = cols.get("estado") or cols.get("status")

        for _, row in df.iterrows():
            if col_coin and pd.isna(row[col_coin]):
                continue
            first_val = str(row.iloc[0]).lower()
            if "no hay datos" in first_val or "none" in first_val:
                continue

            coin = str(row[col_coin]).strip().upper() if col_coin else "USDT"
            amount = self._parse_float(row[col_qty]) if col_qty else 0.0
            if amount <= 0:
                continue

            network = str(row[col_net]).strip() if col_net and not pd.isna(row[col_net]) else "TRC20"
            txid = str(row[col_txid]).strip() if col_txid and not pd.isna(row[col_txid]) else None
            address = str(row[col_addr]).strip() if col_addr and not pd.isna(row[col_addr]) else None

            raw_status = str(row[col_status]).strip().upper() if col_status else "COMPLETED"
            status = "COMPLETED" if "COMPLET" in raw_status or "SUCCESS" in raw_status else "PENDING"

            timestamp = self._parse_datetime(row[col_date]) if col_date else datetime.now(UTC)

            movements.append(
                WalletMovement(
                    movement_type="DEPOSIT",
                    asset=coin,
                    amount=amount,
                    fee=0.0,
                    network=network,
                    txid=txid,
                    address=address,
                    status=status,
                    timestamp=timestamp,
                )
            )

        return movements

    def parse_withdrawals_file(self, file_path: str) -> list[WalletMovement]:
        """Parsea retiros on-chain desde archivo CSV o Excel."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        if file_path.lower().endswith((".xlsx", ".xls")):
            header_row = self._find_header_row_excel(
                file_path, ["hora", "time", "moneda", "tarifa", "fee"]
            )
            df = pd.read_excel(file_path, header=header_row)
        else:
            df = pd.read_csv(file_path)

        cols = {str(c).strip().lower(): c for c in df.columns}
        movements: list[WalletMovement] = []

        col_date = cols.get("hora") or cols.get("time") or cols.get("date")
        col_coin = cols.get("moneda") or cols.get("coin") or cols.get("currency")
        col_net = cols.get("red") or cols.get("network")
        col_qty = cols.get("cantidad") or cols.get("amount")
        col_fee = cols.get("tarifa") or cols.get("fee") or cols.get("transaction fee")
        col_addr = (
            cols.get("dirección")
            or cols.get("address")
            or cols.get("destination address")
        )
        col_txid = (
            cols.get("id de transacción (txid)")
            or cols.get("txid")
            or cols.get("id de transacción")
        )
        col_status = cols.get("estado") or cols.get("status")

        for _, row in df.iterrows():
            if col_coin and pd.isna(row[col_coin]):
                continue
            first_val = str(row.iloc[0]).lower()
            if "no hay datos" in first_val:
                continue

            coin = str(row[col_coin]).strip().upper() if col_coin else "USDT"
            amount = self._parse_float(row[col_qty]) if col_qty else 0.0
            if amount <= 0:
                continue

            fee = self._parse_float(row[col_fee]) if col_fee else 0.0
            network = str(row[col_net]).strip() if col_net and not pd.isna(row[col_net]) else "TRC20"
            txid = str(row[col_txid]).strip() if col_txid and not pd.isna(row[col_txid]) else None
            address = str(row[col_addr]).strip() if col_addr and not pd.isna(row[col_addr]) else None

            raw_status = str(row[col_status]).strip().upper() if col_status else "COMPLETED"
            status = "COMPLETED" if "COMPLET" in raw_status or "SUCCESS" in raw_status else "PENDING"

            timestamp = self._parse_datetime(row[col_date]) if col_date else datetime.now(UTC)

            movements.append(
                WalletMovement(
                    movement_type="WITHDRAWAL",
                    asset=coin,
                    amount=amount,
                    fee=fee,
                    network=network,
                    txid=txid,
                    address=address,
                    status=status,
                    timestamp=timestamp,
                )
            )

        return movements

    def import_orders_to_db(self, orders: list[Order], db: Session) -> int:
        """Importa órdenes de forma estrictamente idempotente en la base de datos."""
        from src.data.repositories import OrderRepository

        repo = OrderRepository(db)
        inserted_count = 0
        for ord_item in orders:
            existing = repo.get_by_order_number(str(ord_item.order_number))
            if not existing:
                repo.create(ord_item)
                inserted_count += 1
        return inserted_count

    def import_movements_to_db(self, movements: list[WalletMovement], db: Session) -> int:
        """Importa depósitos y retiros de forma idempotente en la base de datos."""
        from src.data.repositories import WalletMovementRepository

        repo = WalletMovementRepository(db)
        inserted_count = 0
        for mov in movements:
            if mov.txid:
                existing = repo.get_by_txid(str(mov.txid))
                if existing:
                    continue
            repo.create(mov)
            inserted_count += 1
        return inserted_count

    @classmethod
    def import_into_database(cls, content: bytes, file_name: str, db: Session) -> dict[str, int]:
        """Guarda temporalmente el archivo, auto-detecta su tipo, lo parsea e inserta en la BD."""
        import tempfile

        parser = cls()
        suffix = ".xlsx" if file_name.lower().endswith((".xlsx", ".xls")) else ".csv"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        orders_imported = 0
        movements_imported = 0
        try:
            lower_name = file_name.lower()
            if "c2c" in lower_name or "orden" in lower_name or "order" in lower_name:
                orders = parser.parse_c2c_file(tmp_path)
                orders_imported = parser.import_orders_to_db(orders, db)
            elif "dep" in lower_name:
                deps = parser.parse_deposits_file(tmp_path)
                movements_imported = parser.import_movements_to_db(deps, db)
            elif "ret" in lower_name or "with" in lower_name:
                withs = parser.parse_withdrawals_file(tmp_path)
                movements_imported = parser.import_movements_to_db(withs, db)
            else:
                try:
                    orders = parser.parse_c2c_file(tmp_path)
                    orders_imported = parser.import_orders_to_db(orders, db)
                except (ValueError, KeyError, OSError, RuntimeError):
                    try:
                        deps = parser.parse_deposits_file(tmp_path)
                        movements_imported = parser.import_movements_to_db(deps, db)
                    except (ValueError, KeyError, OSError, RuntimeError):
                        withs = parser.parse_withdrawals_file(tmp_path)
                        movements_imported = parser.import_movements_to_db(withs, db)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return {
            "orders_imported": orders_imported,
            "movements_imported": movements_imported,
        }
