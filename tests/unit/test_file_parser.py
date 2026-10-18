"""Tests unitarios (TDD) para el parser inteligente de archivos exportados de Binance (SPEC-014).
Prueba formatos CSV y XLSX de C2C Orders, Deposits y Withdrawals.
"""

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.file_parser import BinanceFileParser
from src.data.database import Base
from src.data.repositories import OrderRepository


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_parse_c2c_csv(tmp_path):
    csv_content = """Número de Pedido,Tipo de orden,Activo,Tipo de Fiat,Precio Total,Precio,Cantidad,Tipo de cambio,Tarifa de creador,Comisión de tomador,Contraparte,Estado,Hora de creación
21888999000,Compra,USDT,VES,45000.00,45.00,1000.00,0,0,0,PEDRO PEREZ,Completado,2026-10-16 14:30:00
21888999001,Venta,USDT,VES,46500.00,46.50,1000.00,0,0,0,MARIA GOMEZ,Completado,2026-10-16 15:45:00
"""
    file_path = tmp_path / "c2c_sample.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    parser = BinanceFileParser()
    orders = parser.parse_c2c_file(str(file_path))

    assert len(orders) == 2
    o1 = orders[0]
    assert o1.order_number == "21888999000"
    assert o1.trade_type == "BUY"
    assert o1.crypto_amount == 1000.0
    assert o1.fiat_amount == 45000.0
    assert o1.unit_price == 45.0
    assert o1.order_status == "COMPLETED"

    o2 = orders[1]
    assert o2.order_number == "21888999001"
    assert o2.trade_type == "SELL"
    assert o2.fiat_amount == 46500.0


def test_parse_c2c_excel_with_metadata_headers(tmp_path):
    # Simular estructura exacta del Excel exportado por Binance (metadatos en filas 0-4)
    data = [
        ["", "", "", "", "", "www.binance.com"],
        ["", "Historial de órdenes C2C", "", "", "", ""],
        ["", "Nombre", "MANUEL RODRIGUEZ", "Email", "user@test.com", "Dirección"],
        ["", "ID de usuario", "924411621", "Período(UTC--4)", "2026-10-16 to 2026-10-17", ""],
        ["", "", "", "", "", ""],
        ["Número de Pedido", "Tipo de orden", "Activo", "Tipo de Fiat", "Precio Total", "Precio", "Cantidad", "Tipo de cambio", "Tarifa de creador", "Comisión de tomador", "Contraparte", "Estado", "Hora de creación"],
        ["21999111222", "Compra", "USDT", "VES", "18000.00", "45.00", "400.00", "0", "0", "0", "CARLOS SANCHEZ", "Completado", "2026-10-16 11:20:00"],
    ]
    df = pd.DataFrame(data)
    file_path = tmp_path / "c2c_metadata.xlsx"
    df.to_excel(file_path, header=False, index=False)

    parser = BinanceFileParser()
    orders = parser.parse_c2c_file(str(file_path))

    assert len(orders) == 1
    assert orders[0].order_number == "21999111222"
    assert orders[0].crypto_amount == 400.0
    assert orders[0].trade_type == "BUY"


def test_parse_deposits_csv_and_xlsx(tmp_path):
    csv_content = """Hora,Moneda,Red,Cantidad,Dirección,ID de transacción (TXID),Estado
2026-10-16 10:15:00,USDT,TRC20,150.00000000,TXYZ123456789,0x_deposit_txid_01,Completado
"""
    file_path = tmp_path / "deposits.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    parser = BinanceFileParser()
    movements = parser.parse_deposits_file(str(file_path))

    assert len(movements) == 1
    m = movements[0]
    assert m.movement_type == "DEPOSIT"
    assert m.asset == "USDT"
    assert m.amount == 150.0
    assert m.network == "TRC20"
    assert m.txid == "0x_deposit_txid_01"
    assert m.status == "COMPLETED"


def test_parse_withdrawals_csv_and_xlsx(tmp_path):
    csv_content = """Hora,Moneda,Red,Cantidad,Tarifa,Dirección,ID de transacción (TXID),Estado
2026-10-16 18:00:00,USDT,TRC20,50.00000000,1.00000000,TABC987654321,0x_withdraw_txid_02,Completado
"""
    file_path = tmp_path / "withdrawals.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    parser = BinanceFileParser()
    movements = parser.parse_withdrawals_file(str(file_path))

    assert len(movements) == 1
    w = movements[0]
    assert w.movement_type == "WITHDRAWAL"
    assert w.asset == "USDT"
    assert w.amount == 50.0
    assert w.fee == 1.0
    assert w.network == "TRC20"
    assert w.txid == "0x_withdraw_txid_02"
    assert w.status == "COMPLETED"


def test_save_parsed_records_to_database_idempotent(tmp_path):
    db = setup_in_memory_db()
    parser = BinanceFileParser()

    csv_content = """Número de Pedido,Tipo de orden,Activo,Tipo de Fiat,Precio Total,Precio,Cantidad,Tipo de cambio,Tarifa de creador,Comisión de tomador,Contraparte,Estado,Hora de creación
21888999555,Compra,USDT,VES,22500.00,45.00,500.00,0,0,0,PEDRO PEREZ,Completado,2026-10-16 14:30:00
"""
    file_path = tmp_path / "orders_idempotent.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    orders = parser.parse_c2c_file(str(file_path))
    inserted_count = parser.import_orders_to_db(orders, db)
    assert inserted_count == 1

    # Segunda importación del mismo archivo (Idempotencia)
    second_import = parser.import_orders_to_db(orders, db)
    assert second_import == 0

    order_repo = OrderRepository(db)
    assert order_repo.get_by_order_number("21888999555") is not None
