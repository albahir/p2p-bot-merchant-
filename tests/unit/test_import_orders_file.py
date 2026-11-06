"""Tests unitarios (TDD) para la importación directa de archivos Excel y CSV de órdenes de Binance."""

import io

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.database import Base
from src.data.repositories import OrderRepository


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_import_orders_from_excel_file():
    db = setup_in_memory_db()
    syncer = BinanceHistorySyncer()

    # Simular un DataFrame con columnas estándar de Binance P2P exportado
    df = pd.DataFrame([
        {
            "Order Number": "BINANCE-EXCEL-001",
            "Order Type": "BUY",
            "Asset": "USDT",
            "Fiat": "VES",
            "Total Price": 5500.0,
            "Quantity": 100.0,
            "Unit Price": 55.0,
            "Order Status": "Completed",
            "Counterparty": "Juan Binance",
            "Created Time": "2026-11-05 10:30:00",
        },
        {
            "Order Number": "BINANCE-EXCEL-002",
            "Order Type": "SELL",
            "Asset": "USDT",
            "Fiat": "VES",
            "Total Price": 2750.0,
            "Quantity": 50.0,
            "Unit Price": 55.0,
            "Order Status": "Completed",
            "Counterparty": "Maria P2P",
            "Created Time": "2026-11-05 11:00:00",
        },
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    excel_bytes = output.getvalue()

    result = syncer.import_orders_file(
        file_bytes=excel_bytes,
        filename="reporte_binance.xlsx",
        db=db,
    )

    assert result.success is True
    assert result.orders_inserted == 2

    repo = OrderRepository(db)
    orders = repo.list_completed()
    assert len(orders) == 2
    assert orders[0].order_number == "BINANCE-EXCEL-001"
